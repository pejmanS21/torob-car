import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from errors import (
    AccountDisabledError,
    AdminReauthRequiredError,
    AdminUserNotFoundError,
    AlertNotFoundError,
    AppError,
    CannotModifySelfError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    LastAdminError,
    ListingNotFoundError,
    NotAuthenticatedError,
    PermissionDeniedError,
    TokenExpiredError,
    register_exception_handlers,
)
from schemas.auth import UserCreate


def _failing_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/missing")
    async def missing() -> None:
        raise ListingNotFoundError(uuid.UUID(int=7))

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret detail")

    @app.get("/typed/{number}")
    async def typed(number: int) -> int:
        return number

    @app.post("/register")
    async def register(body: UserCreate) -> None:
        return None

    return app


async def _get(path: str) -> tuple[int, dict]:
    transport = ASGITransport(app=_failing_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        response = await http.get(path)
    return response.status_code, response.json()


async def _post(path: str, json: dict) -> tuple[int, dict]:
    transport = ASGITransport(app=_failing_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        response = await http.post(path, json=json)
    return response.status_code, response.json()


async def test_app_error_becomes_structured_envelope() -> None:
    status, body = await _get("/missing")
    assert status == 404
    assert body["error"]["code"] == "listing_not_found"
    assert body["error"]["details"] == {"listing_id": str(uuid.UUID(int=7))}


async def test_unhandled_error_is_generic_and_leaks_nothing() -> None:
    status, body = await _get("/boom")
    assert status == 500
    assert body["error"]["code"] == "internal_error"
    assert "secret detail" not in str(body)


async def test_validation_error_uses_the_same_envelope() -> None:
    status, body = await _get("/typed/not-a-number")
    assert status == 422
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"], list)


async def test_unknown_route_uses_the_same_envelope() -> None:
    status, body = await _get("/nope")
    assert status == 404
    assert body["error"]["code"] == "http_error"


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (InvalidCredentialsError(), 401, "invalid_credentials"),
        (NotAuthenticatedError(), 401, "not_authenticated"),
        (TokenExpiredError(), 401, "token_expired"),
        (AccountDisabledError(), 403, "account_disabled"),
        (PermissionDeniedError(), 403, "permission_denied"),
        (EmailAlreadyRegisteredError(), 409, "email_taken"),
        (AlertNotFoundError(uuid.UUID(int=9)), 404, "alert_not_found"),
        (AdminReauthRequiredError(), 403, "admin_reauth_required"),
        (CannotModifySelfError(), 409, "cannot_modify_self"),
        (LastAdminError(), 409, "last_admin"),
        (AdminUserNotFoundError(uuid.UUID(int=1)), 404, "admin_user_not_found"),
    ],
)
def test_auth_errors_carry_their_status_and_code(
    error: AppError, status_code: int, code: str
) -> None:
    assert (error.status_code, error.code) == (status_code, code)


def test_email_taken_never_echoes_the_address() -> None:
    assert EmailAlreadyRegisteredError().context == {}


async def test_422_never_echoes_the_plaintext_password() -> None:
    status, body = await _post(
        "/register",
        {"email": "reviewer@example.com", "password": "sekret1"},
    )
    assert status == 422
    assert body["error"]["code"] == "validation_error"
    assert "sekret1" not in str(body)
    details = body["error"]["details"]
    assert any(entry["loc"][-1] == "password" for entry in details)
    assert all("input" not in entry for entry in details)
