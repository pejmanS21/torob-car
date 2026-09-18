"""GET /models/{model}/stats on the seeded fixture DB."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.db


async def test_model_stats_summarise_the_market(api: AsyncClient) -> None:
    response = await api.get("/api/v1/models/پژو ۲۰۶/stats")  # Persian digits resolve
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["model"] == "پژو 206" and body["brand"] == "پژو"
    assert body["category"] == "light" and body["count"] > 20
    assert body["year_min"] <= body["year_max"]
    assert body["price_min"] <= body["price_median"] <= body["price_max"]
    assert len(body["histogram"]) == 8
    priced = sum(bucket["count"] for bucket in body["histogram"])
    assert 0 < priced <= body["count"]
    counts = [trim["count"] for trim in body["trims"]]
    assert counts == sorted(counts, reverse=True) and sum(counts) == body["count"]
    scores = [card["deal_score"] for card in body["top_deals"]]
    assert 0 < len(scores) <= 6 and scores == sorted(scores, reverse=True)
    assert all(card["model"] == "پژو 206" for card in body["top_deals"])


async def test_unknown_model_is_a_404_envelope(api: AsyncClient) -> None:
    response = await api.get("/api/v1/models/بوگاتی/stats")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"
