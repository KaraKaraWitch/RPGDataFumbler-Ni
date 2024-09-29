import textwrap
from typing import Generator


from .EventBase import EventBase, EventWrapped


class EventText(EventBase):
    # EventText extends from EventBase. 
    # This combines multiple show text codes into 1 bigger block
    
    # (faceName, faceIndex)
    # ...faceIndex is supposed to be a string but
    # I suppose it gets cast to an integer?
    faceData: tuple[str, int | str]
    background: int
    position: int
    text: str
    name: str | None
    is_predicted:bool

    @property
    def as_evtbase(self) -> Generator[EventBase, None, None]:
        if isinstance(self.faceData[1], str) and self.faceData[1] == "":
            self.faceData = (self.faceData[0], 0)
        root_params = [
            self.faceData[0],
            self.faceData[1],
            self.background,
            self.position,
        ]
        # Predicted self.name. ala MV Game
        if self.is_predicted:
            yield EventBase(code=101, indent=self.indent, parameters=root_params)
            yield EventBase(code=401, indent=self.indent, parameters=[self.name])
        # A MZ Game.
        elif self.name is not None:
            root_params.append(self.name)
            yield EventBase(code=101, indent=self.indent, parameters=root_params)
        # as is?
        else:
            yield EventBase(code=101, indent=self.indent, parameters=root_params)
            
        self.text = textwrap.fill(self.text)
        for section in self.text.split("\n"):
            yield EventBase(code=401, indent=self.indent, parameters=[section])


class EventChoice(EventBase, EventWrapped):
    # Does event choices.
    @classmethod
    def wrap(cls, event: EventBase) -> "EventChoice":
        return cls(code=event.code, indent=event.indent, parameters=event.parameters)

    @property
    def choices(self) -> tuple:
        return tuple(self.parameters[0])

    @choices.setter
    def choices(self, value: list[str]):
        self.parameters[0] = value
