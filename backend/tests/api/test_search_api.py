"""End-to-end golden queries (spec §11): real migrations, real ingest of the fixture
CSV, real SQL and ranking — only Redis and the LLM are replaced. Assertions are about
PROPERTIES of the ranking, never about specific listing ids."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.db
MILLION = 1_000_000


async def search(api: AsyncClient, **params: object) -> dict:
    response = await api.get("/api/v1/search", params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def test_model_query_returns_only_that_model_first(api: AsyncClient) -> None:
    body = await search(api, q="۲۰۶ تهران", page_size=10)
    assert body["parsed_by"] == "rules"
    assert body["intent"]["chips"] == ["پژو 206", "تهران"]
    assert [item["model"] for item in body["items"]] == ["پژو 206"] * 10


async def test_exact_matches_precede_near_misses(api: AsyncClient) -> None:
    body = await search(api, q="۲۰۶ تیپ ۲ تهران", page_size=50)
    exactness = [item["is_exact"] for item in body["items"]]
    assert exactness == sorted(exactness, reverse=True)
    assert body["exact_count"] == sum(exactness) > 0
    near_misses = [item for item in body["items"] if not item["is_exact"]]
    assert near_misses and all(item["near_miss_labels"] for item in near_misses)


async def test_budget_is_soft_but_bounded(api: AsyncClient) -> None:
    budget = 900 * MILLION
    body = await search(api, q="۲۰۶ زیر ۹۰۰ میلیون", page_size=50)
    prices = [item["price"] for item in body["items"] if item["price"]]
    assert prices and max(prices) <= budget * 1.25
    over = [item for item in body["items"] if item["price"] and item["price"] > budget]
    assert all("بالاتر از بودجه" in " ".join(i["near_miss_labels"]) for i in over)


async def test_nearer_city_beats_a_far_one(api: AsyncClient) -> None:
    body = await search(api, q="۲۰۶ تیپ ۲ تهران", page_size=50)
    cities = [item["city"] for item in body["items"]]
    assert cities[0] == "تهران"
    if "کرج" in cities and "مشهد" in cities:
        assert cities.index("کرج") < cities.index("مشهد")


async def test_other_models_never_precede_the_requested_model(api: AsyncClient) -> None:
    body = await search(api, q="۲۰۶", page_size=50)
    models = [item["model"] for item in body["items"]]
    last_206 = max(index for index, model in enumerate(models) if model == "پژو 206")
    assert all(model == "پژو 206" for model in models[: last_206 + 1])


async def test_explicit_filters_override_the_text(api: AsyncClient) -> None:
    body = await search(api, q="۲۰۶ تهران", cities=["مشهد"], sort="price")
    assert body["intent"]["cities"] == ["مشهد"]
    exact_prices = [i["price"] for i in body["items"] if i["is_exact"] and i["price"]]
    assert exact_prices == sorted(exact_prices)


async def test_heavy_vehicles_are_found_by_title_text(api: AsyncClient) -> None:
    body = await search(api, q="کامیون", category="heavy")
    assert body["total"] > 0
    assert {item["category"] for item in body["items"]} == {"heavy"}


async def test_browse_mode_and_stable_pagination(api: AsyncClient) -> None:
    first = await search(api, page=1, page_size=5)
    second = await search(api, page=2, page_size=5)
    assert first["total"] == 500  # capped at MAX_RESULTS
    ids = [item["id"] for item in first["items"] + second["items"]]
    assert len(set(ids)) == 10


async def test_paging_past_the_cap_is_a_clean_422(api: AsyncClient) -> None:
    response = await api.get("/api/v1/search", params={"page": 11, "page_size": 50})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_search"


async def test_overlong_query_is_rejected(api: AsyncClient) -> None:
    response = await api.get("/api/v1/search", params={"q": "پ" * 301})
    assert response.status_code == 422


async def test_detail_similar_batch_and_facets(api: AsyncClient) -> None:
    listing = (await search(api, q="۲۰۶ تیپ ۲ تهران"))["items"][0]
    detail = (await api.get(f"/api/v1/listings/{listing['id']}")).json()
    assert detail["token"] == listing["token"]
    assert set(detail["price_breakdown"]) >= {"base", "km_adjustment", "est_basis"}
    similar = (await api.get(f"/api/v1/listings/{listing['id']}/similar")).json()
    assert similar and listing["id"] not in [item["id"] for item in similar]
    assert similar[0]["model"] == "پژو 206"
    batch = await api.get("/api/v1/listings", params={"ids": [listing["id"]]})
    assert [item["id"] for item in batch.json()] == [listing["id"]]
    facets = (await api.get("/api/v1/facets")).json()
    assert facets["categories"]["light"] == 420
    assert facets["models"][0]["count"] >= facets["models"][-1]["count"]


async def test_unknown_listing_is_a_404_envelope(api: AsyncClient) -> None:
    missing = "00000000-0000-8000-8000-000000000000"
    response = await api.get(f"/api/v1/listings/{missing}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "listing_not_found"


async def test_readiness(api: AsyncClient) -> None:
    assert (await api.get("/health/ready")).json() == {"status": "ready"}


async def test_second_identical_search_is_served_from_the_cache(
    api: AsyncClient, cache
) -> None:
    await search(api, q="۲۰۶ تهران")
    keys_after_first = set(cache.values)
    body = await search(api, q="۲۰۶ تهران", page=2)
    assert set(cache.values) == keys_after_first  # nothing new was computed
    assert body["page"] == 2
