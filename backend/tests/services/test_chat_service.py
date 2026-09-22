import uuid
from unittest.mock import AsyncMock

from enums import ChatRole, ParsedBy
from models.chat import Chat, ChatMessage
from schemas.assistant import AssistantMessage, AssistantRequest, AssistantResponse
from services.chat_service import ChatService


def request(text: str, chat_id: uuid.UUID | None = None) -> AssistantRequest:
    return AssistantRequest(
        messages=[AssistantMessage(role=ChatRole.USER, text=text)], chat_id=chat_id
    )


async def test_older_long_replies_can_be_followed_up_with_saved_card_ids() -> None:
    chat_id, user_id, listing_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    chat = Chat(
        id=chat_id,
        user_id=user_id,
        title="۲۰۶",
        messages=[
            ChatMessage(role=ChatRole.USER, text="۲۰۶ تهران", listing_ids=[]),
            ChatMessage(
                role=ChatRole.ASSISTANT, text="پ" * 2500, listing_ids=[listing_id]
            ),
        ],
    )
    chats, assistant = AsyncMock(), AsyncMock()
    chats.get_owned.return_value = chat
    assistant.reply.return_value = AssistantResponse(
        text="اولی", listings=[], answered_by=ParsedBy.LLM
    )
    service = ChatService(assistant, chats, AsyncMock(), AsyncMock())
    await service.ask(request("کدوم بهتره؟", chat_id), user_id, "visitor")
    history = assistant.reply.call_args.args[0].messages
    assert history[0].text == "۲۰۶ تهران"
    assert len(history[1].text) == 2000
    assert history[1].listing_ids == [listing_id]


async def test_guest_history_is_saved_when_signing_in_mid_conversation() -> None:
    chat_id, user_id, listing_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    chats, assistant, quota = AsyncMock(), AsyncMock(), AsyncMock()
    chats.add.return_value = Chat(id=chat_id, user_id=user_id, title="۲۰۶")
    assistant.reply.return_value = AssistantResponse(
        text="اولی", listings=[], answered_by=ParsedBy.LLM
    )
    service = ChatService(assistant, chats, AsyncMock(), quota)
    guest_history = [
        AssistantMessage(role=ChatRole.USER, text="۲۰۶ تهران"),
        AssistantMessage(
            role=ChatRole.ASSISTANT, text="پیدا کردم", listing_ids=[listing_id]
        ),
    ]
    current = request("کدوم بهتره؟")
    current.messages = guest_history + current.messages
    await service.ask(current, user_id, "visitor")
    imported = chats.add_messages.call_args_list[0].args[0]
    assert [message.text for message in imported] == [
        message.text for message in guest_history
    ]
    assert imported[1].listing_ids == [listing_id]
    quota.enforce.assert_not_called()


async def test_reopening_chat_does_not_rewrite_user_text_or_expand_its_length() -> None:
    text = "کمکارکرد" + "پ" * (500 - len("کمکارکرد"))
    chat = Chat(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="۲۰۶",
        messages=[
            ChatMessage(role=ChatRole.USER, text=text, listing_ids=[]),
            ChatMessage(role=ChatRole.ASSISTANT, text="بهصرفهبودن", listing_ids=[]),
        ],
    )
    service = ChatService(AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock())
    messages = await service._messages_of(chat)
    assert messages[0].text == text
    assert len(messages[0].text) == 500
    assert messages[1].text == "به‌صرفه بودن"
