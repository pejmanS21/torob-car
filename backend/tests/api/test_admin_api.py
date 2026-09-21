"""Admin API. The first test is the important one: it proves no route escapes the
guard."""

import uuid

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.admin.router import router as admin_router
from enums import UserRole
from repositories.user_repository import UserRepository

pytestmark = pytest.mark.db

ADMIN = "/api/v1/admin"
PASSWORD = "correct horse"


def _error_code(response: Response) -> str:
    return response.json()["error"]["code"]


async def _register(api: AsyncClient, email: str) -> None:
    api.cookies.clear()
    body = {"email": email, "password": PASSWORD}
    assert (await api.post("/api/v1/auth/register", json=body)).status_code == 201


async def _promote(session: AsyncSession, email: str) -> None:
    user = await UserRepository(session).get_by_email(email)
    assert user is not None
    user.role = UserRole.ADMIN
    await session.flush()


@pytest.mark.parametrize(
    ("method", "path"),
    sorted(
        (method, route.path)
        for route in admin_router.routes
        for method in getattr(route, "methods", set())
        if method != "HEAD"
    ),
)
async def test_no_admin_route_is_reachable_without_admin(
    api: AsyncClient, method: str, path: str
) -> None:
    """Parametrised over the router's own routes, so a future endpoint cannot quietly
    skip the guard — adding one adds a case here automatically."""
    await _register(api, "driver@example.com")
    concrete = path.replace("{user_id}", str(uuid.UUID(int=9)))
    response = await api.request(method, f"/api/v1{concrete}")
    assert response.status_code == 403
    assert _error_code(response) == "permission_denied"


async def test_an_admin_can_list_and_search_users(
    api: AsyncClient, seeded_session: AsyncSession
) -> None:
    await _register(api, "admin@example.com")
    await _promote(seeded_session, "admin@example.com")
    listed = await api.get(f"{ADMIN}/users")
    assert listed.status_code == 200 and listed.json()["total"] >= 1
    searched = await api.get(f"{ADMIN}/users", params={"term": "admin"})
    assert [row["email"] for row in searched.json()["items"]] == ["admin@example.com"]


async def test_an_admin_cannot_demote_themselves(
    api: AsyncClient, seeded_session: AsyncSession
) -> None:
    await _register(api, "solo@example.com")
    await _promote(seeded_session, "solo@example.com")
    solo = await UserRepository(seeded_session).get_by_email("solo@example.com")
    assert solo is not None
    response = await api.patch(f"{ADMIN}/users/{solo.id}", json={"role": "user"})
    assert (response.status_code, _error_code(response)) == (409, "cannot_modify_self")


async def test_disabling_a_user_writes_an_audit_row(
    api: AsyncClient, seeded_session: AsyncSession
) -> None:
    await _register(api, "driver@example.com")
    target = await UserRepository(seeded_session).get_by_email("driver@example.com")
    assert target is not None
    await _register(api, "admin@example.com")
    await _promote(seeded_session, "admin@example.com")
    updated = await api.patch(f"{ADMIN}/users/{target.id}", json={"is_active": False})
    assert updated.status_code == 200 and updated.json()["is_active"] is False
    audit = (await api.get(f"{ADMIN}/audit")).json()
    assert audit["items"][0]["action"] == "user_disabled"
    assert audit["items"][0]["actor_email"] == "admin@example.com"


async def test_stats_reports_real_counts(
    api: AsyncClient, seeded_session: AsyncSession
) -> None:
    await _register(api, "admin@example.com")
    await _promote(seeded_session, "admin@example.com")
    stats = (await api.get(f"{ADMIN}/stats")).json()
    assert stats["users_total"] >= 1 and stats["admins_active"] >= 1
    assert stats["listings_total"] == 617  # the seeded fixture
