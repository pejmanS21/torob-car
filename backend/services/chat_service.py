"""Assistant conversations that outlive the browser tab.

`AssistantService` stays stateless — it answers one question. This service wraps it:
it answers, then keeps the turn when the caller has an account.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import aclosing

from core.persian_prose import format_persian_prose
from enums import ChatRole
from errors import ChatNotFoundError
from models.chat import TITLE_MAX_LENGTH, Chat, ChatMessage
from models.user import utc_now
from repositories.chat_repository import ChatRepository
from repositories.listing_repository import ListingRepository
from schemas.assistant import (
    MAX_HISTORY,
    MAX_REPLY_LENGTH,
    AssistantMessage,
    AssistantRequest,
    AssistantResponse,
    AssistantTextUpdate,
)
from schemas.chat import MAX_CHATS, ChatDetail, ChatMessageRead, ChatSummary
from schemas.listing import ListingCard
from services.anonymous_chat_limit import AnonymousChatLimit
from services.assistant_service import AssistantService
from services.listing_views import to_card


def _title_of(question: str) -> str:
    return question[:TITLE_MAX_LENGTH]


class ChatService:
    def __init__(
        self,
        assistant: AssistantService,
        chats: ChatRepository,
        listings: ListingRepository,
        anonymous_limit: AnonymousChatLimit,
    ) -> None:
        self._assistant = assistant
        self._chats = chats
        self._listings = listings
        self._anonymous_limit = anonymous_limit

    async def ask(
        self, request: AssistantRequest, user_id: uuid.UUID | None, client_host: str
    ) -> AssistantResponse:
        """Anonymous callers still get an answer; only an account gets a transcript."""
        request, chat = await self._prepare(request, user_id, client_host)
        reply = await self._assistant.reply(request)
        return await self._save_reply(chat, request.question, reply)

    async def start_stream(
        self, request: AssistantRequest, user_id: uuid.UUID | None, client_host: str
    ) -> AsyncIterator[AssistantTextUpdate | AssistantResponse]:
        # Reject quota/ownership errors before HTTP streaming headers are sent.
        request, chat = await self._prepare(request, user_id, client_host)
        return self._stream_reply(request, chat)

    async def _prepare(
        self, request: AssistantRequest, user_id: uuid.UUID | None, client_host: str
    ) -> tuple[AssistantRequest, Chat | None]:
        if user_id is None:
            await self._anonymous_limit.enforce(client_host)
            return request, None
        chat = await self._resolve_chat(request, user_id)
        if request.chat_id is not None:
            messages = self._history_of(chat) + [request.messages[-1]]
            request = request.model_copy(update={"messages": messages})
        return request, chat

    async def _save_reply(
        self, chat: Chat | None, question: str, reply: AssistantResponse
    ) -> AssistantResponse:
        if chat is None:
            return reply
        await self._record(chat, question, reply)
        return reply.model_copy(update={"chat_id": chat.id})

    async def _stream_reply(
        self, request: AssistantRequest, chat: Chat | None
    ) -> AsyncIterator[AssistantTextUpdate | AssistantResponse]:
        async with aclosing(self._assistant.stream(request)) as stream:
            async for update in stream:
                if isinstance(update, AssistantResponse):
                    update = await self._save_reply(chat, request.question, update)
                yield update

    def _history_of(self, chat: Chat) -> list[AssistantMessage]:
        # Older stored replies may exceed today's transport limit.
        return [
            AssistantMessage(
                role=message.role,
                text=message.text[:MAX_REPLY_LENGTH],
                listing_ids=message.listing_ids,
            )
            for message in chat.messages[-(MAX_HISTORY - 1) :]
        ]

    async def list_chats(self, user_id: uuid.UUID) -> list[ChatSummary]:
        chats = await self._chats.list_for_user(user_id, MAX_CHATS)
        return [ChatSummary.model_validate(chat) for chat in chats]

    async def get_chat(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> ChatDetail:
        chat = await self._chats.get_owned(chat_id, user_id)
        if chat is None:
            raise ChatNotFoundError(chat_id)
        return ChatDetail(
            id=chat.id,
            title=chat.title,
            updated_at=chat.updated_at,
            messages=await self._messages_of(chat),
        )

    async def delete_chat(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> None:
        if not await self._chats.remove(chat_id, user_id):
            raise ChatNotFoundError(chat_id)

    async def _resolve_chat(
        self, request: AssistantRequest, user_id: uuid.UUID
    ) -> Chat:
        """Runs before the answer, so an unknown id costs a 404 and not an LLM call."""
        if request.chat_id is None:
            chat = await self._chats.add(
                Chat(user_id=user_id, title=_title_of(request.question))
            )
            # Signing in continues the visible guest conversation. Save its history
            # before making stored history authoritative on subsequent turns.
            await self._chats.add_messages(
                [
                    ChatMessage(
                        chat_id=chat.id,
                        role=message.role,
                        text=message.text,
                        listing_ids=message.listing_ids,
                    )
                    for message in request.messages[:-1]
                ]
            )
            return chat
        chat = await self._chats.get_owned(request.chat_id, user_id)
        if chat is None:
            raise ChatNotFoundError(request.chat_id)
        return chat

    async def _record(
        self, chat: Chat, question: str, reply: AssistantResponse
    ) -> None:
        chat.updated_at = utc_now()
        # ponytail: the pair is ordered by `created_at` alone, which `utc_now()` stamps
        # per row at flush. Microsecond resolution has always separated them; give the
        # rows an explicit sequence column if a coarser clock ever ties a turn.
        await self._chats.add_messages(
            [
                ChatMessage(chat_id=chat.id, role=ChatRole.USER, text=question),
                ChatMessage(
                    chat_id=chat.id,
                    role=ChatRole.ASSISTANT,
                    text=reply.text,
                    listing_ids=[card.id for card in reply.listings],
                ),
            ]
        )

    async def _messages_of(self, chat: Chat) -> list[ChatMessageRead]:
        cards = await self._cards_of(chat)
        return [
            ChatMessageRead(
                role=message.role,
                text=(
                    format_persian_prose(message.text)
                    if message.role is ChatRole.ASSISTANT
                    else message.text
                ),
                # A listing that has since gone is simply dropped from the card row.
                listings=[
                    cards[listing_id]
                    for listing_id in message.listing_ids
                    if listing_id in cards
                ],
            )
            for message in chat.messages
        ]

    async def _cards_of(self, chat: Chat) -> dict[uuid.UUID, ListingCard]:
        """One query for the whole transcript, not one per message."""
        wanted = {
            listing_id
            for message in chat.messages
            for listing_id in message.listing_ids
        }
        if not wanted:
            return {}
        found = await self._listings.get_by_ids(list(wanted))
        return {listing.id: to_card(listing) for listing in found}
