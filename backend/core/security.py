"""Password hashing and token encoding — pure functions, no I/O (spec 4 §4)."""

import base64
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from enums import TokenType, UserRole
from errors import NotAuthenticatedError, TokenExpiredError

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"

_SCHEME = "scrypt"
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32
_SCRYPT_BLOCK_BYTES = 128
_ALGORITHM = "HS256"
_REQUIRED_CLAIMS = ["sub", "ver", "typ", "exp"]


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    token_version: int
    role: UserRole | None


@dataclass(frozen=True)
class TokenPair:
    access: str
    refresh: str


def _derive_key(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    # OpenSSL refuses scrypt above 32 MiB unless told otherwise; n=2**17, r=8 needs
    # 128 MiB, so the limit is sized from the parameters with headroom.
    max_memory = _SCRYPT_BLOCK_BYTES * n * r * 2
    return hashlib.scrypt(
        password.encode(), salt=salt, n=n, r=r, p=p, dklen=_KEY_BYTES, maxmem=max_memory
    )


def hash_password(password: str, n: int) -> str:
    """`scrypt$n$r$p$salt$key` — the cost travels with the hash, so it can be raised
    later without invalidating stored passwords."""
    salt = secrets.token_bytes(_SALT_BYTES)
    key = _derive_key(password, salt, n, _SCRYPT_R, _SCRYPT_P)
    encoded = [base64.b64encode(part).decode() for part in (salt, key)]
    return "$".join([_SCHEME, str(n), str(_SCRYPT_R), str(_SCRYPT_P), *encoded])


def verify_password(password: str, stored: str) -> bool:
    scheme, n, r, p, salt, key = stored.split("$")
    if scheme != _SCHEME:
        raise ValueError(f"Unsupported password hash scheme: {scheme}")
    derived = _derive_key(password, base64.b64decode(salt), int(n), int(r), int(p))
    return hmac.compare_digest(derived, base64.b64decode(key))


def encode_token(
    claims: TokenClaims, token_type: TokenType, secret: str, lifetime: timedelta
) -> str:
    payload: dict[str, Any] = {
        "sub": str(claims.user_id),
        "ver": claims.token_version,
        "typ": token_type.value,
        "exp": datetime.now(UTC) + lifetime,
    }
    if claims.role is not None:
        payload["role"] = claims.role.value
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_token(token: str, secret: str, expected_type: TokenType) -> TokenClaims:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[_ALGORITHM],  # pinned: blocks `alg: none` and confusion attacks
            options={"require": _REQUIRED_CLAIMS},
        )
    except jwt.ExpiredSignatureError as error:
        raise TokenExpiredError() from error
    except jwt.InvalidTokenError as error:
        raise NotAuthenticatedError() from error
    if payload["typ"] != expected_type.value:
        raise NotAuthenticatedError()
    return _claims_from(payload)


def _claims_from(payload: dict[str, Any]) -> TokenClaims:
    role = payload.get("role")
    try:
        return TokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            token_version=int(payload["ver"]),
            role=UserRole(role) if role is not None else None,
        )
    except (TypeError, ValueError) as error:  # a signed token with malformed claims
        raise NotAuthenticatedError() from error


def issue_token_pair(
    claims: TokenClaims,
    secret: str,
    access_lifetime: timedelta,
    refresh_lifetime: timedelta,
) -> TokenPair:
    roleless = replace(claims, role=None)
    return TokenPair(
        access=encode_token(claims, TokenType.ACCESS, secret, access_lifetime),
        refresh=encode_token(roleless, TokenType.REFRESH, secret, refresh_lifetime),
    )
