"""POST /assistant on the seeded fixture DB (no LLM → rules path)."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from db.session import get_session
from dependencies.providers import (
    get_assistant_agent,
    get_cache,
    get_intent_agent,
)
from llm.assistant_agent import build_assistant_agent

pytestmark = pytest.mark.db


async def test_rules_answer_carries_real_cards(api: AsyncClient) -> None:
    body = {"messages": [{"role": "user", "text": "۲۰۶ تهران"}], "compare_ids": []}
    response = await api.post("/api/v1/assistant", json=body)
    assert response.status_code == 200, response.text
    reply = response.json()
    assert reply["answered_by"] == "rules"
    assert "آگهی پیدا کردم" in reply["text"]
    assert 0 < len(reply["listings"]) <= 3
    assert all(card["model"] == "پژو 206" for card in reply["listings"])


@pytest.mark.parametrize(
    "body",
    [
        {"messages": []},
        {"messages": [{"role": "user", "text": "پ" * 501}]},
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


async def test_overridden_agent_answers_through_the_llm_path(
    app, seeded_session, cache
) -> None:
    """Verify dependency override applies: agent override → LLM path not rules."""

    def scripted(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[
                ToolCallPart(
                    info.output_tools[0].name,
                    {"text": "سلام از ایچ‌تی‌ام‌ال", "listing_ids": []},
                )
            ]
        )

    async def use_seeded_session() -> AsyncIterator:
        yield seeded_session

    app.dependency_overrides[get_session] = use_seeded_session
    app.dependency_overrides[get_cache] = lambda: cache
    app.dependency_overrides[get_intent_agent] = lambda: None
    app.dependency_overrides[get_assistant_agent] = lambda: build_assistant_agent(
        FunctionModel(scripted)
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        body = {"messages": [{"role": "user", "text": "سلام"}], "compare_ids": []}
        response = await http.post("/api/v1/assistant", json=body)
        assert response.status_code == 200, response.text
        reply = response.json()
        assert reply["answered_by"] == "llm"
