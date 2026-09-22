"""Transport models for the stored assistant conversations (`GET /me/chats`)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from enums import ChatRole
from schemas.listing import ListingCard

MAX_CHATS = 50


class ChatSummary(BaseModel):
    """A row in the history list: enough to label it, nothing more."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    updated_at: datetime


class ChatMessageRead(BaseModel):
    role: ChatRole
    text: str
    listings: list[ListingCard]


class ChatDetail(BaseModel):
    id: uuid.UUID
    title: str
    updated_at: datetime
    messages: list[ChatMessageRead]
