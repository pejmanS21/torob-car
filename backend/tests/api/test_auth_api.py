"""The /auth flow end to end on the test database."""

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import TokenClaims, encode_token
from enums import TokenType, UserRole
from repositories.user_repository import UserRepository
from tests.support import TEST_JWT_SECRET

pytestmark = pytest.mark.db

AUTH = "/api/v1/auth"
EMAIL = "driver@example.com"
PASSWORD = "correct horse"
CREDENTIALS = {"email": EMAIL, "password": PASSWORD}
THIRTY_DAYS_IN_SECONDS = 30 * 24 * 60 * 60


def _cookie(response: Response, name: str) -> str:
    cookies = response.headers.get_list("set-cookie")
    return next(cookie for cookie in cookies if cookie.startswith(f"{name}="))


def _error_code(response: Response) -> str:
    return response.json()["error"]["code"]


async def test_register_logs_in_and_sets_both_cookies(api: AsyncClient) -> None:
    response = await api.post(f"{AUTH}/register", json=CREDENTIALS)
    assert response.status_code == 201
    body = response.json()
    assert (body["email"], body["role"]) == (EMAIL, "user")
    assert set(body) == {"id", "email", "role", "created_at"}
    access = _cookie(response, "access_token")
    refresh = _cookie(response, "refresh_token")
    for cookie in (access, refresh):
        assert "HttpOnly" in cookie and "SameSite=lax" in cookie
        assert f"Max-Age={THIRTY_DAYS_IN_SECONDS}" in cookie
        assert "Secure" not in cookie  # ENV=development in tests
    assert "Path=/api/v1/auth" in refresh and "Path=/api/v1/auth" not in access


async def test_the_session_lasts_until_logout(api: AsyncClient) -> None:
    await api.post(f"{AUTH}/register", json=CREDENTIALS)
    assert (await api.get("/api/v1/me")).json()["email"] == EMAIL
    assert (await api.post(f"{AUTH}/logout")).status_code == 204
    after = await api.get("/api/v1/me")
    assert (after.status_code, _error_code(after)) == (401, "not_authenticated")


async def test_login_is_case_insensitive_and_rejects_bad_credentials(
    api: AsyncClient,
) -> None:
    await api.post(f"{AUTH}/register", json=CREDENTIALS)
    api.cookies.clear()
    shouting = {"email": "DRIVER@Example.com", "password": PASSWORD}
    assert (await api.post(f"{AUTH}/login", json=shouting)).status_code == 200
    for wrong in (
        {"email": EMAIL, "password": "a wrong password"},
        {"email": "nobody@example.com", "password": PASSWORD},
    ):
        response = await api.post(f"{AUTH}/login", json=wrong)
        assert (response.status_code, _error_code(response)) == (
            401,
            "invalid_credentials",
        )
        assert response.json()["error"]["message"] == "Invalid email or password"


async def test_a_duplicate_email_is_409_and_a_short_password_is_422(
    api: AsyncClient,
) -> None:
    await api.post(f"{AUTH}/register", json=CREDENTIALS)
    duplicate = await api.post(f"{AUTH}/register", json=CREDENTIALS)
    assert (duplicate.status_code, _error_code(duplicate)) == (409, "email_taken")
    short = await api.post(
        f"{AUTH}/register", json={"email": "new@example.com", "password": "short"}
    )
    assert (short.status_code, _error_code(short)) == (422, "validation_error")


async def test_an_expired_access_token_says_token_expired(api: AsyncClient) -> None:
    # auth_at is irrelevant here — this test is about the exp claim, not freshness.
    claims = TokenClaims(uuid.UUID(int=1), 0, UserRole.USER, auth_at=0)
    expired = encode_token(
        claims, TokenType.ACCESS, TEST_JWT_SECRET, timedelta(minutes=-1)
    )
    response = await api.get(
        "/api/v1/me", headers={"cookie": f"access_token={expired}"}
    )
    assert (response.status_code, _error_code(response)) == (401, "token_expired")


async def test_refresh_issues_a_new_pair(api: AsyncClient) -> None:
    await api.post(f"{AUTH}/register", json=CREDENTIALS)
    response = await api.post(f"{AUTH}/refresh")
    assert response.status_code == 200 and response.json()["email"] == EMAIL
    assert _cookie(response, "access_token") and _cookie(response, "refresh_token")


