"""Accounts: sign-up, login, token refresh, password change, admin bootstrap."""

import asyncio
import logging
import secrets
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache

from core.config import Settings
from core.security import (
    TokenClaims,
    TokenPair,
    decode_token,
    hash_password,
    issue_token_pair,
    verify_password,
)
from enums import TokenType, UserRole
from errors import (
    AccountDisabledError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    NotAuthenticatedError,
    PermissionDeniedError,
    TokenExpiredError,
)
from models.user import User
from repositories.user_repository import UserRepository
from schemas.auth import LoginRequest, PasswordChange, UserCreate, UserRead

logger = logging.getLogger(__name__)

# ponytail: two hashes at a time. Each holds 128 MiB at n=2**17, so an unbounded pool
# would let a login burst exhaust the container. Raise max_workers along with RAM.
_HASH_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="scrypt")


async def _in_hash_pool[T](function: Callable[..., T], *args: object) -> T:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_HASH_POOL, function, *args)


@lru_cache
def _dummy_hash(n: int) -> str:
    """Verified against when the email is unknown, so that path costs exactly what a
    wrong password costs and timing does not reveal which accounts exist."""
    return hash_password(secrets.token_urlsafe(16), n)


@dataclass(frozen=True)
class AuthResult:
    user: UserRead
    tokens: TokenPair


class AuthService:
    def __init__(self, users: UserRepository, settings: Settings) -> None:
        self._users = users
        self._settings = settings

    async def register(self, payload: UserCreate) -> AuthResult:
        password_hash = await self._hash(payload.password.get_secret_value())
        user = await self._users.create_if_absent(
            payload.email, password_hash, UserRole.USER
        )
        if user is None:
            raise EmailAlreadyRegisteredError()
        return self._issue(user)

    async def authenticate(self, payload: LoginRequest) -> AuthResult:
        user = await self._users.get_by_email(payload.email)
        stored = (
            user.password_hash
            if user is not None
            else await _in_hash_pool(_dummy_hash, self._settings.scrypt_n)
        )
        password = payload.password.get_secret_value()
        matches = await _in_hash_pool(verify_password, password, stored)
        if user is None or not matches:
            raise InvalidCredentialsError()
        if not user.is_active:
            raise AccountDisabledError()
        await self._users.record_login(user)
        return self._issue(user)

    async def refresh(self, refresh_token: str | None) -> AuthResult:
        if refresh_token is None:
            raise NotAuthenticatedError()
        try:
            claims = decode_token(refresh_token, self._secret, TokenType.REFRESH)
        except TokenExpiredError as error:
            # `token_expired` tells the client to refresh; here there is nothing left to
            # refresh with, so the session is simply over.
            raise NotAuthenticatedError() from error
        user = await self._users.get_by_id(claims.user_id)
        if user is None or user.token_version != claims.token_version:
            raise NotAuthenticatedError()
        if not user.is_active:
            raise AccountDisabledError()
        return self._issue(user)

    async def change_password(
        self, user_id: uuid.UUID, payload: PasswordChange
    ) -> AuthResult:
        user = await self._load(user_id)
        current = payload.current.get_secret_value()
        if not await _in_hash_pool(verify_password, current, user.password_hash):
            raise InvalidCredentialsError()
        new_hash = await self._hash(payload.new.get_secret_value())
        await self._users.replace_password(user, new_hash)
        return self._issue(user)  # a fresh pair, so this device stays logged in

    async def logout_all(self, user_id: uuid.UUID) -> None:
        await self._users.bump_token_version(await self._load(user_id))

    async def get_user(self, user_id: uuid.UUID) -> UserRead:
        return UserRead.model_validate(await self._load(user_id))

    async def require_admin(self, user_id: uuid.UUID) -> UserRead:
        """Always reads the database, never the token, so disabling or demoting an
        admin takes effect on their very next request."""
        user = await self._load(user_id)
        if not user.is_active:
            raise AccountDisabledError()
        if user.role is not UserRole.ADMIN:
            raise PermissionDeniedError()
        return UserRead.model_validate(user)

    async def ensure_admin(self, email: str, password: str) -> bool:
        if not email or not password:
            logger.info("admin bootstrap skipped: ADMIN_EMAIL or ADMIN_PASSWORD empty")
            return False
        account = UserCreate(email=email, password=password)  # sign-up rules apply
        if await self._users.get_by_email(account.email) is not None:
            logger.info("admin bootstrap: account already exists, left untouched")
            return False
        password_hash = await self._hash(account.password.get_secret_value())
        created = await self._users.create_if_absent(
            account.email, password_hash, UserRole.ADMIN
        )
        logger.info("admin bootstrap: %s", "created" if created else "lost the race")
        return created is not None

    @property
    def _secret(self) -> str:
        return self._settings.jwt_secret.get_secret_value()

    async def _hash(self, password: str) -> str:
        return await _in_hash_pool(hash_password, password, self._settings.scrypt_n)

    async def _load(self, user_id: uuid.UUID) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotAuthenticatedError()
        return user

    def _issue(self, user: User) -> AuthResult:
        claims = TokenClaims(user.id, user.token_version, user.role)
        tokens = issue_token_pair(
            claims,
            self._secret,
            timedelta(minutes=self._settings.access_token_minutes),
            timedelta(days=self._settings.refresh_token_days),
        )
        return AuthResult(UserRead.model_validate(user), tokens)
