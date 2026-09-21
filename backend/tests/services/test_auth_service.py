import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from core.security import (
    TokenClaims,
    decode_token,
    encode_token,
    hash_password,
    verify_password,
)
from enums import TokenType, UserRole
from errors import (
    AccountDisabledError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    NotAuthenticatedError,
    PermissionDeniedError,
)
from models.user import User
from repositories.user_repository import UserRepository
from schemas.auth import LoginRequest, PasswordChange, ReauthRequest, UserCreate
from services import auth_service
from services.auth_service import AuthService
from tests.support import TEST_JWT_SECRET, TEST_SCRYPT_N, fast_auth_settings

EMAIL = "driver@example.com"
PASSWORD = "correct horse"


def _user(**overrides: object) -> User:
    values: dict[str, object] = {
        "id": uuid.UUID(int=42),
        "email": EMAIL,
        "password_hash": hash_password(PASSWORD, TEST_SCRYPT_N),
        "role": UserRole.USER,
        "is_active": True,
        "token_version": 0,
        "created_at": datetime.now(UTC),
    }
    return User(**(values | overrides))


def _service(users: AsyncMock) -> AuthService:
    return AuthService(users, fast_auth_settings())


def _users(**returns: object) -> AsyncMock:
    users = AsyncMock(spec=UserRepository)
    for method, value in returns.items():
        getattr(users, method).return_value = value
    return users


def _refresh_token(
    user: User, lifetime: timedelta = timedelta(days=1), auth_at: int = 1
) -> str:
    claims = TokenClaims(user.id, user.token_version, None, auth_at)
    return encode_token(claims, TokenType.REFRESH, TEST_JWT_SECRET, lifetime)


async def test_register_hashes_the_password_and_issues_tokens() -> None:
    users = _users(create_if_absent=_user())
    result = await _service(users).register(UserCreate(email=EMAIL, password=PASSWORD))
    email, stored_hash, role = users.create_if_absent.call_args.args
    assert (email, role) == (EMAIL, UserRole.USER)
    assert stored_hash != PASSWORD and verify_password(PASSWORD, stored_hash)
    claims = decode_token(result.tokens.access, TEST_JWT_SECRET, TokenType.ACCESS)
    assert (claims.user_id, claims.token_version, claims.role) == (
        uuid.UUID(int=42),
        0,
        UserRole.USER,
    )
    assert claims.auth_at > 0
    assert result.user.email == EMAIL


async def test_register_with_a_taken_email_raises() -> None:
    users = _users(create_if_absent=None)
    with pytest.raises(EmailAlreadyRegisteredError):
        await _service(users).register(UserCreate(email=EMAIL, password=PASSWORD))


async def test_authenticate_returns_tokens_and_records_the_login() -> None:
    user = _user()
    users = _users(get_by_email=user)
    result = await _service(users).authenticate(
        LoginRequest(email=EMAIL, password=PASSWORD)
    )
    users.record_login.assert_awaited_once_with(user)
    assert decode_token(result.tokens.refresh, TEST_JWT_SECRET, TokenType.REFRESH)


async def test_unknown_email_and_wrong_password_fail_identically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify = Mock(return_value=False)
    monkeypatch.setattr(auth_service, "verify_password", verify)
    for users in (_users(get_by_email=None), _users(get_by_email=_user())):
        with pytest.raises(InvalidCredentialsError) as raised:
            await _service(users).authenticate(
                LoginRequest(email=EMAIL, password="a wrong password")
            )
        assert raised.value.message == "Invalid email or password"
        users.record_login.assert_not_awaited()
    # The hasher ran for the unknown email too: both paths cost the same.
    assert verify.call_count == 2


async def test_a_disabled_user_cannot_log_in() -> None:
    users = _users(get_by_email=_user(is_active=False))
    with pytest.raises(AccountDisabledError):
        await _service(users).authenticate(LoginRequest(email=EMAIL, password=PASSWORD))


async def test_refresh_issues_a_new_pair_for_a_current_token() -> None:
    user = _user(token_version=2)
    result = await _service(_users(get_by_id=user)).refresh(_refresh_token(user))
    claims = decode_token(result.tokens.access, TEST_JWT_SECRET, TokenType.ACCESS)
    assert claims.token_version == 2


async def test_refresh_rejects_a_missing_stale_expired_or_wrong_type_token() -> None:
    user = _user(token_version=1)
    stale = _refresh_token(_user(token_version=0))
    expired = _refresh_token(user, timedelta(minutes=-1))
    access = encode_token(
        TokenClaims(user.id, 1, UserRole.USER, auth_at=1),
        TokenType.ACCESS,
        TEST_JWT_SECRET,
        timedelta(minutes=1),
    )
    service = _service(_users(get_by_id=user))
    for token in (None, stale, expired, access, "garbage"):
        with pytest.raises(NotAuthenticatedError):
            await service.refresh(token)


async def test_refresh_rejects_a_deleted_or_disabled_user() -> None:
    user = _user()
    with pytest.raises(NotAuthenticatedError):
        await _service(_users(get_by_id=None)).refresh(_refresh_token(user))
    disabled = _user(is_active=False)
    with pytest.raises(AccountDisabledError):
        await _service(_users(get_by_id=disabled)).refresh(_refresh_token(disabled))


async def test_change_password_verifies_the_current_one_and_revokes_tokens() -> None:
    user = _user()
    users = _users(get_by_id=user)
    change = PasswordChange(current=PASSWORD, new="a brand new password")
    await _service(users).change_password(user.id, change)
    replaced_user, new_hash = users.replace_password.call_args.args
    assert replaced_user is user
    assert verify_password("a brand new password", new_hash)


