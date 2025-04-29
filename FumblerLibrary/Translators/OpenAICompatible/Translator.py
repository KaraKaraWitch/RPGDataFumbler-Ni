import asyncio
import collections
from io import StringIO
import pathlib
import re
from copy import deepcopy
from itertools import islice
from typing import AsyncGenerator

import httpx
import httpx_sse
import jinja2
from .JsonDecoder import try_json_decode
import orjson
from loguru import logger
import tqdm

from FumblerLibrary.FumblerModels import TomlConfig, TranslationContainer

JP_TRANSFORMS = str.maketrans(
    {
        "？": "?",
        "！": "!",
        "。": ".",
        "…": "...",
        "　": " ",
        "―": "-",
        # Dakuten
        "\uff9e": "",
    }
)

JP_POSTFIX = str.maketrans(
    {
        "？": "?",
        "！": "!",
        "。": ".",
        "…": "...",
        "　": " ",
        "―": "-",
        # Dakuten
        "\uff9e": "",
    }
)


JP_DEEXPAND = re.compile(r"(\.{3}\.+)")
WAIT025 = re.compile(r"\\\.")
WAIT1 = re.compile(r"\\\|")
WAITKEYPRESS = re.compile(r"\\\!")
SFX = re.compile(r"\\SE\[(\d+)\]")
SMPPOSE = re.compile(r"\\SM\[(.+)\]")
# JP_RUBY = re.compile(r'([\\]+[r][b]?\[.*?,(.*?)\])')


def transform_text(text: str):
    text = text.translate(JP_TRANSFORMS)
    text = text.replace("  ", " ")
    text = JP_DEEXPAND.sub("...", text)
    # Experiment
    # The trick with fixing \. is to expand it into a for for the LLM to keep / rmemeber.
    text = WAIT025.sub("<PAUSE 0.25s>", text)
    text = WAIT1.sub("<PAUSE 1s>", text)
    text = WAITKEYPRESS.sub("<PAUSE KEY_PRESS>", text)
    text = SFX.sub(r"<SFX \1>", text)
    text = SMPPOSE.sub(r"<SM_POSE \1>", text)
    return text
    # ruby text is complex.
    # I know that RJ366405 uses it in such a way
    # that it can break DazedMTL's ruby regex

    # def rb(match:re.Match):
    #     return match.group(1)

    # text = JP_RUBY.sub("...",text)


SFXUnTransform = re.compile(r"<SFX (\d+)>")
SMPPOSEUnTransform = re.compile(r"<SM_POSE (.+)>")


def detransform(text: str):
    # print(text)
    replacements = (
        text
        # Fix weird spacing issues.
        .replace("<PAUSE KEY PRESS>", "<PAUSE KEY_PRESS>")
        .replace("<PAUSE KEYPRESS>", "<PAUSE KEY_PRESS>")
        .replace(" <PAUSE 0.25s> ", "\\.")
        .replace(" <PAUSE 1s> ", "\\|")
        .replace(" <PAUSE KEY_PRESS> ", "\\!")
        .replace(" <PAUSE 0.25s>", "\\.")
        .replace(" <PAUSE 1s>", "\\|")
        .replace(" <PAUSE KEY_PRESS>", "\\!")
        .replace("<PAUSE 0.25s>", "\\.")
        .replace("<PAUSE 1s>", "\\|")
        .replace("<PAUSE KEY_PRESS>", "\\!")
    )
    replacements = SFXUnTransform.sub(r"\\SE[\1]", replacements)
    replacements = SMPPOSEUnTransform.sub(r"\\SM[\1]", replacements)
    return replacements


def detransform_responses(text: dict[str, list[str] | str]):
    for k, v in deepcopy(text).items():
        if isinstance(v, str):
            v = detransform(v)
        elif isinstance(v, list):
            for idx, jp_string in enumerate(v):
                v[idx] = detransform(jp_string)
        text[k] = v
    return text


def normalize_responses(text: dict[str, list[str] | str]):
    for k, v in deepcopy(text).items():
        if isinstance(v, str):
            v = transform_text(v)
        elif isinstance(v, list):
            for idx, jp_string in enumerate(v):
                v[idx] = transform_text(jp_string)
        text[k] = v
    return text


