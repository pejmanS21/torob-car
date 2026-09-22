import uuid
from typing import Self

from pydantic import BaseModel, Field, model_validator

from enums import ChatRole, ParsedBy
from schemas.listing import ListingCard

MAX_MESSAGE_LENGTH = 500  # what a person types into the box
# The model's own reply comes back in the next turn's history, and a generated answer
# is longer than the fixed sentences this used to send. Capping both at 500 rejected
# the second question of every conversation as `string_too_long`.
MAX_REPLY_LENGTH = 2_000
MAX_HISTORY = 10
MAX_COMPARE_IDS = 3


class AssistantMessage(BaseModel):
    role: ChatRole
    text: str = Field(min_length=1, max_length=MAX_REPLY_LENGTH)
    listing_ids: list[uuid.UUID] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def _a_question_stays_short(self) -> Self:
        """The looser cap is for replayed replies only; a question is still 500."""
        if self.role is ChatRole.USER and len(self.text) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"at most {MAX_MESSAGE_LENGTH} characters")
        if self.role is ChatRole.USER and self.listing_ids:
            raise ValueError("listing_ids belong to assistant recommendations only")
        return self


class AssistantRequest(BaseModel):
    messages: list[AssistantMessage] = Field(min_length=1, max_length=MAX_HISTORY)
    compare_ids: list[uuid.UUID] = Field(
        default_factory=list, max_length=MAX_COMPARE_IDS
    )
    # Which stored conversation this turn belongs to. `None` starts a new one — that
    # is exactly what the "new chat" button sends. Ignored for anonymous callers.
    chat_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _last_message_is_the_users(self) -> Self:
        if self.messages[-1].role is not ChatRole.USER:
            raise ValueError("the last message must come from the user")
        return self

    @property
    def question(self) -> str:
        return self.messages[-1].text


class AssistantResponse(BaseModel):
    text: str
    listings: list[ListingCard]
    answered_by: ParsedBy
    # The conversation this turn was stored in; `None` when nobody was logged in.
    chat_id: uuid.UUID | None = None


class AssistantTextUpdate(BaseModel):
    """The current readable text snapshot, not raw model JSON or reasoning."""

    text: str
