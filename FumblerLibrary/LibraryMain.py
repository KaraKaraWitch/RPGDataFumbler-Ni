import asyncio
import pathlib

from loguru import logger
import orjson

from FumblerLibrary.FumblerModels import TomlConfig


async def process_rpgmaker(
    inputs: list[pathlib.Path], output_folder: pathlib.Path, config: TomlConfig
):
    from .Parsers.RPGMVMZ.GameParser import MVMZParser
    from .Translators.OpenAICompatible.Translator import OAICompatTranslator

    parser = MVMZParser(inputs, config)
    if len(parser.parsed) == 0:
        logger.error("No MV/MZ files detected.")
        return

    translator = OAICompatTranslator(config)
    logger.info(f"Translating: {len(parser.parsed)} files.")

    concurrent = asyncio.Semaphore(config.api.concurrency)

    # Gross code wrapped into a worker
    async def patch_worker(origFile: pathlib.Path, parsed_data):
        async with concurrent:
            # Prepare containers for file and
            if parsed_data is None:
                return
            translation_containers = parser.prepare_tl_containers(parsed_data)
            if not translation_containers:
                return
            logger.debug(translation_containers)
            logger.info(
                f"Translating: {len([i for i in translation_containers if i])} containers for {origFile.name}"
            )
            translation_containers = await translator.translate_containers(
                translation_containers
            )
            logger.debug(translation_containers)
            logger.info(f"Applying: {len([i for i in translation_containers if i])}")

            parsed_data = parser.apply_tl_containers(
                parsed_data, translation_containers
            )

            output_file = output_folder / origFile.name
            output_dump_file = (
                output_folder / origFile.with_stem(origFile.stem + "_dump").name
            )

            if isinstance(parsed_data, list):
                parsed_data = [
                    i.model_dump(mode="json") if i else i for i in parsed_data
                ]
                (output_file).write_bytes(
                    orjson.dumps(parsed_data, option=orjson.OPT_INDENT_2)
                )
            else:
                (output_file).write_bytes(
                    orjson.dumps(
                        parsed_data.model_dump(mode="json"),
                        option=orjson.OPT_INDENT_2,
                    )
                )
            output_dump_file.write_bytes(
                orjson.dumps(
                    parser.get_full_mapping(translation_containers, json=True),
                    option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS,
                )
            )
            origFile.unlink()

    await asyncio.gather(
        *[
            patch_worker(parsed_file, parsed_databundle)
            for parsed_file, parsed_databundle in parser.parsed
        ]
    )
