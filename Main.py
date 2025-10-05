import asyncio
import pathlib

import orjson
import tomli
import typer
from loguru import logger

from FumblerLibrary.FumblerModels import SupportedRPGEngine, TomlConfig
from FumblerLibrary.LibraryMain import process_csv, process_rpgmaker

app = typer.Typer(pretty_exceptions_enable=False)


def prepare_config(root_dir: pathlib.Path, root: str):
    config = TomlConfig(
        **tomli.loads((root_dir / "config.toml").read_text(encoding="utf-8"))
    )
    config.prompts.db = tomli.loads(
        (root_dir / "knowledge_db.toml").read_text(encoding="utf-8")
    )["db"]
    config.prompts.samples = orjson.loads(
        (root_dir / f"sample.{root.lower()}.json").read_text(encoding="utf-8")
    )
    return config


@app.command(name="rpgmaker")
def rpgmaker(
    dump: bool = False,
    format: SupportedRPGEngine = SupportedRPGEngine.js.value,
    precheck: bool = False,
):
    """Translates input files as rpgmaker engine.

    --precheck: Dumps any infomation for a prepass. Currently only dumps names.

    --dump: Dumps the file into a raw parsed format. Does not translate anything



    --format: Sets the "Format to detect". Either "js" or "rb" (ruby) is accepted.

    You shouldn't need to change this unless you're doing a VX / VX Ace / XP game.



    NOTES:

    - The only format supported when in "ruby" / "rb" format is the exports from SnowSzn/rgss-db-cli.

    """
    logger.info("Translating RPG Maker Data...")
    main_dir = pathlib.Path(__file__).resolve().parent

    files = list((main_dir / "inputs").glob("*.json"))
    output_folder = pathlib.Path("outputs")
    config = prepare_config(main_dir, "rpgmaker")
    asyncio.run(
        process_rpgmaker(
            files, output_folder, config, dump=dump, format=format, precheck=precheck
        )
    )


@app.command(name="csv")
def csv():
    logger.info("Translating CSV...")
    main_dir = pathlib.Path(__file__).resolve().parent

    files = list((main_dir / "inputs").glob("*.csv"))
    output_folder = pathlib.Path("outputs")
    config = prepare_config(main_dir, "csv")
    asyncio.run(process_csv(files, output_folder, config))


if __name__ == "__main__":
    app()
