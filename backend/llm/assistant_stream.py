"""Extract only the reply's text from partial JSON, never tool args or reasoning."""

from pydantic_ai.messages import (
    AgentStreamEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)
from pydantic_core import from_json

from core.persian_prose import format_persian_prose
from schemas.assistant import MAX_REPLY_LENGTH


class AssistantTextStream:
    def __init__(self) -> None:
        self._raw = ""
        self._previous = ""

    def update(self, event: AgentStreamEvent) -> str | None:
        if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
            # A retry starts a new JSON answer; snapshots replace previous attempts.
            self._raw = event.part.content
        elif isinstance(event, PartDeltaEvent) and isinstance(
            event.delta, TextPartDelta
        ):
            self._raw += event.delta.content_delta
        else:
            return None
        raw = self._raw.lstrip().removeprefix("```json").removeprefix("```").lstrip()
        try:
            value = from_json(raw, allow_partial="trailing-strings")
        except ValueError:
            return None
        if not isinstance(value, dict) or not isinstance(value.get("text"), str):
            return None
        text = format_persian_prose(value["text"][:MAX_REPLY_LENGTH])
        if text == self._previous or not text:
            return None
        self._previous = text
        return text
