"""POST /estimates on the seeded fixture DB."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.db


async def _a_priced_206(api: AsyncClient) -> dict:
    body = (await api.get("/api/v1/search", params={"q": "۲۰۶ تیپ ۲"})).json()
    return next(item for item in body["items"] if item["est_price"] and item["km"])


async def test_estimate_matches_the_listing_it_is_modelled_on(api: AsyncClient) -> None:
    listing = await _a_priced_206(api)
    request = {
        "category": "light",
        "trim": listing["trim"],
        "year": listing["year"],
        "km": listing["km"],
        "insurance_months": listing["insurance_months"],
        "asking_price": listing["price"],
    }
    response = await api.post("/api/v1/estimates", json=request)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["low"] <= body["est_price"] <= body["high"]
    assert body["est_sample_size"] >= 5
    breakdown = body["breakdown"]
    assert set(breakdown) == {"base", "km_adjustment", "insurance_adjustment"}
    assert body["asking_verdict"] in {"cheap", "fair", "expensive"}
    assert body["asking_diff_pct"] is not None
    assert 0 < len(body["similar"]) <= 4
    assert all(card["model"] == "پژو 206" for card in body["similar"])
    # The same formulas as ingest: the listing's own estimate differs only by its
    # leave-one-out comparables, so the two agree to within a few percent.
    assert abs(body["est_price"] - listing["est_price"]) / listing["est_price"] < 0.1


async def test_no_asking_price_means_no_verdict(api: AsyncClient) -> None:
    listing = await _a_priced_206(api)
    request = {"category": "light", "trim": listing["trim"], "year": listing["year"]}
    body = (await api.post("/api/v1/estimates", json=request)).json()
    assert body["asking_verdict"] is None and body["asking_diff_pct"] is None


async def test_unknown_trim_is_a_422_invalid_search(api: AsyncClient) -> None:
    request = {"category": "light", "trim": "بوگاتی شیرون", "year": 1400}
    response = await api.post("/api/v1/estimates", json=request)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_search"


async def test_without_comparables_the_basis_chain_is_reported(
    api: AsyncClient,
) -> None:
    listing = await _a_priced_206(api)
    # A real trim, but a year nobody sells: every basis in the chain comes up empty.
    request = {"category": "light", "trim": listing["trim"], "year": 1320}
    response = await api.post("/api/v1/estimates", json=request)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "no_comparables"
    assert error["details"]["tried"] == [
        "trim_year",
        "trim_near_year",
        "model_year",
        "model_near_year",
    ]


@pytest.mark.parametrize(
    "bad",
    [
        {"year": 1200},
        {"year": 1398, "km": -1},
        {"year": 1398, "asking_price": 0},
        {"year": 1398, "category": "spaceship"},
    ],
)
async def test_invalid_bodies_are_422_envelopes_not_500s(
    api: AsyncClient, bad: dict
) -> None:
    request = {"category": "light", "trim": "پژو 206 تیپ ۲", **bad}
    response = await api.post("/api/v1/estimates", json=request)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
