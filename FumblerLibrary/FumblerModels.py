from typing import Any
import orjson
import pydantic


class PromptConfig(pydantic.BaseModel):
    system: str
    template: str | None
    batch: int
    history: int
    source_lang: str
    dest_lang: str
    modes: dict[str, str]
    _db: dict[str, str]
    _sample_in: dict[str, str]
    _sample_out: dict[str, str]

    transform_japanese:bool = True

    @property
    def get_text_db(self):
        db_text = "; ".join([f'"{k}": "{v}"' for k, v in self.db.items()])
        db_text = f"[{db_text}]"
        return db_text

    def get_system_prompt(self, mode: str):
        return self.system.format(
            db_data=self.get_text_db,
            source_lang=self.source_lang,
            dest_lang=self.dest_lang,
            mode=self.modes[mode],
            sample_in=orjson.dumps(
                self._sample_in, option=orjson.OPT_INDENT_2
            ).decode(),
            sample_out=orjson.dumps(
                self._sample_out, option=orjson.OPT_INDENT_2
            ).decode(),
        )

    @property
    def db(self):
        return self._db

    @db.setter
    def db(self, value):
        self._db = value

    @property
    def samples(self):
        return self._sample_in, self._sample_out

    @samples.setter
    def samples(self, value):
        self._sample_in, self._sample_out = value


class ApiConfig(pydantic.BaseModel):
    key: str
    host: str = ""
    model: str
    concurrency: int = 2
    params: dict[str, Any]

class MVMZMangling(pydantic.BaseModel):
    speaker_check_for_mv:bool = True
    

class EngineConfig(pydantic.BaseModel):
    
    rpgmaker:MVMZMangling


class TomlConfig(pydantic.BaseModel):
    prompts: PromptConfig
    api: ApiConfig
    engine: EngineConfig


class TranslationContainer(pydantic.BaseModel):
    tl_type: str
    data: dict[str, str | list | dict[str, list[str]]]
    translated: dict[str, str | list | dict] = {}

    @property
    def get_text_map(self):
        mappings = {}
        if not self.translated:
            return mappings
        transformed_keys = {k.upper():v for k,v in self.translated.items()}
        for k, v in self.data.items():
            if isinstance(v,list):
                v = tuple(v)
            mappings[v] = transformed_keys[k]
        return mappings
