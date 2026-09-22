import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.chat import Chat, ChatMessage


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: uuid.UUID, limit: int) -> list[Chat]:
        found = await self._session.scalars(
            select(Chat)
            .where(Chat.user_id == user_id)
            .order_by(Chat.updated_at.desc())
            .limit(limit)
        )
        return list(found)

    async def get_owned(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> Chat | None:
        """Ownership is part of the lookup, so no caller can forget to check it."""
        return await self._session.scalar(
            select(Chat)
            .options(selectinload(Chat.messages))
            .where(Chat.id == chat_id, Chat.user_id == user_id)
        )

    async def add(self, chat: Chat) -> Chat:
        self._session.add(chat)
        await self._session.flush()
        return chat

    async def add_messages(self, messages: list[ChatMessage]) -> None:
        self._session.add_all(messages)
        await self._session.flush()

    async def remove(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            delete(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
        )
        return result.rowcount > 0
