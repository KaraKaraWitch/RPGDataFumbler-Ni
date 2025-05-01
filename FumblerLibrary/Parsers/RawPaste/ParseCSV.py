import csv
from io import StringIO
import pathlib
from typing import Any

from FumblerLibrary.FumblerModels import TomlConfig, TranslationContainer
from .CSVModels import Dialogue, CSVBlock


class CSVData:
    def __init__(
        self, files: list[pathlib.Path], config: TomlConfig, sig: bool = False
    ) -> None:
        self.files = files
        self.sig = sig
        self.parsed: list[tuple[pathlib.Path, Any]] = []
        self.parse()

    def parse(self):
        for file in self.files:
            with open(file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                lines = []
                for row in reader:
                    print(row)
                    if "\ufeffSpeaker":
                        key = "\ufeffSpeaker"
                    else:
                        key = "Speaker"
                    lines.append(
                        Dialogue(
                            speaker=row.get(key, ""),
                            dialogue=row.get("Dialogue", ""),
                        )
                    )
                self.parsed.append((file, CSVBlock(dialogues=lines)))

    def prepare_tl_containers(
        self, data: Any
    ) -> list[TranslationContainer | None] | None:
        if isinstance(data, CSVBlock):
            return [
                TranslationContainer(
                    tl_type="event",
                    data={
                        f"L_{str(idx).zfill(2)}": [
                            dialogue.speaker,
                            dialogue.dialogue,
                        ]
                        for idx, dialogue in enumerate(data.dialogues)
                    },
                )
            ]

    def apply_tl_containers(
        self, parsed_block: CSVBlock, containers: list[TranslationContainer | None]
    ) -> str:
        if len(containers) == 1 and containers[0]:
            for dkey, dialogue in containers[0].translated.items():
                name, dialoguetext = dialogue
                linekey = int(dkey.split("_")[1])
                parsed_block.dialogues[linekey].tl_speaker = name
                parsed_block.dialogues[linekey].tl_dialogue = dialoguetext

        with StringIO(newline="") as f:
            writer = csv.DictWriter(
                f, ["Speaker", "Dialogue", "tl_Speaker", "tl_Dialogue"], lineterminator="\n"
            )
            writer.writeheader()
            for row in parsed_block.dialogues:
                writer.writerow(
                    {
                        "Speaker": row.speaker,
                        "Dialogue": row.dialogue,
                        "tl_Speaker": row.tl_speaker,
                        "tl_Dialogue": row.tl_dialogue,
                    }
                )
            return f.getvalue()
