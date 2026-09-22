"""Stored assistant conversations: who may read them and what a reload gets back."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response

pytestmark = pytest.mark.db

CHATS = "/api/v1/me/chats"
ASSISTANT = "/api/v1/assistant"
PASSWORD = "correct horse"
QUESTION = "۲۰۶ تیپ ۲ تهران"
FOLLOW_UP = "ارزان‌ترین سمند مشهد"


async def _register(api: AsyncClient, email: str) -> None:
    api.cookies.clear()
    body = {"email": email, "password": PASSWORD}
    assert (await api.post("/api/v1/auth/register", json=body)).status_code == 201


async def _ask(
    api: AsyncClient, text: str, chat_id: str | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"messages": [{"role": "user", "text": text}]}
    if chat_id is not None:
        body["chat_id"] = chat_id
    response = await api.post(ASSISTANT, json=body)
    assert response.status_code == 200
    return response.json()


def _error_code(response: Response) -> str:
    return response.json()["error"]["code"]


@pytest.mark.parametrize("path", ["", f"/{uuid.UUID(int=1)}"])
async def test_reading_chats_needs_a_session(api: AsyncClient, path: str) -> None:
    response = await api.get(f"{CHATS}{path}")
    assert (response.status_code, _error_code(response)) == (401, "not_authenticated")


async def test_anonymous_questions_are_answered_but_not_stored(
    api: AsyncClient,
) -> None:
    api.cookies.clear()
    answer = await _ask(api, QUESTION)
    assert answer["text"]
    assert answer["chat_id"] is None


async def test_a_question_starts_a_chat_titled_after_it(api: AsyncClient) -> None:
    await _register(api, "chatter@example.com")
    answer = await _ask(api, QUESTION)
    assert answer["chat_id"] is not None
    listed = (await api.get(CHATS)).json()
    assert [chat["title"] for chat in listed] == [QUESTION]
    assert listed[0]["id"] == answer["chat_id"]


async def test_a_follow_up_appends_to_the_same_chat(api: AsyncClient) -> None:
    await _register(api, "chatter@example.com")
    chat_id = (await _ask(api, QUESTION))["chat_id"]
    assert (await _ask(api, FOLLOW_UP, chat_id))["chat_id"] == chat_id

    assert len((await api.get(CHATS)).json()) == 1
    detail = (await api.get(f"{CHATS}/{chat_id}")).json()
    said = [message["text"] for message in detail["messages"]]
    assert [said[0], said[2]] == [QUESTION, FOLLOW_UP]
    assert [message["role"] for message in detail["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


async def test_a_reopened_chat_carries_the_cards_back(api: AsyncClient) -> None:
    await _register(api, "chatter@example.com")
    answer = await _ask(api, QUESTION)
    detail = (await api.get(f"{CHATS}/{answer['chat_id']}")).json()
    replied = detail["messages"][1]
    assert [card["id"] for card in replied["listings"]] == [
        card["id"] for card in answer["listings"]
    ]


async def test_a_new_chat_does_not_touch_the_previous_one(api: AsyncClient) -> None:
    await _register(api, "chatter@example.com")
    first = (await _ask(api, QUESTION))["chat_id"]
    second = (await _ask(api, FOLLOW_UP))["chat_id"]  # no chat_id = "new chat"
    assert first != second
    assert {chat["id"] for chat in (await api.get(CHATS)).json()} == {first, second}


async def test_chats_are_deleted(api: AsyncClient) -> None:
    await _register(api, "chatter@example.com")
    chat_id = (await _ask(api, QUESTION))["chat_id"]
    assert (await api.delete(f"{CHATS}/{chat_id}")).status_code == 204
    assert (await api.get(CHATS)).json() == []
    assert _error_code(await api.delete(f"{CHATS}/{chat_id}")) == "chat_not_found"


async def test_another_users_chat_is_invisible(api: AsyncClient) -> None:
    await _register(api, "owner@example.com")
    chat_id = (await _ask(api, QUESTION))["chat_id"]

    await _register(api, "stranger@example.com")
    assert (await api.get(CHATS)).json() == []
    for response in (
        await api.get(f"{CHATS}/{chat_id}"),
        await api.delete(f"{CHATS}/{chat_id}"),
    ):
        assert (response.status_code, _error_code(response)) == (404, "chat_not_found")


async def test_answering_into_an_unowned_chat_is_404(api: AsyncClient) -> None:
    await _register(api, "chatter@example.com")
    response = await api.post(
        ASSISTANT,
        json={
            "messages": [{"role": "user", "text": QUESTION}],
            "chat_id": str(uuid.UUID(int=7)),
        },
    )
    assert (response.status_code, _error_code(response)) == (404, "chat_not_found")