async def test_refresh_without_a_cookie_is_not_authenticated(api: AsyncClient) -> None:
    response = await api.post(f"{AUTH}/refresh")
    assert (response.status_code, _error_code(response)) == (401, "not_authenticated")


async def test_logout_all_revokes_refresh_tokens_already_issued(
    api: AsyncClient,
) -> None:
    registered = await api.post(f"{AUTH}/register", json=CREDENTIALS)
    old_refresh = registered.cookies["refresh_token"]
    assert (await api.post(f"{AUTH}/logout-all")).status_code == 204
    response = await api.post(
        f"{AUTH}/refresh", headers={"cookie": f"refresh_token={old_refresh}"}
    )
    assert (response.status_code, _error_code(response)) == (401, "not_authenticated")


async def test_a_disabled_user_cannot_refresh(
    api: AsyncClient, seeded_session: AsyncSession
) -> None:
    await api.post(f"{AUTH}/register", json=CREDENTIALS)
    user = await UserRepository(seeded_session).get_by_email(EMAIL)
    assert user is not None
    user.is_active = False
    await seeded_session.flush()
    response = await api.post(f"{AUTH}/refresh")
    assert (response.status_code, _error_code(response)) == (403, "account_disabled")


async def test_changing_the_password_keeps_this_device_logged_in(
    api: AsyncClient,
) -> None:
    await api.post(f"{AUTH}/register", json=CREDENTIALS)
    change = {"current": PASSWORD, "new": "a brand new password"}
    assert (await api.post(f"{AUTH}/password", json=change)).status_code == 204
    assert (await api.get("/api/v1/me")).status_code == 200
    api.cookies.clear()
    assert (await api.post(f"{AUTH}/login", json=CREDENTIALS)).status_code == 401
    renewed = {"email": EMAIL, "password": "a brand new password"}
    assert (await api.post(f"{AUTH}/login", json=renewed)).status_code == 200


async def test_a_wrong_current_password_changes_nothing(api: AsyncClient) -> None:
    await api.post(f"{AUTH}/register", json=CREDENTIALS)
    change = {"current": "not my password", "new": "a brand new password"}
    response = await api.post(f"{AUTH}/password", json=change)
    assert (response.status_code, _error_code(response)) == (401, "invalid_credentials")


async def test_password_and_logout_all_need_a_session(api: AsyncClient) -> None:
    change = {"current": PASSWORD, "new": "a brand new password"}
    for response in (
        await api.post(f"{AUTH}/password", json=change),
        await api.post(f"{AUTH}/logout-all"),
    ):
        assert (response.status_code, _error_code(response)) == (
            401,
            "not_authenticated",
        )


async def test_reauth_restores_a_stale_admin_window(api: AsyncClient) -> None:
    """A token whose auth_at is old must be refused by admin routes, and /auth/reauth
    must restore access without the user logging out."""
    await api.post(f"{AUTH}/register", json=CREDENTIALS)
    stale = encode_token(
        TokenClaims(uuid.UUID(int=1), 0, UserRole.ADMIN, auth_at=0),
        TokenType.ACCESS,
        TEST_JWT_SECRET,
        timedelta(minutes=5),
    )
    refused = await api.get(
        "/api/v1/admin/stats", headers={"cookie": f"access_token={stale}"}
    )
    assert (refused.status_code, _error_code(refused)) == (403, "admin_reauth_required")

    accepted = await api.post(f"{AUTH}/reauth", json={"password": PASSWORD})
    assert accepted.status_code == 200
    assert _cookie(accepted, "access_token")


async def test_reauth_rejects_the_wrong_password(api: AsyncClient) -> None:
    await api.post(f"{AUTH}/register", json=CREDENTIALS)
    response = await api.post(f"{AUTH}/reauth", json={"password": "not my password"})
    assert (response.status_code, _error_code(response)) == (401, "invalid_credentials")


async def test_reauth_needs_a_session(api: AsyncClient) -> None:
    response = await api.post(f"{AUTH}/reauth", json={"password": PASSWORD})
    assert (response.status_code, _error_code(response)) == (401, "not_authenticated")
