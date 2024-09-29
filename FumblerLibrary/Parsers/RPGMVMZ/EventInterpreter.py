import re
from typing import Callable, Generator, List

import tqdm

from FumblerLibrary.FumblerModels import TomlConfig

from .EventsModels.EventBase import EventBase, EventTypes, EventWrapped
from .EventsModels.EventCommon import EventChoice, EventText
from .EventsModels.KMSActiveMessage import EvtPluginKMSActiveMessage

EVENTS_TYPES = EventBase | EventText | EvtPluginKMSActiveMessage | EventChoice

# Copied from DazedTL
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

OPEN_BRACE = set(["「", '"', "(", "（", "*", "["])

JP_DEEXPAND = re.compile(r"(\.{3}\.+)")
# JP_RUBY = re.compile(r'([\\]+[r][b]?\[.*?,(.*?)\])')


def transform_text(text: str):
    text = text.translate(JP_TRANSFORMS)
    text = JP_DEEXPAND.sub("...", text)
    return text
    # ruby text is complex.
    # I know that RJ366405 uses it in such a way
    # that it can break DazedMTL's ruby regex

    # def rb(match:re.Match):
    #     return match.group(1)

    # text = JP_RUBY.sub("...",text)


class EventInterpreter:
    def __init__(self, events: list[EventBase], config: TomlConfig) -> None:
        """RPG Maker Event Interpreter

        This parses Base Events into higher abstracted forms such as EvtText

        Args:
            events (list[EventBase]): _description_
        """
        self.events = events
        self.parsers: dict[int, Callable[[], EventBase | None]] = {
            EventTypes.SHOW_TEXT.value: self.showTextParser,
            EventTypes.SHOW_CHOICES.value: self.showChoices,
            EventTypes.EVENT_COMMENT.value: self.eventCommentParser,
            EventTypes.EVENT_COMMENT_2.value: self.eventCommentParser,
        }
        self.config_mvmz = config.engine.rpgmaker
        self.ptr = 0

    def defaultParseFn(self) -> EventBase:
        data = self.events[self.ptr]
        self.ptr += 1
        return data

    def showChoices(self) -> EventChoice:
        event_data = self.events[self.ptr]
        self.ptr += 1
        event_choice = EventChoice.wrap(event_data)
        if not event_choice:
            raise Exception("???")
        return event_choice

    @staticmethod
    def is_speaker(text: str, nxt_event: EventBase) -> str:
        # Length of string is shorter than X
        if len(text) > 40:
            return ""
        # Next text is a open brace.
        nxt_txt: str = nxt_event.parameters[0]
        nxt_txt = nxt_txt.strip()
        if nxt_txt and nxt_txt.strip()[0] in OPEN_BRACE:
            return text
        return ""

    def showTextParser(self) -> EventText:
        event_data = self.events[self.ptr]
        base_event = event_data
        name: str | None = None
        parse_speakers: bool = self.config_mvmz.speaker_check_for_mv
        is_predicted = False
        if len(event_data.parameters) == 5:
            faceName, faceIdx, bgmIdx, positionType, name = event_data.parameters
            value = {"name": event_data.parameters[4], "text": []}
        else:
            faceName, faceIdx, bgmIdx, positionType = event_data.parameters
            value = {"name": None, "text": []}
        if self.events[self.ptr + 1].code == EventTypes.ADD_TEXT.value:
            self.ptr += 1
            event_data = self.events[self.ptr]
            step = 0
            while event_data.code == EventTypes.ADD_TEXT.value:
                text: str = event_data.parameters[0]

                # Speaker check (See config for infomation.)
                if parse_speakers and value["name"] is None and step == 0:
                    # Check if the next event is available
                    if self.events[self.ptr + 1] is None:
                        pass
                    # Check if next is still "ADD_TEXT" instruction
                    elif self.events[self.ptr + 1].code != EventTypes.ADD_TEXT.value:
                        pass
                    elif self.is_speaker(text, self.events[self.ptr + 1]):
                        is_predicted = True
                        # If it's probably a speaker, set the name
                        value["name"] = text
                        step += 1
                        self.ptr += 1
                        nxt_data = self.events[self.ptr]
                        event_data = self.events[self.ptr]
                        continue
                # Append the text

                value["text"].append(text)
                # Increment pointer stuff
                step += 1
                self.ptr += 1
                # Get the next event data
                nxt_data = self.events[self.ptr]
                if nxt_data is None or event_data.code != EventTypes.ADD_TEXT.value:
                    break
                event_data = self.events[self.ptr]
        if not parse_speakers or value["name"] is None:
            value["text"] = "\n".join(value["text"])
        else:
            value["text"] = " ".join(value["text"])
        name = value["name"]
        return EventText(
            code=-1,
            indent=base_event.indent,
            is_predicted=is_predicted,
            parameters=[],
            text=value["text"],
            faceData=(faceName, faceIdx),
            background=bgmIdx,
            position=positionType,
            name=name,
        )

    def eventCommentParser(self):
        event_data = self.events[self.ptr]
        self.ptr += 1
        if EvtPluginKMSActiveMessage.wrap(event_data):
            return EvtPluginKMSActiveMessage.wrap(event_data)
        else:
            return event_data

    def run(self) -> Generator[EVENTS_TYPES | None, None, None]:
        self.ptr = 0
        with tqdm.tqdm(
            desc="EventInterp", total=len(self.events), disable=True
        ) as pbar:
            while self.ptr < len(self.events):
                yield self.parsers.get(
                    self.events[self.ptr].code, self.defaultParseFn
                )()
                pbar.n = self.ptr

    @staticmethod
    def decompile(
        raw_events: list[EventBase], config: TomlConfig
    ) -> Generator[EVENTS_TYPES | None, None, None]:
        return EventInterpreter(raw_events, config).run()

    @staticmethod
    def compile(
        events: Generator[EVENTS_TYPES, None, None] | List[EVENTS_TYPES | None],
    ) -> Generator[EventBase | None, None, None]:
        for event in events:
            if isinstance(event, EventText):
                for subevent in event.as_evtbase:
                    yield subevent
            elif isinstance(event, EventWrapped):
                yield super(EventBase, event)  # type: ignore
            elif isinstance(event, EventBase):
                if event.code < 0:
                    raise Exception(
                        f"Unexpected Non-conforming code: {event.code} used."
                    )
                yield event
            else:
                yield event
