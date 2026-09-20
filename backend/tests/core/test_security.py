import uuid
from datetime import timedelta

import jwt
import pytest

from core.security import (
    TokenClaims,
    decode_token,
    encode_token,
    hash_password,
    issue_token_pair,
    verify_password,
)
from enums import TokenType, UserRole
from errors import NotAuthenticatedError, TokenExpiredError

FAST_N = 2**4
SECRET = "s" * 32
CLAIMS = TokenClaims(user_id=uuid.UUID(int=1), token_version=3, role=UserRole.ADMIN)
ONE_MINUTE = timedelta(minutes=1)


def test_a_hash_verifies_its_own_password_only() -> None:
    stored = hash_password("correct horse", FAST_N)
    assert verify_password("correct horse", stored)
    assert not verify_password("wrong horse", stored)


def test_two_hashes_of_one_password_differ() -> None:
    assert hash_password("same", FAST_N) != hash_password("same", FAST_N)


def test_the_stored_cost_is_used_so_old_hashes_survive_a_cost_bump() -> None:
    old = hash_password("kept", FAST_N)
    assert old.startswith(f"scrypt${FAST_N}$8$1$")
    assert verify_password("kept", old)  # no `n` argument: read from the hash


def test_production_cost_fits_the_memory_limit() -> None:
    assert verify_password("big", hash_password("big", 2**17))


def test_an_unknown_scheme_fails_loudly() -> None:
    with pytest.raises(ValueError, match="scheme"):
        verify_password("x", "bcrypt$1$2$3$c2FsdA==$a2V5")


def test_a_token_round_trips() -> None:
    token = encode_token(CLAIMS, TokenType.ACCESS, SECRET, ONE_MINUTE)
    assert decode_token(token, SECRET, TokenType.ACCESS) == CLAIMS


def test_an_expired_token_raises_token_expired() -> None:
    token = encode_token(CLAIMS, TokenType.ACCESS, SECRET, -ONE_MINUTE)
    with pytest.raises(TokenExpiredError):
        decode_token(token, SECRET, TokenType.ACCESS)


def test_a_tampered_token_is_not_authenticated() -> None:
    token = encode_token(CLAIMS, TokenType.ACCESS, SECRET, ONE_MINUTE)
    with pytest.raises(NotAuthenticatedError):
        decode_token(token, "another-secret-" + "x" * 32, TokenType.ACCESS)
    with pytest.raises(NotAuthenticatedError):
        decode_token("not-a-jwt", SECRET, TokenType.ACCESS)


def test_an_unsigned_token_is_rejected() -> None:
    payload = {"sub": str(CLAIMS.user_id), "ver": 3, "typ": "access", "exp": 9999999999}
    unsigned = jwt.encode(payload, key=None, algorithm="none")
    with pytest.raises(NotAuthenticatedError):
        decode_token(unsigned, SECRET, TokenType.ACCESS)


def test_a_signed_token_with_malformed_claims_is_not_authenticated() -> None:
    for sub, ver in (("not-a-uuid", 0), (str(CLAIMS.user_id), ["not", "a", "number"])):
        payload = {"sub": sub, "ver": ver, "typ": "access", "exp": 9999999999}
        forged = jwt.encode(payload, SECRET, algorithm="HS256")
        with pytest.raises(NotAuthenticatedError):
            decode_token(forged, SECRET, TokenType.ACCESS)


def test_token_types_are_not_interchangeable() -> None:
    pair = issue_token_pair(CLAIMS, SECRET, ONE_MINUTE, ONE_MINUTE)
    with pytest.raises(NotAuthenticatedError):
        decode_token(pair.refresh, SECRET, TokenType.ACCESS)
    with pytest.raises(NotAuthenticatedError):
        decode_token(pair.access, SECRET, TokenType.REFRESH)


def test_the_refresh_token_carries_no_role() -> None:
    pair = issue_token_pair(CLAIMS, SECRET, ONE_MINUTE, ONE_MINUTE)
    assert decode_token(pair.access, SECRET, TokenType.ACCESS).role is UserRole.ADMIN
    assert decode_token(pair.refresh, SECRET, TokenType.REFRESH).role is None
