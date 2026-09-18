import uuid
from typing import Self

from pydantic import BaseModel, Field, model_validator

from enums import ChatRole, ParsedBy
from schemas.listing import ListingCard

MAX_MESSAGE_LENGTH = 500
MAX_HISTORY = 10
MAX_COMPARE_IDS = 3


class AssistantMessage(BaseModel):
    role: ChatRole
    text: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


class AssistantRequest(BaseModel):
    messages: list[AssistantMessage] = Field(min_length=1, max_length=MAX_HISTORY)
    compare_ids: list[uuid.UUID] = Field(
        default_factory=list, max_length=MAX_COMPARE_IDS
    )

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
