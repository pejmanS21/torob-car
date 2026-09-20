"""Saved listings, price alerts and the one-shot import, per user."""

import uuid

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.listing import Listing

pytestmark = pytest.mark.db

ME = "/api/v1/me"
PASSWORD = "correct horse"
ALERT = {"title": "۲۰۶ زیر ۵۰۰", "threshold": 500_000_000, "params": {"q": "۲۰۶"}}


async def _register(api: AsyncClient, email: str) -> None:
    api.cookies.clear()
    body = {"email": email, "password": PASSWORD}
    assert (await api.post("/api/v1/auth/register", json=body)).status_code == 201


async def _listing_id(session: AsyncSession) -> str:
    return str(await session.scalar(select(Listing.id).limit(1)))


def _error_code(response: Response) -> str:
    return response.json()["error"]["code"]


@pytest.mark.parametrize("path", ["", "/saved", "/alerts"])
async def test_every_me_route_needs_a_session(api: AsyncClient, path: str) -> None:
    response = await api.get(f"{ME}{path}")
    assert (response.status_code, _error_code(response)) == (401, "not_authenticated")


async def test_saving_is_idempotent_and_reversible(
    api: AsyncClient, seeded_session: AsyncSession
) -> None:
    await _register(api, "saver@example.com")
    listing_id = await _listing_id(seeded_session)
    for _ in range(2):
        assert (await api.put(f"{ME}/saved/{listing_id}")).status_code == 204
    assert (await api.get(f"{ME}/saved")).json() == [listing_id]
    for _ in range(2):
        assert (await api.delete(f"{ME}/saved/{listing_id}")).status_code == 204
    assert (await api.get(f"{ME}/saved")).json() == []


async def test_saving_an_unknown_listing_is_404(api: AsyncClient) -> None:
    await _register(api, "saver@example.com")
    response = await api.put(f"{ME}/saved/{uuid.UUID(int=5)}")
    assert (response.status_code, _error_code(response)) == (404, "listing_not_found")


async def test_alerts_are_created_listed_and_deleted(api: AsyncClient) -> None:
    await _register(api, "alerts@example.com")
    created = await api.post(f"{ME}/alerts", json=ALERT)
    assert created.status_code == 201
    alert = created.json()
    assert {key: alert[key] for key in ALERT} == ALERT
    assert [item["id"] for item in (await api.get(f"{ME}/alerts")).json()] == [
        alert["id"]
    ]
    assert (await api.delete(f"{ME}/alerts/{alert['id']}")).status_code == 204
    assert (await api.get(f"{ME}/alerts")).json() == []


async def test_another_users_alert_looks_like_it_does_not_exist(
    api: AsyncClient,
) -> None:
    await _register(api, "owner@example.com")
    alert_id = (await api.post(f"{ME}/alerts", json=ALERT)).json()["id"]
    await _register(api, "intruder@example.com")
    response = await api.delete(f"{ME}/alerts/{alert_id}")
    assert (response.status_code, _error_code(response)) == (404, "alert_not_found")


async def test_import_merges_once_and_is_idempotent(
    api: AsyncClient, seeded_session: AsyncSession
) -> None:
    await _register(api, "importer@example.com")
    listing_id = await _listing_id(seeded_session)
    payload = {
        "saved": [listing_id, str(uuid.UUID(int=5))],  # the second no longer exists
        "alerts": [ALERT, ALERT],
    }
    first = (await api.post(f"{ME}/import", json=payload)).json()
    second = (await api.post(f"{ME}/import", json=payload)).json()
    assert first["saved"] == [listing_id] and len(first["alerts"]) == 1
    assert second == first


async def test_an_oversized_import_is_rejected(api: AsyncClient) -> None:
    await _register(api, "importer@example.com")
    payload = {"saved": [str(uuid.uuid4()) for _ in range(501)], "alerts": []}
    response = await api.post(f"{ME}/import", json=payload)
    assert (response.status_code, _error_code(response)) == (422, "validation_error")
