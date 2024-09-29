import asyncio
import pathlib

import orjson
import tomli
import typer
from loguru import logger

from FumblerLibrary.FumblerModels import TomlConfig
from FumblerLibrary.LibraryMain import process_rpgmaker

app = typer.Typer()


def prepare_config(root_dir: pathlib.Path):
    config = TomlConfig(
        **tomli.loads((root_dir / "config.toml").read_text(encoding="utf-8"))
    )
    config.prompts.db = tomli.loads(
        (root_dir / "knowledge_db.toml").read_text(encoding="utf-8")
    )["db"]
    config.prompts.samples = orjson.loads(
        (root_dir / "sample.json").read_text(encoding="utf-8")
    )
    return config


@app.command(name="rpgmaker")
def rpgmaker():
    logger.info("Translating RPG Maker Data...")
    main_dir = pathlib.Path(__file__).resolve().parent

    files = list((main_dir / "inputs").glob("*.json"))
    output_folder = pathlib.Path("outputs")
    config = prepare_config(main_dir)
    asyncio.run(process_rpgmaker(files, output_folder, config))


@app.command(name="_")
def rpgmaker_dummy():
    pass


if __name__ == "__main__":
    app()
