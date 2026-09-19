"""GET /catalog/suggest on the seeded fixture DB."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.db


async def test_suggest_is_typo_tolerant_and_capped(api: AsyncClient) -> None:
    response = await api.get("/api/v1/catalog/suggest", params={"q": "پژو 206 تیب"})
    rows = response.json()
    assert response.status_code == 200 and rows
    assert rows[0]["model"] == "پژو 206"
    assert {"brand", "model", "trim", "category", "count"} <= set(rows[0])
    everything = (await api.get("/api/v1/catalog/suggest", params={"q": "پ"})).json()
    assert len(everything) <= 10


async def test_suggest_respects_the_category_and_lists_the_largest_by_default(
    api: AsyncClient,
) -> None:
    motorcycles = (
        await api.get("/api/v1/catalog/suggest", params={"category": "motorcycle"})
    ).json()
    assert 0 < len(motorcycles) <= 10
    assert {row["category"] for row in motorcycles} == {"motorcycle"}
    counts = [row["count"] for row in motorcycles]
    assert counts == sorted(counts, reverse=True)


async def test_overlong_suggest_query_is_a_422(api: AsyncClient) -> None:
    response = await api.get("/api/v1/catalog/suggest", params={"q": "پ" * 101})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
