"""POST /assistant on the seeded fixture DB (no LLM → rules path)."""

import pytest
from httpx import AsyncClient

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
