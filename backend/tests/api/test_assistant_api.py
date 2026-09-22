"""POST /assistant on the seeded fixture DB. The `api` fixture wires a scripted model,
so these exercise the only two outcomes the endpoint has: the LLM answers, or it says
it cannot — there is no third, script-written reply."""

import json
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from db.session import get_session
from dependencies.providers import (
    get_assistant_agent,
    get_cache,
    get_intent_agent,
)

pytestmark = pytest.mark.db


def stream_events(text: str) -> list[tuple[str, dict]]:
    events = []
    for frame in text.split("\n\n"):
        if frame.startswith("event:"):
            name, data = frame.split("\n", 1)
            events.append(
                (name.removeprefix("event: "), json.loads(data.removeprefix("data: ")))
            )
    return events


async def test_stream_sends_readable_text_then_cards_and_persists_before_done(
    api: AsyncClient,
) -> None:
    await api.post(
        "/api/v1/auth/register",
        json={"email": "stream@example.com", "password": "stream-password"},
    )
    response = await api.post(
        "/api/v1/assistant/stream",
        json={"messages": [{"role": "user", "text": "۲۰۶ تهران"}]},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    events = stream_events(response.text)
    assert events[0][0] == "text"
    assert events[-1][0] == "done"
    reply = events[-1][1]
    assert reply["listings"]
    assert reply["chat_id"]
    assert events[0][1]["text"] in reply["text"]
    saved = await api.get("/api/v1/me/chats/" + reply["chat_id"])
    assert saved.status_code == 200
    assert saved.json()["messages"][-1]["text"] == reply["text"]


async def test_stream_and_json_share_the_guest_quota(api: AsyncClient) -> None:
    body = {"messages": [{"role": "user", "text": "۲۰۶ تهران"}]}
    for suffix in ("", "/stream", "/stream"):
        response = await api.post("/api/v1/assistant" + suffix, json=body)
        assert response.status_code == 200, response.text
        if suffix:
            assert stream_events(response.text)[-1][0] == "done"
    for suffix in ("", "/stream"):
        response = await api.post("/api/v1/assistant" + suffix, json=body)
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "anonymous_chat_limit"


async def test_the_answer_carries_real_cards(api: AsyncClient) -> None:
    body = {"messages": [{"role": "user", "text": "۲۰۶ تهران"}], "compare_ids": []}
    response = await api.post("/api/v1/assistant", json=body)
    assert response.status_code == 200, response.text
    reply = response.json()
    assert reply["answered_by"] == "llm"
    assert 0 < len(reply["listings"]) <= 3
    assert all(card["model"] == "پژو 206" for card in reply["listings"])


async def test_a_long_reply_can_be_replayed_as_history(api: AsyncClient) -> None:
    """A generated answer is longer than the fixed sentences this used to send. When
    both caps were 500 the *second* question of every conversation was rejected."""
    body = {
        "messages": [
            {"role": "user", "text": "۲۰۶ تهران"},
            {"role": "assistant", "text": "پ" * 1_500},
            {"role": "user", "text": "بین این‌ها کدوم به‌صرفه‌تره؟"},
        ],
        "compare_ids": [],
    }
    response = await api.post("/api/v1/assistant", json=body)
    assert response.status_code == 200, response.text


async def test_fourth_anonymous_message_is_blocked_but_sign_in_continues(
    api: AsyncClient,
) -> None:
    body = {"messages": [{"role": "user", "text": "۲۰۶ تهران"}]}
    for _ in range(3):
        assert (await api.post("/api/v1/assistant", json=body)).status_code == 200
    # Supplying a new chat and spoofing a forwarding header cannot reset the quota.
    limited = await api.post(
        "/api/v1/assistant", json=body, headers={"X-Forwarded-For": "192.0.2.99"}
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "anonymous_chat_limit"
    assert int(limited.headers["Retry-After"]) > 0
    registered = await api.post(
        "/api/v1/auth/register",
        json={"email": "quota@example.com", "password": "strong-enough-password"},
    )
    assert registered.status_code == 201, registered.text
    assert (await api.post("/api/v1/assistant", json=body)).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"messages": []},
        {"messages": [{"role": "user", "text": "پ" * 501}]},
        {"messages": [{"role": "assistant", "text": "پ" * 2001}]},
        {"messages": [{"role": "assistant", "text": "سلام"}]},
        {"messages": [{"role": "user", "text": "سلام"}] * 11},
    ],
)
async def test_invalid_chat_bodies_are_422_envelopes(
    api: AsyncClient, body: dict
) -> None:
    response = await api.post("/api/v1/assistant", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_without_a_model_the_chat_says_so_instead_of_answering(
    app, seeded_session, cache
) -> None:
    """The whole point of dropping the rules reply: an outage is visible, not papered
    over with a sentence the model never wrote."""

    async def use_seeded_session() -> AsyncIterator:
        yield seeded_session

    app.dependency_overrides[get_session] = use_seeded_session
    app.dependency_overrides[get_cache] = lambda: cache
    app.dependency_overrides[get_intent_agent] = lambda: None
    app.dependency_overrides[get_assistant_agent] = lambda: None
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        body = {"messages": [{"role": "user", "text": "سلام"}], "compare_ids": []}
        response = await http.post("/api/v1/assistant", json=body)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "assistant_unavailable"