async def test_change_password_with_a_wrong_current_password_raises() -> None:
    users = _users(get_by_id=_user())
    change = PasswordChange(current="not my password", new="a brand new password")
    with pytest.raises(InvalidCredentialsError):
        await _service(users).change_password(uuid.UUID(int=42), change)
    users.replace_password.assert_not_awaited()


async def test_logout_all_bumps_the_token_version() -> None:
    user = _user()
    users = _users(get_by_id=user)
    await _service(users).logout_all(user.id)
    users.bump_token_version.assert_awaited_once_with(user)


async def test_get_user_raises_when_the_account_is_gone() -> None:
    with pytest.raises(NotAuthenticatedError):
        await _service(_users(get_by_id=None)).get_user(uuid.UUID(int=42))


async def test_get_user_raises_when_the_account_is_disabled() -> None:
    users = _users(get_by_id=_user(is_active=False))
    with pytest.raises(AccountDisabledError):
        await _service(users).get_user(uuid.UUID(int=42))


async def test_change_password_raises_when_the_account_is_disabled() -> None:
    users = _users(get_by_id=_user(is_active=False))
    change = PasswordChange(current=PASSWORD, new="a brand new password")
    with pytest.raises(AccountDisabledError):
        await _service(users).change_password(uuid.UUID(int=42), change)
    users.replace_password.assert_not_awaited()


async def test_require_admin_checks_role_and_activity_against_the_database() -> None:
    admin = _user(role=UserRole.ADMIN)
    assert (await _service(_users(get_by_id=admin)).require_admin(admin.id)).role is (
        UserRole.ADMIN
    )
    with pytest.raises(PermissionDeniedError):
        await _service(_users(get_by_id=_user())).require_admin(uuid.UUID(int=42))
    disabled_admin = _user(role=UserRole.ADMIN, is_active=False)
    with pytest.raises(AccountDisabledError):
        await _service(_users(get_by_id=disabled_admin)).require_admin(admin.id)


async def test_ensure_admin_creates_the_account_when_absent() -> None:
    users = _users(get_by_email=None, create_if_absent=_user(role=UserRole.ADMIN))
    assert await _service(users).ensure_admin(" Admin@Example.com ", PASSWORD) is True
    email, stored_hash, role = users.create_if_absent.call_args.args
    assert (email, role) == ("admin@example.com", UserRole.ADMIN)
    assert verify_password(PASSWORD, stored_hash)


async def test_ensure_admin_leaves_an_existing_account_alone() -> None:
    users = _users(get_by_email=_user())
    assert await _service(users).ensure_admin(EMAIL, "another password") is False
    users.create_if_absent.assert_not_awaited()
    users.replace_password.assert_not_awaited()


@pytest.mark.parametrize(("email", "password"), [("", PASSWORD), (EMAIL, "")])
async def test_ensure_admin_skips_when_a_variable_is_empty(
    email: str, password: str
) -> None:
    users = _users()
    assert await _service(users).ensure_admin(email, password) is False
    users.get_by_email.assert_not_awaited()


async def test_ensure_admin_fails_loudly_on_a_weak_password() -> None:
    with pytest.raises(ValidationError):
        await _service(_users(get_by_email=None)).ensure_admin(EMAIL, "short")


async def test_login_stamps_auth_at_and_refresh_preserves_it() -> None:
    user = _user()
    service = _service(_users(get_by_email=user, get_by_id=user))
    logged_in = await service.authenticate(LoginRequest(email=EMAIL, password=PASSWORD))
    stamped = decode_token(logged_in.tokens.access, TEST_JWT_SECRET, TokenType.ACCESS)
    assert stamped.auth_at > 0

    refreshed = await service.refresh(logged_in.tokens.refresh)
    carried = decode_token(refreshed.tokens.access, TEST_JWT_SECRET, TokenType.ACCESS)
    assert carried.auth_at == stamped.auth_at  # a refresh must NOT renew freshness


async def test_reauth_restamps_without_logging_other_devices_out() -> None:
    user = _user()
    users = _users(get_by_id=user)
    old = TokenClaims(user.id, user.token_version, user.role, auth_at=1)
    result = await _service(users).reauth(user.id, ReauthRequest(password=PASSWORD))
    fresh = decode_token(result.tokens.access, TEST_JWT_SECRET, TokenType.ACCESS)
    assert fresh.auth_at > old.auth_at
    users.bump_token_version.assert_not_awaited()  # other sessions survive


async def test_reauth_with_the_wrong_password_is_rejected() -> None:
    users = _users(get_by_id=_user())
    with pytest.raises(InvalidCredentialsError):
        await _service(users).reauth(uuid.UUID(int=42), ReauthRequest(password="wrong"))


async def test_reauth_refuses_a_disabled_account() -> None:
    users = _users(get_by_id=_user(is_active=False))
    payload = ReauthRequest(password=PASSWORD)
    with pytest.raises(AccountDisabledError):
        await _service(users).reauth(uuid.UUID(int=42), payload)


async def test_changing_the_password_restamps_auth_at() -> None:
    user = _user()
    service = _service(_users(get_by_id=user))
    change = PasswordChange(current=PASSWORD, new="a brand new password")
    result = await service.change_password(user.id, change)
    claims = decode_token(result.tokens.access, TEST_JWT_SECRET, TokenType.ACCESS)
    assert claims.auth_at > 0  # they just proved they know the password