class OAICompatTranslator:
    translator_dir = pathlib.Path(__file__).resolve().parent

    def __init__(self, config: TomlConfig) -> None:
        self.config = config
        # self.oai = openai.AsyncOpenAI(api_key=)
        self.debug = self.config.api.debug
        self.key = self.config.api.key
        self.completions = f"{self.config.api.host.rstrip('/')}/completions"
        self.template: jinja2.Template | None
        if self.config.prompts.template:
            self.template = jinja2.Template(
                (
                    self.translator_dir
                    / "llm-prompt-templates"
                    / f"{self.config.prompts.template}.jinja"
                ).read_text(encoding="utf-8")
            )
        else:
            self.template = None
        self.concurrency = asyncio.Semaphore(config.api.concurrency)
        self.session = httpx.AsyncClient(timeout=None)

    async def sse_execute(self, prompt: str, stopping_strings, param_args: dict):
        block = {
            "model": self.config.api.model,
            "prompt": prompt,
            "stop": stopping_strings,
            "stream": True,
            **param_args,
        }
        # print(orjson.dumps(block).decode())
        return httpx_sse.aconnect_sse(
            self.session,
            "POST",
            self.completions,
            headers={
                "user-agent": "ShinonTranslationAgent/1.0.0",
                "authorization": f"Bearer {self.key}",
            },
            json=block,
        )

    @staticmethod
    def dict_chunk(data, chunk: int):
        it = iter(data)
        for i in range(0, len(data), chunk):
            yield {k: data[k] for k in islice(it, chunk)}

    @staticmethod
    def wrap_json(data):
        return f"```json\n{orjson.dumps(data,option=orjson.OPT_INDENT_2).decode()}\n```"

    def format_messages(
        self,
        section_type: str,
        event_group: dict[str, str | dict[str, str | list[str]]],
    ):
        system_prompt = self.config.prompts.get_system_prompt(section_type)
        batch_size = self.config.prompts.batch
        for chunk in self.dict_chunk(event_group, batch_size):
            wrapped_chunk = normalize_responses(chunk)
            yield (
                system_prompt,
                chunk,
                {
                    "role": "user",
                    "content": self.wrap_json(wrapped_chunk),
                },
            )

    async def stream_to_str(
        self,
        stream: AsyncGenerator[httpx_sse.EventSource, None],
    ):
        buffer = StringIO()
        async with stream as fff:  # type: ignore
            try:
                with tqdm.tqdm(disable=True if self.debug else False) as pbar:
                    async for event in fff.aiter_sse():
                        if isinstance(event, httpx_sse.ServerSentEvent):
                            if event.data == "[DONE]":
                                pass
                            else:
                                event_data = try_json_decode(event.data)
                                if event_data is None:
                                    logger.warning(
                                        f"Server returned an error: \"{event_data}\""
                                    )
                                    return None
                                if "error" in event_data:
                                    logger.warning(
                                        f"Server returned an error: \"{event_data['error']}\""
                                    )
                                    return None
                                if "choices" in event_data:
                                    text = event_data["choices"][0]["text"]
                                    if self.jp_regex.search(text):
                                        return None
                                    buffer.write(text)
                                    if self.debug:
                                        print(event_data["choices"][0]["text"], end="",flush=True)
                                    pbar.update(1)
                    # print(event)
                return buffer.getvalue()
            except Exception as e:
                logger.exception(e)
                return None
                # raise e
        return None

    json_data_extractor = re.compile(r"(```)json(.*)\1", flags=re.DOTALL)
    jp_regex = re.compile(r"[一-龠]+|[ぁ-ゔ]+|[ァ-ヴー]+")
    JP_Braces = re.compile(r"[「」]")

    async def do_retryable_completion_text(
        self,
        prompt: str,
        raw_chunk: dict,
        stopping_strings: list[str],
        inject: str = "",
    ):
        tries = 10
        key_ignore = {}
        do_append = True
        if "response_format" in self.config.api.params:
            # response should just be json... in theory.
            do_append = False
        while tries > 0:
            try:
                # print(prompt + inject)
                r = await self.sse_execute(
                    prompt + inject if do_append else prompt,
                    stopping_strings,
                    self.config.api.params,
                )
            except Exception as e:
                logger.warning("Server returned an InternalServerError. Retrying")
                await asyncio.sleep(5)
                continue
            response: str | None = await self.stream_to_str(r)
            if response is None:
                logger.warning("Server Stopped sending. Retrying")
                await asyncio.sleep(5)
                continue
            if not response.strip():
                # logger.debug(prompt + inject)
                logger.warning("Server Sent empty response. Retrying...")
                await asyncio.sleep(5)
                continue
            if do_append:
                response = inject + response + "```"
                extracted_response = self.json_data_extractor.search(response)
                if not extracted_response:
                    logger.debug(response)
                    logger.warning(
                        f"! Can't find expected json output. Tries left: {tries}"
                    )
                    tries -= 1
                    continue
                try:
                    json_text = extracted_response.group(2)
                except Exception as e:
                    logger.warning(f"Cannot decode response: {e}. Tries left: {tries}")
            else:
                json_text = response
            
            response_json: dict|None = try_json_decode(json_text)
            extracted: str = json_text
            if response_json is None:
                logger.debug(json_text)
                logger.warning(f"Cannot decode response. Tries left: {tries}")
                tries -= 1
                continue
            if len(list(response_json.keys())) != len(list(raw_chunk.keys())):
                logger.debug(json_text)
                logger.warning(
                    f"Decoded keys: {len(list(response_json.keys()))} does not match expected. {len(list(raw_chunk.keys()))}. Tries left: {tries}"
                )
                tries -= 1
                continue
            if self.jp_regex.search(extracted):
                logger.debug(json_text)
                logger.warning(f"Found Japanese Text. Retrying... Tries left: {tries}")
                continue
            response_json = {k.upper(): v for k, v in response_json.items()}
            all_keys_matched = True
            for k, v in raw_chunk.items():
                # Check for JP braces in original
                if isinstance(v, str):
                    has_braces_inorig = len(self.JP_Braces.findall(v))
                else:
                    has_braces_inorig = 0

                if k.upper() not in response_json:
                    logger.debug(
                        orjson.dumps(response_json, option=orjson.OPT_INDENT_2)
                    )
                    logger.warning(f'Key: "{k.upper()}" Not present in response data')
                    all_keys_matched = False
                    break

                # Check type with original
                tl_data = response_json[k.upper()]
                if not isinstance(tl_data, type(v)):
                    logger.debug(
                        orjson.dumps(response_json, option=orjson.OPT_INDENT_2)
                    )
                    logger.warning(f'Key: "{k.upper()}" does not match expected type.')
                    all_keys_matched = False
                    break
                elif (
                    isinstance(v, list)
                    and isinstance(tl_data, list)
                    and len(tl_data) != len(v)
                ):
                    logger.debug(
                        orjson.dumps(response_json, option=orjson.OPT_INDENT_2)
                    )
                    logger.warning("List length does not match expected.")
                    all_keys_matched = False
                    break
                # Braces check.
                if isinstance(v, str):
                    if isinstance(tl_data, str):
                        has_braces_intl = len(self.JP_Braces.findall(tl_data))
                    else:
                        logger.debug(
                            orjson.dumps(response_json, option=orjson.OPT_INDENT_2)
                        )
                        logger.warning("Mismatched json key and value.")
                        all_keys_matched = False
                else:
                    has_braces_intl = 0
                if (
                    has_braces_inorig != has_braces_intl
                    and key_ignore.get(k.upper(), 0) <= 2
                ):
                    key_ignore[k.upper()] = key_ignore.setdefault(k.upper(), 0) + 1
                    logger.warning(f'Key: "{k.upper()}" does not match braces.')
                    all_keys_matched = False
                    break
            if not all_keys_matched:
                # tries -= 1
                continue
            # Apply post-fixes
            response_json = detransform_responses(normalize_responses(response_json))
            logger.debug(f"Final transformed: {response_json}")
            return response_json

    async def do_container(
        self, container: TranslationContainer
    ) -> TranslationContainer:
        section_type = container.tl_type
        section_data = container.data

        queue = collections.deque(maxlen=self.config.prompts.history * 2)
        for system, raw_chunk, chunk in self.format_messages(
            section_type, section_data
        ):
            async with self.concurrency:
                logger.debug(f"Working on chunk: {raw_chunk}")
                if self.template:
                    queue.append(chunk)
                    messages = [*queue]
                    messages.insert(-2,{"role": "system", "content": system})
                    
                    vars = {
                        "add_generation_prompt": True,
                        "stop_strings": [],
                        "messages": messages,
                    }
                    logger.debug(vars)

                    template_module = self.template.make_module(vars)
                    append_completion = f"\nLocalized & Translated text to {self.config.prompts.dest_lang}:\n```json"

                    response_json = await self.do_retryable_completion_text(
                        # HACK: adding "```json" is pretty rough but like... not too sure what else to do lmao
                        str(template_module),
                        raw_chunk,
                        template_module.stop_strings + ["```"],  # type: ignore
                        inject=append_completion,
                    )
                    if response_json is None:
                        logger.warning(f"Gave up with batch container: {raw_chunk}.")
                        break
                    if container.translated is None:
                        container.translated = {}
                    if response_json:
                        container.translated.update(response_json)
                        queue.append(
                            {
                                "role": "assistant",
                                "content": self.wrap_json(response_json),
                            }
                        )
                        logger.debug(
                            f"Translated chunk:\n{raw_chunk}\n -> {response_json}"
                        )
                else:
                    raise NotImplementedError()
        return container

    async def translate_containers_batched(
        self, to_tl_containers: list[TranslationContainer | None]
    ) -> list[TranslationContainer | None]:
        container_queue = asyncio.Queue()
        responses = []

        async def container_worker():
            while container_queue.qsize() > 0:
                try:
                    data: tuple[int, TranslationContainer] = (
                        container_queue.get_nowait()
                    )
                except asyncio.QueueEmpty:
                    break
                index, container = data
                container = await self.do_container(container)
                responses.append((index, container))

        loop = asyncio.get_running_loop()
        workers = [loop.create_task(container_worker()) for _ in range(5)]
        for idx, container in enumerate(to_tl_containers):
            if not container:
                continue
            # print(container)
            await container_queue.put((idx, container))
        await asyncio.gather(*workers)
        for idx, container in responses:
            to_tl_containers[idx] = container
        return to_tl_containers

    async def translate_containers(
        self, to_tl_containers: list[TranslationContainer | None]
    ) -> list[TranslationContainer | None]:
        logger.info(f"Translating: {len(to_tl_containers)} Containers")
        response = await self.translate_containers_batched(to_tl_containers)
        logger.info(f"Translated: {len(to_tl_containers)} Containers")
        return response
