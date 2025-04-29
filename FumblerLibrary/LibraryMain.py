import asyncio
import pathlib

from loguru import logger
import orjson

from FumblerLibrary.FumblerModels import SupportedRPGEngine, TomlConfig


async def process_csv(
    inputs: list[pathlib.Path],
    output_folder: pathlib.Path,
    config: TomlConfig,
    dump: bool = False,
    precheck: bool = False,
    format: SupportedRPGEngine = SupportedRPGEngine.js,
):
    from .Parsers.RawPaste.ParseCSV import CSVData
    from .Translators.OpenAICompatible.Translator import OAICompatTranslator

    parser = CSVData(inputs, config)
    if len(parser.parsed) == 0:
        logger.error("No CSV files detected.")
        return

    translator = OAICompatTranslator(config)
    logger.info(f"Translating: {len(parser.parsed)} files.")

    async def patch_worker(origFile: pathlib.Path, written_data):
        # Prepare containers for file and
        if written_data is None:
            return
        translation_containers = parser.prepare_tl_containers(written_data)
        if dump:
            if translation_containers and any([i for i in translation_containers if i]):
                translation_containers = [i.dump for i in translation_containers if i]
                if translation_containers:
                    output_file = (
                        output_folder / origFile.with_stem(origFile.stem + "_dump").name
                    ).write_bytes(
                        orjson.dumps(translation_containers, option=orjson.OPT_INDENT_2)
                    )
            origFile.unlink()
            return
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

        written_data = parser.apply_tl_containers(written_data, translation_containers)

        output_file = output_folder / origFile.name
        output_file.write_text(
            written_data,
            encoding="utf-8-sig",
        )
        origFile.unlink()

    await asyncio.gather(
        *[
            patch_worker(parsed_file, parsed_databundle)
            for parsed_file, parsed_databundle in parser.parsed
        ]
    )


async def process_rpgmaker(
    inputs: list[pathlib.Path],
    output_folder: pathlib.Path,
    config: TomlConfig,
    dump: bool = False,
    precheck: bool = False,
    format: SupportedRPGEngine = SupportedRPGEngine.js,
):
    from .Parsers.RPGMVMZ.GameParser import MVMZParser
    from .Translators.OpenAICompatible.Translator import OAICompatTranslator

    treat_as_ruby = SupportedRPGEngine.rb == format
    logger.debug(f"Treat as ruby? {treat_as_ruby}")
    parser = MVMZParser(inputs, config, is_ruby_like=treat_as_ruby)
    if len(parser.parsed) == 0:
        logger.error("No MV/MZ files detected.")
        return

    if precheck:
        print(parser.extract_prepass())
        return
    translator = OAICompatTranslator(config)
    logger.info(f"Translating: {len(parser.parsed)} files.")

    # Gross code wrapped into a worker
    async def patch_worker(origFile: pathlib.Path, parsed_data):
        # Prepare containers for file and
        if parsed_data is None:
            return
        translation_containers = parser.prepare_tl_containers(parsed_data)
        if dump:
            if translation_containers and any([i for i in translation_containers if i]):
                translation_containers = [i.dump for i in translation_containers if i]
                if translation_containers:
                    output_file = (
                        output_folder / origFile.with_stem(origFile.stem + "_dump").name
                    ).write_bytes(
                        orjson.dumps(translation_containers, option=orjson.OPT_INDENT_2)
                    )
            origFile.unlink()
            return
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

        parsed_data = parser.apply_tl_containers(parsed_data, translation_containers)

        output_file = output_folder / origFile.name
        output_dump_file = (
            output_folder / origFile.with_stem(origFile.stem + "_dump").name
        )

        if isinstance(parsed_data, list):
            parsed_data = [i.model_dump(mode="json") if i else i for i in parsed_data]
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
