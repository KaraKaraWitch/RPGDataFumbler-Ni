from pydantic import BaseModel

class Dialogue(BaseModel):
    speaker:str
    dialogue:str
    tl_speaker:str = ""
    tl_dialogue:str = ""

class CSVBlock(BaseModel):
    dialogues:list[Dialogue]