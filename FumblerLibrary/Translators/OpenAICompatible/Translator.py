import asyncio
import collections
from copy import deepcopy
import pathlib
import re
from itertools import islice

import httpx
import jinja2
from loguru import logger
import openai
import orjson
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
        "\uFF9E": "",
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
        "\uFF9E": "",
    }
)


JP_DEEXPAND = re.compile(r"(\.{3}\.+)")
# JP_RUBY = re.compile(r'([\\]+[r][b]?\[.*?,(.*?)\])')


def transform_text(text: str):
    text = text.translate(JP_TRANSFORMS)
    text = text.replace("  ", " ")
    text = JP_DEEXPAND.sub("...", text)
    return text
    # ruby text is complex.
    # I know that RJ366405 uses it in such a way
    # that it can break DazedMTL's ruby regex

    # def rb(match:re.Match):
    #     return match.group(1)

    # text = JP_RUBY.sub("...",text)


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
        self.oai = openai.AsyncOpenAI(api_key=self.config.api.key)
        self.oai.base_url = self.config.api.host
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
            if self.config.prompts.transform_inputs:
                wrapped_chunk = normalize_responses(chunk)
            else:
                wrapped_chunk = chunk
            yield (
                system_prompt,
                chunk,
                {
                    "role": "user",
                    "content": self.wrap_json(wrapped_chunk),
                },
            )

    async def stream_to_str(self, stream: openai.AsyncStream[openai.types.Completion]):
        buffer = ""
        try:
            async for chunk in stream:
                buffer += chunk.choices[0].text
        except Exception as e:
            logger.exception(e)
            return None
        return buffer

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
        while tries > 0:
            completion = await self.oai.completions.create(
                model=self.config.api.model,
                prompt=prompt + inject,
                stop=stopping_strings,
                extra_body=self.config.api.params,
                stream=True,
            )
            response: str | None = await self.stream_to_str(completion)
            if response is None:
                logger.warning("Server Stopped sending. Retrying")
                await asyncio.sleep(5)
                continue
            response = inject + response
            extracted_response = self.json_data_extractor.search(response)
            if not extracted_response:
                logger.debug(response)
                logger.warning(
                    f"! Can't find expected json output. Tries left: {tries}"
                )
                tries -= 1
                continue
            try:
                response_json: dict = orjson.loads(extracted_response.group(2))
                extracted: str = extracted_response.group(2)
            except orjson.JSONDecodeError as e:
                logger.debug(extracted_response.group(2))
                logger.warning(f"Cannot decode response: {e}. Tries left: {tries}")
                tries -= 1
                continue
            if len(list(response_json.keys())) != len(list(raw_chunk.keys())):
                logger.debug(extracted_response.group(2))
                logger.warning(
                    f"Decoded keys: {len(list(response_json.keys()))} does not match expected. {len(list(raw_chunk.keys()))}. Tries left: {tries}"
                )
                tries -= 1
                continue
            if self.jp_regex.search(extracted):
                logger.debug(extracted_response.group(2))
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
                    has_braces_intl = len(self.JP_Braces.findall(tl_data))
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
            if self.config.prompts.transform_inputs:
                response_json = normalize_responses(response_json)
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
                    vars = {
                        "add_generation_prompt": True,
                        "stop_strings": [],
                        "messages": [{"role": "system", "content": system}, *queue],
                    }
                    logger.debug(vars)

                    template_module = self.template.make_module(vars)
                    append_completion = (
                        f"\nTranslated text to {self.config.prompts.dest_lang}:\n```json"
                    )
                    
                    response_json = await self.do_retryable_completion_text(
                        # HACK: adding "```json" is pretty rough but like... not too sure what else to do lmao
                        str(template_module),
                        raw_chunk,
                        template_module.stop_strings,  # type: ignore
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
                        logger.debug(f"Translated chunk: {response_json}")
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
                    data: tuple[
                        int, TranslationContainer
                    ] = container_queue.get_nowait()
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
