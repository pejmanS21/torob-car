import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from db.base import Base, UUIDPrimaryKeyMixin, enum_type
from enums import ChatRole
from models.user import utc_now

TITLE_MAX_LENGTH = 120


class Chat(UUIDPrimaryKeyMixin, Base):
    """One assistant conversation, owned by the account that started it."""

    __tablename__ = "chats"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(UUIDPrimaryKeyMixin, Base):
    """A turn in a chat. `listing_ids` are the cards the reply showed — ids only, so
    a reopened chat re-reads today's prices instead of replaying a stale snapshot."""

    __tablename__ = "chat_messages"

    chat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[ChatRole] = mapped_column(enum_type(ChatRole))
    text: Mapped[str] = mapped_column(Text)
    listing_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid()), default=list, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    chat: Mapped[Chat] = relationship(back_populates="messages")
