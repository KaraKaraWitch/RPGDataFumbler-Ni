import re
from .EventBase import EventBase, EventWrapped


# KMS_MapActiveMessage
EvtActiveMessage_rgx = re.compile(
    r"<(?:アクティブメッセージ|ActiveMessage)\s*[:\s]\s*([^>]+)>"
)


class EvtPluginKMSActiveMessage(EventBase, EventWrapped):
    @classmethod
    def wrap(cls, event: EventBase) -> "EvtPluginKMSActiveMessage | None":
        return (
            EvtPluginKMSActiveMessage(
                code=event.code, indent=event.indent, parameters=event.parameters
            )
            if event.parameters
            and isinstance(event.parameters[0], str)
            and EvtActiveMessage_rgx.search(event.parameters[0])
            else None
        )

    @property
    def text(self):
        match = EvtActiveMessage_rgx.match(self.parameters[0])
        if match:
            return match.group(1)

    @text.setter
    def text(self, value: str):
        if "\n" in value:
            value = value.encode("unicode_escape").decode("utf-8")
        self.parameters[0] = f"<ActiveMessage:{value}>"
