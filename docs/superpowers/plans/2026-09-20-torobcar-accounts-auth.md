# Accounts and Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the frontend's fake login with real email + password accounts, move saved listings and price alerts server-side, and create an admin account at startup.

**Architecture:** Stateless HS256 JWTs in two `HttpOnly` cookies (15-minute access token, 30-day refresh token); revocation by a `users.token_version` counter checked at refresh. The backend follows the existing endpoint → service → repository → model layering. The frontend keeps Server Components anonymous and loads all account data client-side through the typed API client, which silently refreshes on `token_expired`.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic, PyJWT (new), stdlib `hashlib.scrypt`; Next.js 16 App Router, TypeScript strict, Bun test.

**Spec:** `docs/superpowers/specs/2026-09-20-torobcar-accounts-auth-design.md` — read it before starting any task.

## Global Constraints

- Branch: `feat/accounts-auth`. Never commit to `main`.
- The working tree has unrelated untracked directories (`brag-output/`, `prototype/`, `graphify-out/`, `output/`, …). **Never `git add -A` or `git add .`** — stage only the paths each task names.
- Backend commands run from `backend/`; frontend commands from `frontend/`. Use `uv` and `bun` only — never `pip`, `npm`, `yarn`, `pnpm`. Never hand-edit `uv.lock` or `bun.lock`.
- DB-backed tests need the throwaway Postgres: run `./.scripts/test-db.sh` once from the repo root. Mark DB test modules with `pytestmark = pytest.mark.db`.
- Every Python function is fully type-hinted; functions stay ≤ ~30 lines; no business logic in endpoints; no SQLAlchemy outside `repositories/`; config is read only through `core/config.py`.
- Before each backend commit: `uv run ruff check . --fix && uv run black .` must be clean. Before each frontend commit: `bun run lint && bunx tsc --noEmit` must be clean.
- Exact values from the spec: access token `exp` 15 minutes; refresh token `exp` 30 days; **both cookies' `Max-Age` = 30 days**; cookies `HttpOnly; SameSite=Lax`, `Secure` when `ENV != development`; refresh cookie `Path=/api/v1/auth`; scrypt `n=2**17, r=8, p=1`, 16-byte salt; password length 8–128; import limits 500 saved ids and 50 alerts.
- Error codes (frontend branches on these, never on message text): `invalid_credentials`, `not_authenticated`, `token_expired`, `account_disabled`, `permission_denied`, `email_taken`, `alert_not_found`.
- Test emails use `@example.com` (pydantic's `EmailStr` rejects `.test` domains).
- Tests never hash at production cost: use `fast_auth_settings()` from `tests/support.py` (`scrypt_n=2**4`).
- Deliberate simplifications get a `# ponytail:` comment naming the ceiling and the upgrade path.
- Commit messages are conventional commits and end with:
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`

## File Structure

**Backend — created**

| File | Responsibility |
|---|---|
| `backend/core/security.py` | Pure functions: scrypt hash/verify, JWT encode/decode, cookie name constants |
| `backend/models/user.py`, `saved_listing.py`, `price_alert.py` | ORM tables |
| `backend/db/migrations/versions/0003_accounts.py` | Creates the three tables |
| `backend/repositories/user_repository.py`, `saved_listing_repository.py`, `price_alert_repository.py` | All queries for their table |
| `backend/schemas/auth.py`, `schemas/account.py` | Transport models |
| `backend/services/auth_service.py` | Register, authenticate, refresh, change password, logout-all, `require_admin`, `ensure_admin` |
| `backend/services/account_service.py` | Saved listings, alerts, import |
| `backend/api/v1/endpoints/auth.py`, `me.py` | Thin controllers; `auth.py` owns the cookie helpers |

**Backend — modified:** `enums.py`, `errors.py`, `core/config.py`, `models/__init__.py`, `dependencies/providers.py`, `api/v1/router.py`, `main.py`, `pyproject.toml` (via `uv add`), `tests/support.py`, `tests/conftest.py`.

**Frontend — created:** `src/lib/account.ts` (+ test), `src/components/AuthDialog.tsx` (+ CSS module).
**Frontend — modified:** `src/lib/api/client.ts` (+ test), `src/lib/api/types.ts`, `src/lib/types.ts`, `src/state/AppState.tsx`, `src/components/Header.tsx` (+ CSS), `src/components/AlertsDropdown.tsx`, `src/app/layout.tsx`.

**Infra/docs — modified:** `example.env`, `.scripts/setup.sh`, `.scripts/smoke.sh`, `.docker/compose.yml`, `CLAUDE.md`.

---

### Task 1: Settings, enums and errors

**Files:**
- Modify: `backend/core/config.py`, `backend/enums.py`, `backend/errors.py`, `example.env`, `.scripts/setup.sh`, `backend/tests/support.py`
- Test: `backend/tests/core/test_config.py`, `backend/tests/test_errors.py`

**Interfaces:**
- Produces: `Settings.jwt_secret: SecretStr`, `.access_token_minutes: int`, `.refresh_token_days: int`, `.scrypt_n: int`, `.admin_email: str`, `.admin_password: SecretStr`; `enums.UserRole` (`USER`, `ADMIN`), `enums.TokenType` (`ACCESS`, `REFRESH`); errors `InvalidCredentialsError()`, `NotAuthenticatedError()`, `TokenExpiredError()`, `AccountDisabledError()`, `PermissionDeniedError()`, `EmailAlreadyRegisteredError()`, `AlertNotFoundError(alert_id: uuid.UUID)`; `tests.support.fast_auth_settings() -> Settings`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/core/test_config.py`:

```python
import pytest
from pydantic import ValidationError


def test_empty_jwt_secret_is_rejected_outside_development() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, env="production", jwt_secret="")


def test_short_jwt_secret_is_rejected() -> None:
    with pytest.raises(ValidationError, match="32 bytes"):
        Settings(_env_file=None, env="production", jwt_secret="too-short")


def test_empty_jwt_secret_in_development_becomes_a_random_secret() -> None:
    first = Settings(_env_file=None, env="development", jwt_secret="")
    second = Settings(_env_file=None, env="development", jwt_secret="")
    assert len(first.jwt_secret.get_secret_value()) >= 32
    assert first.jwt_secret.get_secret_value() != second.jwt_secret.get_secret_value()


def test_auth_defaults_match_the_spec() -> None:
    settings = Settings(_env_file=None, env="development")
    assert settings.access_token_minutes == 15
    assert settings.refresh_token_days == 30
    assert settings.scrypt_n == 2**17
    assert settings.admin_email == ""
    assert settings.admin_password.get_secret_value() == ""
```

Move the two new `import` lines to the top of the file with the existing imports.

Append to `backend/tests/test_errors.py`:

```python
import pytest

from errors import (
    AccountDisabledError,
    AlertNotFoundError,
    AppError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    NotAuthenticatedError,
    PermissionDeniedError,
    TokenExpiredError,
)


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
    ],
)
def test_auth_errors_carry_their_status_and_code(
    error: AppError, status_code: int, code: str
) -> None:
    assert (error.status_code, error.code) == (status_code, code)


def test_email_taken_never_echoes_the_address() -> None:
    assert EmailAlreadyRegisteredError().context == {}
```

Merge the imports into the file's existing import block (`uuid` is already imported there).

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `backend/`): `uv run pytest tests/core/test_config.py tests/test_errors.py -q`
Expected: FAIL — `ImportError: cannot import name 'AccountDisabledError'` and `ValidationError` not raised / unexpected keyword behaviour for `jwt_secret`.

- [ ] **Step 3: Add the enums**

Append to `backend/enums.py`:

```python
class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
```

- [ ] **Step 4: Add the errors**

In `backend/errors.py`, after `IngestError`:

```python
class InvalidCredentialsError(AppError):
    status_code = 401
    code = "invalid_credentials"

    def __init__(self) -> None:
        # One message for "no such user" and "wrong password": never say which.
        super().__init__("Invalid email or password")


class NotAuthenticatedError(AppError):
    status_code = 401
    code = "not_authenticated"

    def __init__(self) -> None:
        super().__init__("Not authenticated")


class TokenExpiredError(AppError):
    status_code = 401
    code = "token_expired"

    def __init__(self) -> None:
        super().__init__("Token expired")


class AccountDisabledError(AppError):
    status_code = 403
    code = "account_disabled"

    def __init__(self) -> None:
        super().__init__("Account disabled")


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"

    def __init__(self) -> None:
        super().__init__("Permission denied")


class EmailAlreadyRegisteredError(AppError):
    status_code = 409
    code = "email_taken"

    def __init__(self) -> None:
        super().__init__("Email already registered")


class AlertNotFoundError(AppError):
    status_code = 404
    code = "alert_not_found"

    def __init__(self, alert_id: uuid.UUID) -> None:
        super().__init__("Alert not found", {"alert_id": str(alert_id)})
```

- [ ] **Step 5: Add the settings**

Replace `backend/core/config.py` with:

```python
"""Application settings — the ONLY module allowed to read the environment."""

import logging
import secrets
from functools import lru_cache
from typing import Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from enums import LlmProvider

logger = logging.getLogger(__name__)

DEVELOPMENT_ENV = "development"
MIN_JWT_SECRET_BYTES = 32  # RFC 7518 §3.2: an HS256 key is at least the hash size
_GENERATED_SECRET_BYTES = 48


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    env: str = DEVELOPMENT_ENV
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://app:app@db:5432/app"
    test_database_url: str = "postgresql+asyncpg://app:app@127.0.0.1:54329/app_test"
    redis_url: str = "redis://redis:6379/0"
    search_cache_ttl_seconds: int = 600
    intent_cache_ttl_seconds: int = 86_400
    llm_provider: LlmProvider = LlmProvider.GOOGLE
    llm_model: str = "gemini-3.7-flash"
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str | None = None
    llm_timeout_seconds: float = 4.0
    assistant_timeout_seconds: float = 20.0  # tool calls need two round trips
    jwt_secret: SecretStr = SecretStr("")
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    scrypt_n: int = 2**17
    admin_email: str = ""
    admin_password: SecretStr = SecretStr("")

    @property
    def is_development(self) -> bool:
        return self.env == DEVELOPMENT_ENV

    @model_validator(mode="after")
    def _resolve_jwt_secret(self) -> Self:
        secret = self.jwt_secret.get_secret_value()
        if secret:
            if len(secret.encode()) < MIN_JWT_SECRET_BYTES:
                raise ValueError(
                    f"JWT_SECRET must be at least {MIN_JWT_SECRET_BYTES} bytes"
                )
            return self
        if not self.is_development:
            raise ValueError("JWT_SECRET must be set outside development")
        logger.warning("JWT_SECRET is empty: using a random secret for this process")
        self.jwt_secret = SecretStr(secrets.token_urlsafe(_GENERATED_SECRET_BYTES))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 6: Add the shared fast test settings**

Append to `backend/tests/support.py`:

```python
from core.config import Settings

TEST_JWT_SECRET = "t" * 32
TEST_SCRYPT_N = 2**4  # production cost is 2**17 (~0.2 s and 128 MiB per hash)


def fast_auth_settings() -> Settings:
    return Settings(
        _env_file=None,
        env="development",
        jwt_secret=TEST_JWT_SECRET,
        scrypt_n=TEST_SCRYPT_N,
    )
```

Move the `from core.config import Settings` import to the top of the file, under `from typing import Any`.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/core/test_config.py tests/test_errors.py -q`
Expected: PASS.

- [ ] **Step 8: Add the env keys and secret generation**

In `example.env`, after the `ASSISTANT_TIMEOUT_SECONDS=20` line add:

```dotenv

# Auth — JWT_SECRET must be >= 32 bytes; ./.scripts/setup.sh generates one. Empty is
# allowed only with ENV=development (a random per-process secret: logins reset on restart).
JWT_SECRET=
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=30
SCRYPT_N=131072

# Admin account created at startup when both are set. An existing account with this
# email is never modified.
ADMIN_EMAIL=
ADMIN_PASSWORD=
```

In `.scripts/setup.sh`, after the `[[ -f .env ]] || cp example.env .env` line add:

```bash
if grep -q '^JWT_SECRET=$' .env; then
  secret="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  sed -i.bak "s|^JWT_SECRET=$|JWT_SECRET=${secret}|" .env && rm -f .env.bak
fi
```

- [ ] **Step 9: Lint and commit**

```bash
cd backend && uv run ruff check . --fix && uv run black . && uv run pytest tests/core/test_config.py tests/test_errors.py -q && cd ..
git add backend/core/config.py backend/enums.py backend/errors.py backend/tests/support.py backend/tests/core/test_config.py backend/tests/test_errors.py example.env .scripts/setup.sh
git commit -m "feat(backend): add auth settings, roles and errors"
```

---

### Task 2: Password hashing and tokens (`core/security.py`)

**Files:**
- Create: `backend/core/security.py`
- Modify: `backend/pyproject.toml` + `backend/uv.lock` (only through `uv add`)
- Test: `backend/tests/core/test_security.py`

**Interfaces:**
- Consumes: `enums.TokenType`, `enums.UserRole`, `errors.NotAuthenticatedError`, `errors.TokenExpiredError` (Task 1).
- Produces:
  - constants `ACCESS_COOKIE = "access_token"`, `REFRESH_COOKIE = "refresh_token"`, `REFRESH_COOKIE_PATH = "/api/v1/auth"`
  - `hash_password(password: str, n: int) -> str`
  - `verify_password(password: str, stored: str) -> bool`
  - `TokenClaims(user_id: uuid.UUID, token_version: int, role: UserRole | None)` — frozen dataclass. This plays the spec's `CurrentUser(id, role)` role; there is no second class.
  - `TokenPair(access: str, refresh: str)` — frozen dataclass
  - `encode_token(claims: TokenClaims, token_type: TokenType, secret: str, lifetime: timedelta) -> str`
  - `decode_token(token: str, secret: str, expected_type: TokenType) -> TokenClaims` — raises `TokenExpiredError` / `NotAuthenticatedError`
  - `issue_token_pair(claims: TokenClaims, secret: str, access_lifetime: timedelta, refresh_lifetime: timedelta) -> TokenPair`

- [ ] **Step 1: Add the dependency**

Run (from `backend/`): `uv add pyjwt`
Expected: `pyproject.toml` gains `"pyjwt>=…"` and `uv.lock` is refreshed by uv.

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/core/test_security.py`:

```python
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/core/test_security.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.security'`.

- [ ] **Step 4: Implement**

Create `backend/core/security.py`:

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/core/test_security.py -q`
Expected: PASS (12 tests). `test_production_cost_fits_the_memory_limit` takes ~0.5 s — it is the only test allowed to hash at production cost.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check . --fix && uv run black .
cd .. && git add backend/core/security.py backend/tests/core/test_security.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(backend): add scrypt password hashing and JWT helpers"
```

---

### Task 3: Models and migration

**Files:**
- Create: `backend/models/user.py`, `backend/models/saved_listing.py`, `backend/models/price_alert.py`, `backend/db/migrations/versions/0003_accounts.py`
- Modify: `backend/models/__init__.py`
- Test: `backend/tests/db/test_schema.py` (the existing drift test is the gate)

**Interfaces:**
- Consumes: `enums.UserRole` (Task 1); `db.base.Base`, `UUIDPrimaryKeyMixin`, `enum_type`.
- Produces: `models.user.User` (`email`, `password_hash`, `role`, `is_active`, `token_version`, `created_at`, `last_login_at`) and `models.user.utc_now() -> datetime`; `models.saved_listing.SavedListing` (`user_id`, `listing_id`, `created_at`); `models.price_alert.PriceAlert` (`user_id`, `title`, `threshold`, `params`, `created_at`).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/db/test_schema.py`:

```python
@pytest.mark.db
async def test_account_tables_exist_with_their_constraints(
    session: AsyncSession,
) -> None:
    rows = await session.execute(
        text(
            "SELECT conrelid::regclass::text, conname FROM pg_constraint "
            "WHERE conrelid::regclass::text IN "
            "('users', 'saved_listings', 'price_alerts')"
        )
    )
    constraints = {(table, name) for table, name in rows}
    assert ("users", "users_email_key") in constraints
    assert ("saved_listings", "uq_saved_listings_user_listing") in constraints
    assert ("price_alerts", "price_alerts_user_id_fkey") in constraints
```

If `text` is not already imported in that file, add `from sqlalchemy import text`.

- [ ] **Step 2: Run it to verify it fails**

Run (repo root, once): `./.scripts/test-db.sh`
Run (from `backend/`): `uv run pytest tests/db/test_schema.py -q`
Expected: FAIL — the constraint set is empty (tables do not exist).

- [ ] **Step 3: Create the models**

`backend/models/user.py`:

```python
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, UUIDPrimaryKeyMixin, enum_type
from enums import UserRole

EMAIL_MAX_LENGTH = 320


def utc_now() -> datetime:
    return datetime.now(UTC)


class User(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "users"

    # Always stored lowercased (schemas/auth.py normalises), so uniqueness is
    # case-insensitive without a functional index.
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(enum_type(UserRole), default=UserRole.USER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Copied into every token as `ver`; bumping it revokes all of the user's tokens.
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

`backend/models/saved_listing.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, UUIDPrimaryKeyMixin
from models.user import utc_now


class SavedListing(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "saved_listings"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "listing_id", name="uq_saved_listings_user_listing"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
```

`backend/models/price_alert.py`:

```python
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, UUIDPrimaryKeyMixin
from models.user import utc_now


class PriceAlert(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "price_alerts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(Text)
    threshold: Mapped[int] = mapped_column(BigInteger)
    # The search parameters exactly as the frontend sent them; never interpreted here.
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
```

Replace `backend/models/__init__.py` with:

```python
"""Import every model so `Base.metadata` is complete for Alembic."""

from models.city import City
from models.listing import Listing
from models.price_alert import PriceAlert
from models.saved_listing import SavedListing
from models.user import User
from models.vehicle_catalog import VehicleCatalog

__all__ = ["City", "Listing", "PriceAlert", "SavedListing", "User", "VehicleCatalog"]
```

- [ ] **Step 4: Write the migration**

Create `backend/db/migrations/versions/0003_accounts.py`:

```python
"""add users, saved listings and price alerts

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_USER_ROLE = sa.Enum("user", "admin", name="userrole", native_enum=False, length=32)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", _USER_ROLE, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "saved_listings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "listing_id", name="uq_saved_listings_user_listing"
        ),
    )
    op.create_table(
        "price_alerts",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("threshold", sa.BigInteger(), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_price_alerts_user_id"), "price_alerts", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_price_alerts_user_id"), table_name="price_alerts")
    op.drop_table("price_alerts")
    op.drop_table("saved_listings")
    op.drop_table("users")
```

- [ ] **Step 5: Run the schema tests to verify they pass**

Run: `uv run pytest tests/db/test_schema.py -q`
Expected: PASS — including the pre-existing `test_models_and_migrations_do_not_drift`, which fails if the migration and the models disagree. If it reports a diff, fix the **migration** to match the models, not the reverse.

- [ ] **Step 6: Verify the downgrade against the throwaway test database**

Run (from `backend/`):
```bash
uv run python - <<'EOF'
from alembic import command
from alembic.config import Config
from core.config import get_settings

config = Config("alembic.ini")
config.set_main_option("script_location", "db/migrations")
config.attributes["database_url"] = get_settings().test_database_url
command.downgrade(config, "0002")
command.upgrade(config, "head")
print("downgrade + upgrade ok")
EOF
```
Expected: `downgrade + upgrade ok`. This targets `TEST_DATABASE_URL` (127.0.0.1:54329) only — never the dev database.

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff check . --fix && uv run black .
cd .. && git add backend/models/user.py backend/models/saved_listing.py backend/models/price_alert.py backend/models/__init__.py backend/db/migrations/versions/0003_accounts.py backend/tests/db/test_schema.py
git commit -m "feat(backend): add users, saved listings and price alerts tables"
```

---

### Task 4: `UserRepository`

**Files:**
- Create: `backend/repositories/user_repository.py`
- Test: `backend/tests/repositories/test_user_repository.py`

**Interfaces:**
- Consumes: `models.user.User`, `models.user.utc_now`, `enums.UserRole`.
- Produces `UserRepository(session: AsyncSession)` with:
  - `async get_by_id(user_id: uuid.UUID) -> User | None`
  - `async get_by_email(email: str) -> User | None` — expects an already-normalised (lowercased) email
  - `async create_if_absent(email: str, password_hash: str, role: UserRole) -> User | None` — `None` means the email was already taken
  - `async record_login(user: User) -> None`
  - `async replace_password(user: User, password_hash: str) -> None` — also bumps `token_version`
  - `async bump_token_version(user: User) -> None`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/repositories/test_user_repository.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from enums import UserRole
from repositories.user_repository import UserRepository

pytestmark = pytest.mark.db

EMAIL = "reader@example.com"


async def test_create_if_absent_fills_the_defaults(session: AsyncSession) -> None:
    user = await UserRepository(session).create_if_absent(EMAIL, "hash", UserRole.USER)
    assert user is not None
    assert user.id.version == 8
    assert (user.role, user.is_active, user.token_version) == (UserRole.USER, True, 0)
    assert user.created_at is not None and user.last_login_at is None


async def test_create_if_absent_returns_none_for_a_taken_email(
    session: AsyncSession,
) -> None:
    users = UserRepository(session)
    first = await users.create_if_absent(EMAIL, "first-hash", UserRole.USER)
    second = await users.create_if_absent(EMAIL, "second-hash", UserRole.ADMIN)
    assert first is not None and second is None
    kept = await users.get_by_email(EMAIL)
    assert kept is not None
    assert (kept.password_hash, kept.role) == ("first-hash", UserRole.USER)


async def test_lookups_find_the_user_or_return_none(session: AsyncSession) -> None:
    users = UserRepository(session)
    created = await users.create_if_absent(EMAIL, "hash", UserRole.USER)
    assert created is not None
    assert (await users.get_by_id(created.id)) is created
    assert (await users.get_by_email(EMAIL)) is created
    assert await users.get_by_email("nobody@example.com") is None


async def test_replace_password_revokes_existing_tokens(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create_if_absent(EMAIL, "old-hash", UserRole.USER)
    assert user is not None
    await users.replace_password(user, "new-hash")
    assert (user.password_hash, user.token_version) == ("new-hash", 1)


async def test_record_login_and_bump_token_version(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create_if_absent(EMAIL, "hash", UserRole.USER)
    assert user is not None
    await users.record_login(user)
    await users.bump_token_version(user)
    assert user.last_login_at is not None and user.token_version == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/repositories/test_user_repository.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'repositories.user_repository'`.

- [ ] **Step 3: Implement**

Create `backend/repositories/user_repository.py`:

```python
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from enums import UserRole
from models.user import User, utc_now


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        return await self._session.scalar(select(User).where(User.email == email))

    async def create_if_absent(
        self, email: str, password_hash: str, role: UserRole
    ) -> User | None:
        """One atomic statement, so two concurrent sign-ups (or two workers
        bootstrapping the admin) cannot both win. `None` = the email is taken."""
        statement = (
            insert(User)
            .values(email=email, password_hash=password_hash, role=role)
            .on_conflict_do_nothing(index_elements=[User.email])
            .returning(User)
        )
        return await self._session.scalar(statement)

    async def record_login(self, user: User) -> None:
        user.last_login_at = utc_now()
        await self._session.flush()

    async def replace_password(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        await self.bump_token_version(user)

    async def bump_token_version(self, user: User) -> None:
        user.token_version += 1
        await self._session.flush()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/repositories/test_user_repository.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check . --fix && uv run black .
cd .. && git add backend/repositories/user_repository.py backend/tests/repositories/test_user_repository.py
git commit -m "feat(backend): add user repository"
```

---

### Task 5: `SavedListingRepository` and `PriceAlertRepository`

**Files:**
- Create: `backend/repositories/saved_listing_repository.py`, `backend/repositories/price_alert_repository.py`
- Test: `backend/tests/repositories/test_saved_listing_repository.py`, `backend/tests/repositories/test_price_alert_repository.py`

**Interfaces:**
- Consumes: `UserRepository.create_if_absent` (Task 4); `models.saved_listing.SavedListing`, `models.price_alert.PriceAlert`, `models.listing.Listing`; the `seeded_session` fixture (617 real listings).
- Produces:
  - `SavedListingRepository(session)`: `async list_listing_ids(user_id) -> list[uuid.UUID]` (newest first), `async add_many(user_id, listing_ids: Sequence[uuid.UUID]) -> None` (idempotent), `async remove(user_id, listing_id) -> None` (idempotent)
  - `PriceAlertRepository(session)`: `async list_for_user(user_id) -> list[PriceAlert]` (oldest first), `async add(alert: PriceAlert) -> PriceAlert`, `async remove(user_id, alert_id) -> bool` (`False` = nothing matched, including "owned by someone else")

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/repositories/test_saved_listing_repository.py`:

```python
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums import UserRole
from models.listing import Listing
from models.user import User
from repositories.saved_listing_repository import SavedListingRepository
from repositories.user_repository import UserRepository

pytestmark = pytest.mark.db


async def _user(session: AsyncSession, email: str = "saver@example.com") -> User:
    user = await UserRepository(session).create_if_absent(email, "hash", UserRole.USER)
    assert user is not None
    return user


async def _listing_ids(session: AsyncSession, count: int) -> list[uuid.UUID]:
    found = await session.scalars(select(Listing.id).order_by(Listing.id).limit(count))
    return list(found)


async def test_saving_twice_is_a_no_op(seeded_session: AsyncSession) -> None:
    saved = SavedListingRepository(seeded_session)
    user = await _user(seeded_session)
    (listing_id,) = await _listing_ids(seeded_session, 1)
    await saved.add_many(user.id, [listing_id])
    await saved.add_many(user.id, [listing_id])
    assert await saved.list_listing_ids(user.id) == [listing_id]


async def test_the_list_is_per_user(seeded_session: AsyncSession) -> None:
    saved = SavedListingRepository(seeded_session)
    first_user = await _user(seeded_session)
    other_user = await _user(seeded_session, "other@example.com")
    one, two = await _listing_ids(seeded_session, 2)
    await saved.add_many(first_user.id, [one, two])
    await saved.add_many(other_user.id, [one])
    assert set(await saved.list_listing_ids(first_user.id)) == {one, two}
    assert await saved.list_listing_ids(other_user.id) == [one]


async def test_remove_is_idempotent(seeded_session: AsyncSession) -> None:
    saved = SavedListingRepository(seeded_session)
    user = await _user(seeded_session)
    (listing_id,) = await _listing_ids(seeded_session, 1)
    await saved.add_many(user.id, [listing_id])
    await saved.remove(user.id, listing_id)
    await saved.remove(user.id, listing_id)
    assert await saved.list_listing_ids(user.id) == []


async def test_add_many_with_nothing_does_nothing(seeded_session: AsyncSession) -> None:
    saved = SavedListingRepository(seeded_session)
    user = await _user(seeded_session)
    await saved.add_many(user.id, [])
    assert await saved.list_listing_ids(user.id) == []


async def test_deleting_the_user_cascades(seeded_session: AsyncSession) -> None:
    saved = SavedListingRepository(seeded_session)
    user = await _user(seeded_session)
    await saved.add_many(user.id, await _listing_ids(seeded_session, 2))
    await seeded_session.execute(delete(User).where(User.id == user.id))
    assert await saved.list_listing_ids(user.id) == []
```

(Ordering is `created_at DESC`; it is not asserted here because rows written in the same transaction share a clock reading too closely to order deterministically.)

Create `backend/tests/repositories/test_price_alert_repository.py`:

```python
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from enums import UserRole
from models.price_alert import PriceAlert
from models.user import User
from repositories.price_alert_repository import PriceAlertRepository
from repositories.user_repository import UserRepository

pytestmark = pytest.mark.db

PARAMS = {"q": "پژو ۲۰۶", "cities": ["تهران"]}


async def _user(session: AsyncSession, email: str) -> User:
    user = await UserRepository(session).create_if_absent(email, "hash", UserRole.USER)
    assert user is not None
    return user


def _alert(user: User, title: str = "۲۰۶ زیر ۵۰۰") -> PriceAlert:
    return PriceAlert(
        user_id=user.id, title=title, threshold=500_000_000, params=PARAMS
    )


async def test_an_added_alert_is_stored_and_listed(session: AsyncSession) -> None:
    alerts = PriceAlertRepository(session)
    user = await _user(session, "alerts@example.com")
    stored = await alerts.add(_alert(user))
    assert stored.id.version == 8 and stored.created_at is not None
    listed = await alerts.list_for_user(user.id)
    assert [(a.title, a.threshold, a.params) for a in listed] == [
        ("۲۰۶ زیر ۵۰۰", 500_000_000, PARAMS)
    ]


async def test_remove_reports_whether_anything_was_deleted(
    session: AsyncSession,
) -> None:
    alerts = PriceAlertRepository(session)
    user = await _user(session, "alerts@example.com")
    alert = await alerts.add(_alert(user))
    assert await alerts.remove(user.id, alert.id) is True
    assert await alerts.remove(user.id, alert.id) is False


async def test_another_users_alert_cannot_be_removed(session: AsyncSession) -> None:
    alerts = PriceAlertRepository(session)
    owner = await _user(session, "owner@example.com")
    intruder = await _user(session, "intruder@example.com")
    alert = await alerts.add(_alert(owner))
    assert await alerts.remove(intruder.id, alert.id) is False
    assert len(await alerts.list_for_user(owner.id)) == 1


async def test_deleting_the_user_cascades(session: AsyncSession) -> None:
    alerts = PriceAlertRepository(session)
    user = await _user(session, "alerts@example.com")
    await alerts.add(_alert(user))
    await session.execute(delete(User).where(User.id == user.id))
    assert await alerts.list_for_user(user.id) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/repositories/test_saved_listing_repository.py tests/repositories/test_price_alert_repository.py -q`
Expected: FAIL — `ModuleNotFoundError` for both repository modules.

- [ ] **Step 3: Implement**

Create `backend/repositories/saved_listing_repository.py`:

```python
import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.saved_listing import SavedListing


class SavedListingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_listing_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        found = await self._session.scalars(
            select(SavedListing.listing_id)
            .where(SavedListing.user_id == user_id)
            .order_by(SavedListing.created_at.desc(), SavedListing.id.desc())
        )
        return list(found)

    async def add_many(
        self, user_id: uuid.UUID, listing_ids: Sequence[uuid.UUID]
    ) -> None:
        if not listing_ids:
            return
        rows = [{"user_id": user_id, "listing_id": item} for item in listing_ids]
        statement = insert(SavedListing).values(rows)
        await self._session.execute(
            statement.on_conflict_do_nothing(
                index_elements=[SavedListing.user_id, SavedListing.listing_id]
            )
        )

    async def remove(self, user_id: uuid.UUID, listing_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(SavedListing).where(
                SavedListing.user_id == user_id, SavedListing.listing_id == listing_id
            )
        )
```

Create `backend/repositories/price_alert_repository.py`:

```python
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.price_alert import PriceAlert


class PriceAlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: uuid.UUID) -> list[PriceAlert]:
        found = await self._session.scalars(
            select(PriceAlert)
            .where(PriceAlert.user_id == user_id)
            .order_by(PriceAlert.created_at, PriceAlert.id)
        )
        return list(found)

    async def add(self, alert: PriceAlert) -> PriceAlert:
        self._session.add(alert)
        await self._session.flush()
        return alert

    async def remove(self, user_id: uuid.UUID, alert_id: uuid.UUID) -> bool:
        """Scoped by owner: someone else's alert is indistinguishable from none."""
        result = await self._session.execute(
            delete(PriceAlert)
            .where(PriceAlert.id == alert_id, PriceAlert.user_id == user_id)
            .returning(PriceAlert.id)
        )
        return result.first() is not None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/repositories/test_saved_listing_repository.py tests/repositories/test_price_alert_repository.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check . --fix && uv run black .
cd .. && git add backend/repositories/saved_listing_repository.py backend/repositories/price_alert_repository.py backend/tests/repositories/test_saved_listing_repository.py backend/tests/repositories/test_price_alert_repository.py
git commit -m "feat(backend): add saved listing and price alert repositories"
```

---

### Task 6: Auth schemas and `AuthService`

**Files:**
- Create: `backend/schemas/auth.py`, `backend/services/auth_service.py`
- Test: `backend/tests/schemas/__init__.py` (empty), `backend/tests/schemas/test_auth_schemas.py`, `backend/tests/services/test_auth_service.py`

**Interfaces:**
- Consumes: `core.security` (Task 2), `UserRepository` (Task 4), `Settings` + `fast_auth_settings()` (Task 1), errors (Task 1).
- Produces:
  - `schemas.auth`: `UserCreate {email, password}`, `LoginRequest {email, password}`, `PasswordChange {current, new}`, `UserRead {id, email, role, created_at}`; constants `MIN_PASSWORD_LENGTH = 8`, `MAX_PASSWORD_LENGTH = 128`. Emails arrive stripped and lowercased; passwords are `SecretStr`.
  - `services.auth_service.AuthResult(user: UserRead, tokens: TokenPair)` — frozen dataclass
  - `AuthService(users: UserRepository, settings: Settings)` with:
    - `async register(payload: UserCreate) -> AuthResult`
    - `async authenticate(payload: LoginRequest) -> AuthResult`
    - `async refresh(refresh_token: str | None) -> AuthResult`
    - `async change_password(user_id: uuid.UUID, payload: PasswordChange) -> AuthResult`
    - `async logout_all(user_id: uuid.UUID) -> None`
    - `async get_user(user_id: uuid.UUID) -> UserRead`
    - `async require_admin(user_id: uuid.UUID) -> UserRead`
    - `async ensure_admin(email: str, password: str) -> bool` — `True` only when it created the account

- [ ] **Step 1: Write the failing schema tests**

Create an empty `backend/tests/schemas/__init__.py`, then `backend/tests/schemas/test_auth_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from schemas.auth import LoginRequest, PasswordChange, UserCreate


def test_email_is_stripped_and_lowercased() -> None:
    account = UserCreate(email="  Reader@Example.COM ", password="12345678")
    assert account.email == "reader@example.com"
    assert LoginRequest(email="READER@example.com", password="x").email == (
        "reader@example.com"
    )


@pytest.mark.parametrize("password", ["1234567", "x" * 129])
def test_new_passwords_must_be_8_to_128_characters(password: str) -> None:
    with pytest.raises(ValidationError):
        UserCreate(email="reader@example.com", password=password)
    with pytest.raises(ValidationError):
        PasswordChange(current="whatever", new=password)


def test_login_accepts_a_short_password_so_it_fails_as_401_not_422() -> None:
    assert LoginRequest(email="reader@example.com", password="x")
    with pytest.raises(ValidationError):
        LoginRequest(email="reader@example.com", password="x" * 129)


def test_passwords_never_appear_in_repr() -> None:
    account = UserCreate(email="reader@example.com", password="hunter2-hunter2")
    assert "hunter2" not in repr(account)


def test_a_malformed_email_is_rejected() -> None:
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", password="12345678")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/schemas -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'schemas.auth'`.

- [ ] **Step 3: Implement the schemas**

Create `backend/schemas/auth.py`:

```python
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
)

from enums import UserRole

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128  # bounds the work an attacker can force on the hasher


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


# EmailStr lowercases only the domain; the whole address is lowered so that
# `users.email` uniqueness is case-insensitive.
Email = Annotated[EmailStr, BeforeValidator(_strip), AfterValidator(str.lower)]
NewPassword = Annotated[
    SecretStr, Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
]
# No minimum: a too-short guess must fail as 401 invalid_credentials, not 422.
GivenPassword = Annotated[SecretStr, Field(max_length=MAX_PASSWORD_LENGTH)]


class UserCreate(BaseModel):
    email: Email
    password: NewPassword


class LoginRequest(BaseModel):
    email: Email
    password: GivenPassword


class PasswordChange(BaseModel):
    current: GivenPassword
    new: NewPassword


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: UserRole
    created_at: datetime
```

Run: `uv run pytest tests/schemas -q` — Expected: PASS (6 tests).

- [ ] **Step 4: Write the failing service tests**

Create `backend/tests/services/test_auth_service.py`:

```python
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
from schemas.auth import LoginRequest, PasswordChange, UserCreate
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


def _refresh_token(user: User, lifetime: timedelta = timedelta(days=1)) -> str:
    claims = TokenClaims(user.id, user.token_version, None)
    return encode_token(claims, TokenType.REFRESH, TEST_JWT_SECRET, lifetime)


async def test_register_hashes_the_password_and_issues_tokens() -> None:
    users = _users(create_if_absent=_user())
    result = await _service(users).register(UserCreate(email=EMAIL, password=PASSWORD))
    email, stored_hash, role = users.create_if_absent.call_args.args
    assert (email, role) == (EMAIL, UserRole.USER)
    assert stored_hash != PASSWORD and verify_password(PASSWORD, stored_hash)
    claims = decode_token(result.tokens.access, TEST_JWT_SECRET, TokenType.ACCESS)
    assert claims == TokenClaims(uuid.UUID(int=42), 0, UserRole.USER)
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
        TokenClaims(user.id, 1, UserRole.USER),
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
```

- [ ] **Step 5: Run them to verify they fail**

Run: `uv run pytest tests/services/test_auth_service.py -q`
Expected: FAIL — `ImportError: cannot import name 'auth_service' from 'services'`.

- [ ] **Step 6: Implement the service**

Create `backend/services/auth_service.py`:

```python
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
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/schemas tests/services/test_auth_service.py -q`
Expected: PASS (6 + 18 tests).

- [ ] **Step 8: Lint and commit**

```bash
uv run ruff check . --fix && uv run black .
cd .. && git add backend/schemas/auth.py backend/services/auth_service.py backend/tests/schemas backend/tests/services/test_auth_service.py
git commit -m "feat(backend): add auth schemas and service"
```

---

### Task 7: Account schemas and `AccountService`

**Files:**
- Create: `backend/schemas/account.py`, `backend/services/account_service.py`
- Test: `backend/tests/services/test_account_service.py`

**Interfaces:**
- Consumes: `SavedListingRepository`, `PriceAlertRepository` (Task 5); the existing `ListingRepository.get_by_id(listing_id) -> Listing | None` and `.get_by_ids(listing_ids) -> list[Listing]`; `errors.ListingNotFoundError`, `errors.AlertNotFoundError`.
- Produces:
  - `schemas.account`: `PriceAlertCreate {title, threshold, params}`, `PriceAlertRead {id, title, threshold, params, created_at}`, `ImportRequest {saved, alerts}`, `AccountState {saved, alerts}`; constants `MAX_IMPORT_SAVED = 500`, `MAX_IMPORT_ALERTS = 50`
  - `AccountService(saved: SavedListingRepository, alerts: PriceAlertRepository, listings: ListingRepository)` with `async list_saved(user_id) -> list[uuid.UUID]`, `async save_listing(user_id, listing_id) -> None`, `async unsave_listing(user_id, listing_id) -> None`, `async list_alerts(user_id) -> list[PriceAlertRead]`, `async create_alert(user_id, payload: PriceAlertCreate) -> PriceAlertRead`, `async delete_alert(user_id, alert_id) -> None`, `async import_state(user_id, payload: ImportRequest) -> AccountState`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/services/test_account_service.py`:

```python
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from errors import AlertNotFoundError, ListingNotFoundError
from models.price_alert import PriceAlert
from repositories.listing_repository import ListingRepository
from repositories.price_alert_repository import PriceAlertRepository
from repositories.saved_listing_repository import SavedListingRepository
from schemas.account import ImportRequest, PriceAlertCreate
from services.account_service import AccountService

USER_ID = uuid.UUID(int=1)
REAL = uuid.UUID(int=100)
GONE = uuid.UUID(int=200)
ALERT = {"title": "۲۰۶ زیر ۵۰۰", "threshold": 500_000_000, "params": {"q": "۲۰۶"}}


def _stored(alert: PriceAlert) -> PriceAlert:
    alert.id = uuid.uuid4()
    alert.created_at = datetime.now(UTC)
    return alert


class Doubles:
    def __init__(self) -> None:
        self.saved = AsyncMock(spec=SavedListingRepository)
        self.alerts = AsyncMock(spec=PriceAlertRepository)
        self.listings = AsyncMock(spec=ListingRepository)
        self.alerts.add.side_effect = _stored
        self.alerts.list_for_user.return_value = []
        self.saved.list_listing_ids.return_value = []
        self.service = AccountService(self.saved, self.alerts, self.listings)


async def test_saving_an_unknown_listing_raises() -> None:
    doubles = Doubles()
    doubles.listings.get_by_id.return_value = None
    with pytest.raises(ListingNotFoundError):
        await doubles.service.save_listing(USER_ID, GONE)
    doubles.saved.add_many.assert_not_awaited()


async def test_saving_a_known_listing_stores_it() -> None:
    doubles = Doubles()
    doubles.listings.get_by_id.return_value = SimpleNamespace(id=REAL)
    await doubles.service.save_listing(USER_ID, REAL)
    doubles.saved.add_many.assert_awaited_once_with(USER_ID, [REAL])


async def test_create_alert_belongs_to_the_caller() -> None:
    doubles = Doubles()
    created = await doubles.service.create_alert(USER_ID, PriceAlertCreate(**ALERT))
    assert doubles.alerts.add.call_args.args[0].user_id == USER_ID
    assert (created.title, created.threshold, created.params) == (
        ALERT["title"],
        ALERT["threshold"],
        ALERT["params"],
    )


async def test_deleting_a_missing_or_foreign_alert_raises() -> None:
    doubles = Doubles()
    doubles.alerts.remove.return_value = False
    with pytest.raises(AlertNotFoundError):
        await doubles.service.delete_alert(USER_ID, uuid.UUID(int=9))


async def test_import_skips_vanished_listings_and_duplicate_alerts() -> None:
    doubles = Doubles()
    doubles.listings.get_by_ids.return_value = [SimpleNamespace(id=REAL)]
    payload = ImportRequest(saved=[REAL, GONE, REAL], alerts=[ALERT, ALERT])
    await doubles.service.import_state(USER_ID, payload)
    doubles.saved.add_many.assert_awaited_once_with(USER_ID, [REAL])
    assert doubles.alerts.add.await_count == 1


async def test_import_does_not_duplicate_an_alert_the_server_already_has() -> None:
    doubles = Doubles()
    doubles.listings.get_by_ids.return_value = []
    existing = _stored(PriceAlert(user_id=USER_ID, **ALERT))
    doubles.alerts.list_for_user.return_value = [existing]
    state = await doubles.service.import_state(
        USER_ID, ImportRequest(saved=[], alerts=[ALERT])
    )
    doubles.alerts.add.assert_not_awaited()
    assert [alert.id for alert in state.alerts] == [existing.id]


async def test_an_empty_import_touches_nothing() -> None:
    doubles = Doubles()
    await doubles.service.import_state(USER_ID, ImportRequest(saved=[], alerts=[]))
    doubles.listings.get_by_ids.assert_not_awaited()
    doubles.alerts.add.assert_not_awaited()


def test_import_limits_and_alert_bounds_are_enforced() -> None:
    with pytest.raises(ValidationError):
        ImportRequest(saved=[uuid.uuid4() for _ in range(501)], alerts=[])
    with pytest.raises(ValidationError):
        ImportRequest(saved=[], alerts=[ALERT] * 51)
    with pytest.raises(ValidationError):
        PriceAlertCreate(title="", threshold=1, params={})
    with pytest.raises(ValidationError):
        PriceAlertCreate(title="x", threshold=0, params={})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/services/test_account_service.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'schemas.account'`.

- [ ] **Step 3: Implement the schemas**

Create `backend/schemas/account.py`:

```python
import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

MAX_IMPORT_SAVED = 500
MAX_IMPORT_ALERTS = 50
MAX_ALERT_TITLE_LENGTH = 200


class PriceAlertCreate(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_ALERT_TITLE_LENGTH)
    threshold: int = Field(gt=0)
    # The frontend's search parameters, stored as sent and never interpreted here.
    params: dict[str, Any]


class PriceAlertRead(PriceAlertCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class ImportRequest(BaseModel):
    saved: Annotated[list[uuid.UUID], Field(max_length=MAX_IMPORT_SAVED)]
    alerts: Annotated[list[PriceAlertCreate], Field(max_length=MAX_IMPORT_ALERTS)]


class AccountState(BaseModel):
    saved: list[uuid.UUID]
    alerts: list[PriceAlertRead]
```

- [ ] **Step 4: Implement the service**

Create `backend/services/account_service.py`:

```python
"""What an account holds: saved listings and price alerts."""

import json
import uuid
from collections.abc import Sequence
from typing import Any

from errors import AlertNotFoundError, ListingNotFoundError
from models.price_alert import PriceAlert
from repositories.listing_repository import ListingRepository
from repositories.price_alert_repository import PriceAlertRepository
from repositories.saved_listing_repository import SavedListingRepository
from schemas.account import (
    AccountState,
    ImportRequest,
    PriceAlertCreate,
    PriceAlertRead,
)


def _alert_key(title: str, threshold: int, params: dict[str, Any]) -> str:
    return json.dumps([title, threshold, params], sort_keys=True, ensure_ascii=False)


class AccountService:
    def __init__(
        self,
        saved: SavedListingRepository,
        alerts: PriceAlertRepository,
        listings: ListingRepository,
    ) -> None:
        self._saved = saved
        self._alerts = alerts
        self._listings = listings

    async def list_saved(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        return await self._saved.list_listing_ids(user_id)

    async def save_listing(self, user_id: uuid.UUID, listing_id: uuid.UUID) -> None:
        if await self._listings.get_by_id(listing_id) is None:
            raise ListingNotFoundError(listing_id)
        await self._saved.add_many(user_id, [listing_id])

    async def unsave_listing(self, user_id: uuid.UUID, listing_id: uuid.UUID) -> None:
        await self._saved.remove(user_id, listing_id)

    async def list_alerts(self, user_id: uuid.UUID) -> list[PriceAlertRead]:
        alerts = await self._alerts.list_for_user(user_id)
        return [PriceAlertRead.model_validate(alert) for alert in alerts]

    async def create_alert(
        self, user_id: uuid.UUID, payload: PriceAlertCreate
    ) -> PriceAlertRead:
        alert = PriceAlert(user_id=user_id, **payload.model_dump())
        return PriceAlertRead.model_validate(await self._alerts.add(alert))

    async def delete_alert(self, user_id: uuid.UUID, alert_id: uuid.UUID) -> None:
        if not await self._alerts.remove(user_id, alert_id):
            raise AlertNotFoundError(alert_id)

    async def import_state(
        self, user_id: uuid.UUID, payload: ImportRequest
    ) -> AccountState:
        """The one-shot upload of what the browser held before login. Idempotent."""
        await self._import_saved(user_id, payload.saved)
        await self._import_alerts(user_id, payload.alerts)
        return AccountState(
            saved=await self.list_saved(user_id),
            alerts=await self.list_alerts(user_id),
        )

    async def _import_saved(
        self, user_id: uuid.UUID, listing_ids: Sequence[uuid.UUID]
    ) -> None:
        if not listing_ids:
            return
        found = await self._listings.get_by_ids(listing_ids)
        existing = {listing.id for listing in found}
        # dict.fromkeys de-duplicates while keeping the browser's order.
        kept = [item for item in dict.fromkeys(listing_ids) if item in existing]
        await self._saved.add_many(user_id, kept)

    async def _import_alerts(
        self, user_id: uuid.UUID, alerts: Sequence[PriceAlertCreate]
    ) -> None:
        if not alerts:
            return
        stored = await self._alerts.list_for_user(user_id)
        known = {_alert_key(a.title, a.threshold, a.params) for a in stored}
        for alert in alerts:
            key = _alert_key(alert.title, alert.threshold, alert.params)
            if key in known:
                continue
            known.add(key)
            await self._alerts.add(PriceAlert(user_id=user_id, **alert.model_dump()))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/services/test_account_service.py -q`
Expected: PASS (8 tests).

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check . --fix && uv run black .
cd .. && git add backend/schemas/account.py backend/services/account_service.py backend/tests/services/test_account_service.py
git commit -m "feat(backend): add account schemas and service"
```

---

### Task 8: Providers, `/auth` endpoints and admin bootstrap

**Files:**
- Create: `backend/api/v1/endpoints/auth.py`, `backend/api/v1/endpoints/me.py`
- Modify: `backend/dependencies/providers.py`, `backend/api/v1/router.py`, `backend/main.py`, `backend/tests/conftest.py`
- Test: `backend/tests/api/test_auth_api.py`

**Interfaces:**
- Consumes: `AuthService`, `AuthResult` (Task 6); `AccountService` (Task 7); `core.security.ACCESS_COOKIE`, `REFRESH_COOKIE`, `REFRESH_COOKIE_PATH`, `TokenClaims`, `TokenPair`, `decode_token`; `Settings.is_development`, `.refresh_token_days`; `tests.support.fast_auth_settings`.
- Produces in `dependencies/providers.py`: `get_auth_service(session, settings) -> AuthService`, `get_account_service(session) -> AccountService`, `get_current_user(settings, access_token) -> TokenClaims`, `CurrentUserDep`, `async require_admin(current, service) -> UserRead`. Routes `POST /api/v1/auth/{register,login,refresh,logout,logout-all,password}` and `GET /api/v1/me`.

- [ ] **Step 1: Make the `api` fixture use fast auth settings**

In `backend/tests/conftest.py`, change the support import to `from tests.support import DictCache, fast_auth_settings`. In the `api` fixture, after the `get_assistant_agent` override line, add:

```python
    app.dependency_overrides[get_settings] = fast_auth_settings
```

(`get_settings` is already imported there.)

- [ ] **Step 2: Write the failing API tests**

Create `backend/tests/api/test_auth_api.py`:

```python
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
    claims = TokenClaims(uuid.UUID(int=1), 0, UserRole.USER)
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
```

Several of these call `GET /api/v1/me`. To keep this task self-contained it adds that single route (Step 5); Task 9 adds the rest of `/me`.

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/api/test_auth_api.py -q`
Expected: FAIL — every request returns 404 (`http_error`).

- [ ] **Step 4: Add the providers**

In `backend/dependencies/providers.py`, change `from fastapi import Depends` to `from fastapi import Cookie, Depends` and add these imports in alphabetical position:

```python
from core.security import ACCESS_COOKIE, TokenClaims, decode_token
from enums import TokenType
from errors import NotAuthenticatedError
from repositories.price_alert_repository import PriceAlertRepository
from repositories.saved_listing_repository import SavedListingRepository
from repositories.user_repository import UserRepository
from schemas.auth import UserRead
from services.account_service import AccountService
from services.auth_service import AuthService
```

Append at the end of the file:

```python
def get_auth_service(session: SessionDep, settings: SettingsDep) -> AuthService:
    return AuthService(UserRepository(session), settings)


def get_account_service(session: SessionDep) -> AccountService:
    return AccountService(
        SavedListingRepository(session),
        PriceAlertRepository(session),
        ListingRepository(session),
    )


def get_current_user(
    settings: SettingsDep,
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> TokenClaims:
    """Trusts the signed token alone — no database hit. A disabled user is therefore
    locked out at their next refresh (≤ 15 min), not instantly; see `require_admin`."""
    if access_token is None:
        raise NotAuthenticatedError()
    secret = settings.jwt_secret.get_secret_value()
    return decode_token(access_token, secret, TokenType.ACCESS)


CurrentUserDep = Annotated[TokenClaims, Depends(get_current_user)]


async def require_admin(
    current: CurrentUserDep,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserRead:
    return await service.require_admin(current.user_id)
```

- [ ] **Step 5: Add the endpoints**

Create `backend/api/v1/endpoints/auth.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status

from core.config import Settings
from core.security import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    REFRESH_COOKIE_PATH,
    TokenPair,
)
from dependencies.providers import CurrentUserDep, SettingsDep, get_auth_service
from schemas.auth import LoginRequest, PasswordChange, UserCreate, UserRead
from services.auth_service import AuthService

SECONDS_PER_DAY = 86_400
ROOT_PATH = "/"
_COOKIE_PATHS = {ACCESS_COOKIE: ROOT_PATH, REFRESH_COOKIE: REFRESH_COOKIE_PATH}

router = APIRouter(prefix="/auth", tags=["auth"])
ServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def _set_auth_cookies(response: Response, tokens: TokenPair, settings: Settings) -> None:
    # Both cookies live as long as the refresh token. The access *token* inside still
    # expires after 15 minutes; keeping its cookie means the backend can answer
    # `token_expired` (→ the client refreshes) instead of `not_authenticated`.
    max_age = settings.refresh_token_days * SECONDS_PER_DAY
    values = {ACCESS_COOKIE: tokens.access, REFRESH_COOKIE: tokens.refresh}
    for name, path in _COOKIE_PATHS.items():
        response.set_cookie(
            name,
            values[name],
            max_age=max_age,
            path=path,
            httponly=True,
            samesite="lax",
            secure=not settings.is_development,
        )


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    for name, path in _COOKIE_PATHS.items():
        response.delete_cookie(
            name,
            path=path,
            httponly=True,
            samesite="lax",
            secure=not settings.is_development,
        )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate, response: Response, service: ServiceDep, settings: SettingsDep
) -> UserRead:
    result = await service.register(payload)
    _set_auth_cookies(response, result.tokens, settings)
    return result.user


@router.post("/login", response_model=UserRead)
async def login(
    payload: LoginRequest, response: Response, service: ServiceDep, settings: SettingsDep
) -> UserRead:
    result = await service.authenticate(payload)
    _set_auth_cookies(response, result.tokens, settings)
    return result.user


@router.post("/refresh", response_model=UserRead)
async def refresh(
    response: Response,
    service: ServiceDep,
    settings: SettingsDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> UserRead:
    result = await service.refresh(refresh_token)
    _set_auth_cookies(response, result.tokens, settings)
    return result.user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, settings: SettingsDep) -> None:
    _clear_auth_cookies(response, settings)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    response: Response,
    current: CurrentUserDep,
    service: ServiceDep,
    settings: SettingsDep,
) -> None:
    await service.logout_all(current.user_id)
    _clear_auth_cookies(response, settings)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChange,
    response: Response,
    current: CurrentUserDep,
    service: ServiceDep,
    settings: SettingsDep,
) -> None:
    result = await service.change_password(current.user_id, payload)
    _set_auth_cookies(response, result.tokens, settings)
```

Create `backend/api/v1/endpoints/me.py` with the one route this task's tests need (Task 9 replaces the file with the full version):

```python
from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.providers import CurrentUserDep, get_auth_service
from schemas.auth import UserRead
from services.auth_service import AuthService

router = APIRouter(prefix="/me", tags=["me"])
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.get("", response_model=UserRead)
async def read_me(current: CurrentUserDep, service: AuthServiceDep) -> UserRead:
    return await service.get_user(current.user_id)
```

In `backend/api/v1/router.py`, add `auth` and `me` to the import tuple (alphabetical: `assistant, auth, catalog, estimates, facets, listings, me, models, search`) and append:

```python
router.include_router(auth.router)
router.include_router(me.router)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/api/test_auth_api.py -q`
Expected: PASS (12 tests).

- [ ] **Step 7: Bootstrap the admin at startup**

In `backend/main.py`, change these two imports:

```python
from db.session import get_engine, get_session_factory
from dependencies.providers import get_auth_service, get_cache
```

and replace `lifespan` with:

```python
async def _bootstrap_admin() -> None:
    """Creates the ADMIN_EMAIL account if it is missing (spec 4 §5.5). A missing
    `users` table fails startup loudly: run the migrations first."""
    settings = get_settings()
    async with get_session_factory()() as session:
        service = get_auth_service(session, settings)
        await service.ensure_admin(
            settings.admin_email, settings.admin_password.get_secret_value()
        )
        await session.commit()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await _bootstrap_admin()
    yield
    await get_cache().close()
    await get_engine().dispose()
```

`httpx.ASGITransport` does not run the lifespan, so the test suite is unaffected. Verify by hand against the dev stack (repo root; first set `ADMIN_EMAIL=admin@example.com` and an 8+ character `ADMIN_PASSWORD` in `.env`):

```bash
./.scripts/dev.sh
docker compose -f .docker/compose.yml -f .docker/compose.dev.yml logs backend | grep "admin bootstrap"
```
Expected: `admin bootstrap: created` on the first boot and `admin bootstrap: account already exists, left untouched` after a restart. Then log in through `POST http://localhost/api/v1/auth/login` with those credentials and confirm the response contains `"role":"admin"`.

- [ ] **Step 8: Run the whole backend suite, lint and commit**

```bash
uv run pytest -q
uv run ruff check . --fix && uv run black .
cd .. && git add backend/dependencies/providers.py backend/api/v1/endpoints/auth.py backend/api/v1/endpoints/me.py backend/api/v1/router.py backend/main.py backend/tests/conftest.py backend/tests/api/test_auth_api.py
git commit -m "feat(backend): add auth endpoints and admin bootstrap"
```
Expected: the full suite passes — the golden queries in `tests/api/test_search_api.py` included.

---

### Task 9: `/me` endpoints

**Files:**
- Modify: `backend/api/v1/endpoints/me.py`
- Test: `backend/tests/api/test_me_api.py`

**Interfaces:**
- Consumes: `get_account_service`, `CurrentUserDep` (Task 8); `AccountService` and `schemas.account` (Task 7).
- Produces routes: `GET /me/saved`, `PUT|DELETE /me/saved/{listing_id}`, `GET|POST /me/alerts`, `DELETE /me/alerts/{alert_id}`, `POST /me/import`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/api/test_me_api.py`:

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/api/test_me_api.py -q`
Expected: FAIL — `/saved`, `/alerts` and `/import` return 404 or 405; only the `""` case of the first test passes.

- [ ] **Step 3: Implement**

Replace `backend/api/v1/endpoints/me.py` with:

```python
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from dependencies.providers import (
    CurrentUserDep,
    get_account_service,
    get_auth_service,
)
from schemas.account import (
    AccountState,
    ImportRequest,
    PriceAlertCreate,
    PriceAlertRead,
)
from schemas.auth import UserRead
from services.account_service import AccountService
from services.auth_service import AuthService

router = APIRouter(prefix="/me", tags=["me"])
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]


@router.get("", response_model=UserRead)
async def read_me(current: CurrentUserDep, service: AuthServiceDep) -> UserRead:
    return await service.get_user(current.user_id)


@router.get("/saved", response_model=list[uuid.UUID])
async def read_saved(
    current: CurrentUserDep, service: AccountServiceDep
) -> list[uuid.UUID]:
    return await service.list_saved(current.user_id)


@router.put("/saved/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def save_listing(
    listing_id: uuid.UUID, current: CurrentUserDep, service: AccountServiceDep
) -> None:
    await service.save_listing(current.user_id, listing_id)


@router.delete("/saved/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_listing(
    listing_id: uuid.UUID, current: CurrentUserDep, service: AccountServiceDep
) -> None:
    await service.unsave_listing(current.user_id, listing_id)


@router.get("/alerts", response_model=list[PriceAlertRead])
async def read_alerts(
    current: CurrentUserDep, service: AccountServiceDep
) -> list[PriceAlertRead]:
    return await service.list_alerts(current.user_id)


@router.post(
    "/alerts", response_model=PriceAlertRead, status_code=status.HTTP_201_CREATED
)
async def create_alert(
    payload: PriceAlertCreate, current: CurrentUserDep, service: AccountServiceDep
) -> PriceAlertRead:
    return await service.create_alert(current.user_id, payload)


@router.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: uuid.UUID, current: CurrentUserDep, service: AccountServiceDep
) -> None:
    await service.delete_alert(current.user_id, alert_id)


@router.post("/import", response_model=AccountState)
async def import_state(
    payload: ImportRequest, current: CurrentUserDep, service: AccountServiceDep
) -> AccountState:
    return await service.import_state(current.user_id, payload)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/api/test_me_api.py tests/api/test_auth_api.py -q`
Expected: PASS (9 + 12 tests).

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check . --fix && uv run black .
cd .. && git add backend/api/v1/endpoints/me.py backend/tests/api/test_me_api.py
git commit -m "feat(backend): add saved listing, alert and import endpoints"
```

---

### Task 10: Traefik rate limit and docs

**Files:**
- Modify: `.docker/compose.yml`, `CLAUDE.md`

No automated test covers Compose labels; the deliverable is verified by hand in Step 3.

- [ ] **Step 1: Put `/api/v1/auth` behind the tight rate limit**

In `.docker/compose.yml`, change the `api-assistant` rule line to:

```yaml
      - traefik.http.routers.api-assistant.rule=PathPrefix(`/api/v1/assistant`) || PathPrefix(`/api/v1/estimates`) || PathPrefix(`/api/v1/auth`)
```

and the comment line above that block to:

```yaml
      # LLM-backed, estimator and auth routes: tighter limit, same explicit priority tier.
```

- [ ] **Step 2: Mirror it in `CLAUDE.md`**

- §11.3 and §11.4 both contain the same two lines — apply the same two edits in both places.
- §2 repository tree: `core/security.py` is already listed; give it the trailing comment `# scrypt password hashing + JWT encode/decode`. The new files sit in directories the tree already describes, so nothing else changes there.
- §4 "Representative keys": after the `LLM_BASE_URL=` line add:

```dotenv
# Auth — JWT_SECRET >= 32 bytes (setup.sh generates it); admin is created at startup
JWT_SECRET=
ADMIN_EMAIL=
ADMIN_PASSWORD=
```

- §1, after the "Cache / LLM" bullet, add:

```markdown
- **Accounts** — email + password; stateless JWTs in two `HttpOnly` cookies (15-minute
  access, 30-day refresh). `users.token_version` is copied into every token and checked
  at refresh, so bumping it revokes a user within one access-token lifetime.
  `require_admin` always re-reads the database. Server Components stay anonymous; all
  `/me` data loads client-side.
```

- [ ] **Step 3: Verify the limit applies**

With the dev stack up (repo root):

```bash
docker compose -f .docker/compose.yml -f .docker/compose.dev.yml up -d --build
for i in $(seq 1 25); do
  curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost/api/v1/auth/refresh
done | sort | uniq -c
```
Expected: mostly `401` and at least one `429`. No `429` means the router rule did not match — re-check the label.

- [ ] **Step 4: Commit**

```bash
git add .docker/compose.yml CLAUDE.md
git commit -m "feat(docker): rate-limit the auth routes and document accounts"
```

---

### Task 11: API client — `apiPut`, `apiDelete`, 204 and silent refresh

**Files:**
- Modify: `frontend/src/lib/api/client.ts`
- Test: `frontend/src/lib/api/client.test.ts`

**Interfaces:**
- Consumes: backend codes `token_expired` and `not_authenticated`; `POST /auth/refresh` (Task 8).
- Produces: `apiPut<T = void>(path: string, body?: unknown, signal?: AbortSignal): Promise<T>`, `apiDelete<T = void>(path: string, signal?: AbortSignal): Promise<T>`; `apiGet`/`apiPost` unchanged in signature; every helper resolves `undefined` on 204 and transparently refreshes once on `token_expired`.

- [ ] **Step 1: Write the failing tests**

In `frontend/src/lib/api/client.test.ts`, change the client import to:

```ts
import { ApiError, apiDelete, apiGet, apiPost, apiPut, buildQuery } from "./client";
```

and append:

```ts
const EXPIRED = { error: { code: "token_expired", message: "Token expired", details: {} } };
const ANONYMOUS = { error: { code: "not_authenticated", message: "Not authenticated", details: {} } };
const reply = (status: number, body: unknown): Response => new Response(JSON.stringify(body), { status });
const pathOf = (call: Call): string => call.url.replace(/^.*\/api\/v1/, "");

function routeFetch(respond: (path: string) => Response): Call[] {
  const calls: Call[] = [];
  globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
    const call = { url: String(url), init };
    calls.push(call);
    return respond(pathOf(call));
  }) as unknown as typeof fetch;
  return calls;
}

test("a 204 resolves to undefined, and PUT/DELETE use their methods", async () => {
  const calls = stubFetch(() => Promise.resolve(new Response(null, { status: 204 })));
  expect(await apiPut("/me/saved/abc")).toBeUndefined();
  expect(await apiDelete("/me/saved/abc")).toBeUndefined();
  expect(calls.map((c) => c.init?.method)).toEqual(["PUT", "DELETE"]);
  expect(calls[0].init?.body).toBeUndefined();
});

test("token_expired refreshes once and replays the request", async () => {
  let refreshed = false;
  const calls = routeFetch((path) => {
    if (path === "/auth/refresh") { refreshed = true; return reply(200, {}); }
    return refreshed ? reply(200, { ok: true }) : reply(401, EXPIRED);
  });
  expect(await apiGet<{ ok: boolean }>("/me")).toEqual({ ok: true });
  expect(calls.map(pathOf)).toEqual(["/me", "/auth/refresh", "/me"]);
  expect(calls[1].init?.method).toBe("POST");
});

test("parallel expired requests share a single refresh", async () => {
  let refreshed = false;
  const calls = routeFetch((path) => {
    if (path === "/auth/refresh") { refreshed = true; return reply(200, {}); }
    return refreshed ? reply(200, []) : reply(401, EXPIRED);
  });
  await Promise.all([apiGet("/me"), apiGet("/me/saved"), apiGet("/me/alerts")]);
  expect(calls.filter((c) => pathOf(c) === "/auth/refresh")).toHaveLength(1);
});

test("a failed refresh surfaces the original token_expired error", async () => {
  const calls = routeFetch((path) => (path === "/auth/refresh" ? reply(401, ANONYMOUS) : reply(401, EXPIRED)));
  const error = await failure(apiGet("/me"));
  expect(error.code).toBe("token_expired");
  expect(calls.map(pathOf)).toEqual(["/me", "/auth/refresh"]);
});

test("not_authenticated never triggers a refresh", async () => {
  const calls = routeFetch(() => reply(401, ANONYMOUS));
  expect((await failure(apiGet("/me"))).code).toBe("not_authenticated");
  expect(calls).toHaveLength(1);
});

test("an expired refresh call is not itself refreshed", async () => {
  const calls = routeFetch(() => reply(401, EXPIRED));
  await failure(apiPost("/auth/refresh", {}));
  expect(calls).toHaveLength(1);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `frontend/`): `bun test src/lib/api/client.test.ts`
Expected: FAIL — `apiPut` / `apiDelete` are not exported.

- [ ] **Step 3: Implement**

In `frontend/src/lib/api/client.ts`, replace everything from `async function request<T>` to the end of the file with:

```ts
const NO_CONTENT = 204;
const REFRESH_PATH = "/auth/refresh";
const TOKEN_EXPIRED = "token_expired";

async function send<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    // Redis already caches rankings server-side; the browser never caches API responses.
    response = await fetch(`${apiBase()}${path}`, { ...init, cache: "no-store" });
  } catch (error) {
    if (isAbort(error)) throw error;
    throw new ApiError(NETWORK_ERROR_STATUS, "network_error", "network failure");
  }
  if (!response.ok) throw await toApiError(response);
  if (response.status === NO_CONTENT) return undefined as T;
  return (await response.json()) as T;
}

let refreshInFlight: Promise<void> | null = null;

/** One refresh shared by every request that found its access token expired. */
function refreshSession(): Promise<void> {
  refreshInFlight ??= send<unknown>(REFRESH_PATH, { method: "POST" })
    .then(() => undefined)
    .finally(() => { refreshInFlight = null; });
  return refreshInFlight;
}

/** The access token lives 15 minutes and its cookie 30 days, so an expired one still
 *  arrives and the backend says `token_expired`: refresh once, then replay. The cookies
 *  are HttpOnly and same-origin — no token is ever visible to this code. */
async function request<T>(path: string, init: RequestInit): Promise<T> {
  try {
    return await send<T>(path, init);
  } catch (error) {
    const expired = error instanceof ApiError && error.code === TOKEN_EXPIRED && path !== REFRESH_PATH;
    if (!expired) throw error;
    try { await refreshSession(); } catch { throw error; } // the session is over: report the original failure
    return send<T>(path, init);
  }
}

const withJson = (method: string, body: unknown, signal?: AbortSignal): RequestInit =>
  body === undefined ? { method, signal } : { method, body: JSON.stringify(body), headers: { "content-type": "application/json" }, signal };

export function apiGet<T>(path: string, params: QueryParams = {}, signal?: AbortSignal): Promise<T> {
  return request<T>(`${path}${buildQuery(params)}`, { method: "GET", signal });
}

export function apiPost<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, withJson("POST", body, signal));
}

export function apiPut<T = void>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, withJson("PUT", body, signal));
}

export function apiDelete<T = void>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { method: "DELETE", signal });
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bun test src/lib/api/client.test.ts`
Expected: PASS — the 5 existing tests and the 6 new ones.

- [ ] **Step 5: Lint, type-check and commit**

```bash
bun run lint && bunx tsc --noEmit
cd .. && git add frontend/src/lib/api/client.ts frontend/src/lib/api/client.test.ts
git commit -m "feat(frontend): add PUT/DELETE helpers and silent token refresh"
```

---

### Task 12: Account types and pure helpers (`lib/account.ts`)

**Files:**
- Create: `frontend/src/lib/account.ts`
- Modify: `frontend/src/lib/api/types.ts`, `frontend/src/lib/types.ts`
- Test: `frontend/src/lib/account.test.ts`

**Interfaces:**
- Consumes: backend schemas from Tasks 6–7 (mirrored by hand — change both together).
- Produces:
  - `lib/api/types.ts`: `UserRole`, `UserRead`, `AuthRequest`, `PriceAlertCreate`, `PriceAlertRead`, `ImportRequest`, `AccountState`
  - `lib/types.ts`: `PriceAlert` gains `id?: string`
  - `lib/account.ts`: `MIN_PASSWORD_LENGTH = 8`, `MAX_PASSWORD_LENGTH = 128`, `AUTH_ERROR_TEXT: Record<string, string>`, `toggleSavedId(saved, id) -> { saved, wasSaved }`, `withAlertId(alerts, local, id) -> PriceAlert[]`, `removeAlertById(alerts, id) -> { alerts, removed }`, `clearAccount(state) -> state`, `toAlertBody(alert) -> PriceAlertCreate`, `toPriceAlert(read) -> PriceAlert`

- [ ] **Step 1: Add the types**

Append to `frontend/src/lib/api/types.ts`:

```ts
/** Mirrors backend `schemas/auth.py` and `schemas/account.py`. */
export type UserRole = "user" | "admin";
export interface UserRead { id: string; email: string; role: UserRole; created_at: string; }
export interface AuthRequest { email: string; password: string; }
export interface PriceAlertCreate { title: string; threshold: number; params: SearchParams; }
export interface PriceAlertRead extends PriceAlertCreate { id: string; created_at: string; }
export interface ImportRequest { saved: string[]; alerts: PriceAlertCreate[]; }
export interface AccountState { saved: string[]; alerts: PriceAlertRead[]; }
```

In `frontend/src/lib/types.ts`, replace the `PriceAlert` line with:

```ts
/** `id` is present once the server has stored the alert; an optimistic one has none yet. */
export interface PriceAlert { id?: string; title: string; params: SearchParams; threshold: number; }
```

- [ ] **Step 2: Write the failing tests**

Create `frontend/src/lib/account.test.ts`:

```ts
import { expect, test } from "bun:test";
import { AUTH_ERROR_TEXT, clearAccount, removeAlertById, toAlertBody, toPriceAlert, toggleSavedId, withAlertId } from "./account";
import type { PriceAlert } from "./types";

const alert = (title: string, id?: string): PriceAlert => ({ id, title, threshold: 500_000_000, params: { q: title } });

test("toggleSavedId adds, removes, and toggling twice restores the list (the revert path)", () => {
  const added = toggleSavedId(["a"], "b");
  expect(added).toEqual({ saved: ["a", "b"], wasSaved: false });
  const reverted = toggleSavedId(added.saved, "b");
  expect(reverted).toEqual({ saved: ["a"], wasSaved: true });
});

test("withAlertId patches the server id onto the optimistic alert only", () => {
  const local = alert("۲۰۶");
  const other = alert("دنا", "srv-1");
  const patched = withAlertId([other, local], local, "srv-2");
  expect(patched.map((a) => a.id)).toEqual(["srv-1", "srv-2"]);
  expect(local.id).toBeUndefined(); // never mutates
});

test("removeAlertById returns what it removed so a failed delete can restore it", () => {
  const kept = alert("دنا", "srv-1");
  const gone = alert("۲۰۶", "srv-2");
  expect(removeAlertById([kept, gone], "srv-2")).toEqual({ alerts: [kept], removed: gone });
  expect(removeAlertById([kept], "missing")).toEqual({ alerts: [kept], removed: undefined });
});

test("logout clears saved and alerts and keeps compare", () => {
  const state = { compare: ["x", "y"], saved: ["a"], alerts: [alert("۲۰۶", "srv-1")] };
  expect(clearAccount(state)).toEqual({ compare: ["x", "y"], saved: [], alerts: [] });
});

test("alerts convert to and from the API shapes without the id leaking into a create body", () => {
  expect(toAlertBody(alert("۲۰۶", "srv-1"))).toEqual({ title: "۲۰۶", threshold: 500_000_000, params: { q: "۲۰۶" } });
  const read = { id: "srv-1", title: "۲۰۶", threshold: 1, params: {}, created_at: "2026-09-20T00:00:00Z" };
  expect(toPriceAlert(read)).toEqual({ id: "srv-1", title: "۲۰۶", threshold: 1, params: {} });
});

test("every auth error code the dialog handles has Persian copy", () => {
  expect(Object.keys(AUTH_ERROR_TEXT).sort()).toEqual(["account_disabled", "email_taken", "invalid_credentials"]);
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `bun test src/lib/account.test.ts`
Expected: FAIL — `Cannot find module './account'`.

- [ ] **Step 4: Implement**

Create `frontend/src/lib/account.ts`:

```ts
import type { PriceAlertCreate, PriceAlertRead } from "./api/types";
import type { PriceAlert } from "./types";

/** Mirror backend `schemas/auth.py`. */
export const MIN_PASSWORD_LENGTH = 8;
export const MAX_PASSWORD_LENGTH = 128;

/** Keyed by `ApiError.code` — never by message text. Anything absent falls back to the shared banner copy. */
export const AUTH_ERROR_TEXT: Record<string, string> = {
  invalid_credentials: "ایمیل یا رمز اشتباه است",
  email_taken: "این ایمیل قبلاً ثبت شده؛ وارد شو",
  account_disabled: "حساب غیرفعال شده",
};

export interface AccountLists { saved: string[]; alerts: PriceAlert[]; }

/** Toggling is its own inverse, so a failed sync reverts by toggling again. */
export function toggleSavedId(saved: string[], id: string): { saved: string[]; wasSaved: boolean } {
  const wasSaved = saved.includes(id);
  return { saved: wasSaved ? saved.filter((x) => x !== id) : [...saved, id], wasSaved };
}

export const withAlertId = (alerts: PriceAlert[], local: PriceAlert, id: string): PriceAlert[] =>
  alerts.map((a) => (a === local ? { ...a, id } : a));

export function removeAlertById(alerts: PriceAlert[], id: string): { alerts: PriceAlert[]; removed: PriceAlert | undefined } {
  return { alerts: alerts.filter((a) => a.id !== id), removed: alerts.find((a) => a.id === id) };
}

/** Logout: the next person on this device must not inherit the account's lists. Compare is a local scratchpad and stays. */
export const clearAccount = <T extends AccountLists>(state: T): T => ({ ...state, saved: [], alerts: [] });

export const toAlertBody = ({ title, threshold, params }: PriceAlert): PriceAlertCreate => ({ title, threshold, params });
export const toPriceAlert = ({ id, title, threshold, params }: PriceAlertRead): PriceAlert => ({ id, title, threshold, params });
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `bun test src/lib/account.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 6: Lint, type-check and commit**

```bash
bun run lint && bunx tsc --noEmit
cd .. && git add frontend/src/lib/account.ts frontend/src/lib/account.test.ts frontend/src/lib/api/types.ts frontend/src/lib/types.ts
git commit -m "feat(frontend): add account types and pure helpers"
```

---

### Task 13: Real sessions in `AppState`, the auth dialog, header and alerts

These change together: `AppState` removes `toggleLogin`, which `Header` and `AlertsDropdown` call, so the type-check only passes once all three are updated.

**Files:**
- Create: `frontend/src/components/AuthDialog.tsx`, `frontend/src/components/AuthDialog.module.css`
- Modify: `frontend/src/state/AppState.tsx`, `frontend/src/components/Header.tsx`, `frontend/src/components/Header.module.css`, `frontend/src/components/AlertsDropdown.tsx`, `frontend/src/app/layout.tsx`

**Interfaces:**
- Consumes: `apiGet`, `apiPost`, `apiPut`, `apiDelete` (Task 11); everything from `lib/account.ts` and the new API types (Task 12); `errorText`, `SERVICE_UNAVAILABLE` from `components/ErrorBanner.tsx` (existing).
- Produces on `useAppState()`: `user: UserRead | null`, `loggedIn: boolean` (derived), `authReady: boolean`, `authOpen: boolean`, `login(email, password): Promise<void>`, `register(email, password): Promise<void>`, `logout(): Promise<void>`, `openAuth(): void`, `closeAuth(): void`, `removeAlert(id: string): void`. `toggleLogin` is gone. `toggleSaved(id)` and `addAlert(alert)` keep their signatures.

There is no component-test setup in this repo (`bun test` covers `lib/` only), so the logic under test lives in `lib/account.ts` (Task 12) and this task is verified by `tsc`, ESLint and the smoke step (Task 14).

- [ ] **Step 1: Update the imports, types and storage shape in `AppState.tsx`**

Replace the three import lines for the API client and types with:

```ts
import { clearAccount, removeAlertById, toAlertBody, toPriceAlert, toggleSavedId, withAlertId } from "@/lib/account";
import { ApiError, apiDelete, apiGet, apiPost, apiPut } from "@/lib/api/client";
import type { AccountState, AssistantRequest, AssistantResponse, PriceAlertRead, UserRead } from "@/lib/api/types";
import type { ChatMessage, PriceAlert } from "@/lib/types";
```

Add below `CHAT_UNAVAILABLE`:

```ts
const SYNC_FAILED = "ذخیره نشد؛ دوباره امتحان کن";
type AuthPath = "/auth/login" | "/auth/register";
```

Replace the `Persisted` / `EMPTY` lines with:

```ts
// `loggedIn` used to live here as a fake flag; an old stored value is simply ignored.
interface Persisted { compare: string[]; saved: string[]; alerts: PriceAlert[]; }
const EMPTY: Persisted = { compare: [], saved: [], alerts: [] };
```

In `readPersisted`, delete the `loggedIn: …` line from the returned object.

Replace the `AppStateValue` interface with:

```ts
export interface AppStateValue extends Persisted {
  user: UserRead | null; loggedIn: boolean; authReady: boolean; authOpen: boolean;
  bellOpen: boolean; chatOpen: boolean; chatMessages: ChatMessage[]; chatBusy: boolean; avatarAnimation: AvatarAnimation; toast: string;
  toggleCompare(id: string): void; removeFromCompare(id: string): void; toggleSaved(id: string): void;
  addAlert(alert: PriceAlert): void; removeAlert(id: string): void;
  login(email: string, password: string): Promise<void>; register(email: string, password: string): Promise<void>; logout(): Promise<void>;
  openAuth(): void; closeAuth(): void;
  setBellOpen(open: boolean): void; setChatOpen(open: boolean): void; sendChat(text: string): void; showToast(text: string): void;
}
```

- [ ] **Step 2: Add the session state and the "who am I" load**

Inside `AppStateProvider`, after the `const [toast, setToast] = useState("");` line add:

```ts
  const [user, setUser] = useState<UserRead | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const userRef = useRef<UserRead | null>(null); // callbacks read this, so they stay stable
```

After the effect that writes `localStorage`, add:

```ts
  const adoptSession = useCallback((me: UserRead | null) => { userRef.current = me; setUser(me); }, []);
  const adoptAccount = useCallback((state: AccountState) => {
    commitPersisted(persistedRef, setPersisted, (p) => ({ next: { ...p, saved: state.saved, alerts: state.alerts.map(toPriceAlert) }, result: undefined }));
  }, []);

  // Who am I? Server Components stay anonymous, so the session is discovered here.
  useEffect(() => {
    if (!hydrated) return;
    let cancelled = false;
    const load = async () => {
      const me = await apiGet<UserRead>("/me");
      const [saved, alerts] = await Promise.all([apiGet<string[]>("/me/saved"), apiGet<PriceAlertRead[]>("/me/alerts")]);
      if (cancelled) return;
      adoptSession(me);
      adoptAccount({ saved, alerts });
    };
    // A 401 is the normal answer for a visitor, and an unreachable API leaves them
    // anonymous too: either way the locally stored `saved` list keeps working.
    load().catch(() => undefined).finally(() => { if (!cancelled) setAuthReady(true); });
    return () => { cancelled = true; };
  }, [hydrated, adoptSession, adoptAccount]);
```

- [ ] **Step 3: Make `toggleSaved`, `addAlert` and `removeAlert` sync optimistically**

Replace the existing `toggleSaved`, `addAlert` and `removeAlert` callbacks with:

```ts
  const flipSaved = useCallback((id: string): boolean =>
    commitPersisted(persistedRef, setPersisted, (p) => {
      const { saved, wasSaved } = toggleSavedId(p.saved, id);
      return { next: { ...p, saved }, result: wasSaved };
    }), []);

  const toggleSaved = useCallback((id: string) => {
    const wasSaved = flipSaved(id);
    showToast(wasSaved ? "از نشان‌ها حذف شد" : "نشان شد");
    if (!userRef.current) return; // anonymous: the list lives in this browser only
    const sync = wasSaved ? apiDelete(`/me/saved/${id}`) : apiPut(`/me/saved/${id}`);
    sync.catch(() => { flipSaved(id); showToast(SYNC_FAILED); });
  }, [flipSaved, showToast]);

  const addAlert = useCallback((alert: PriceAlert) => {
    if (!userRef.current) { setAuthOpen(true); showToast("برای هشدار قیمت اول وارد شو"); return; }
    commitPersisted(persistedRef, setPersisted, (p) => ({ next: { ...p, alerts: [...p.alerts, alert] }, result: undefined }));
    showToast("هشدار قیمت ذخیره شد");
    apiPost<PriceAlertRead>("/me/alerts", toAlertBody(alert))
      .then((stored) => commitPersisted(persistedRef, setPersisted, (p) => ({ next: { ...p, alerts: withAlertId(p.alerts, alert, stored.id) }, result: undefined })))
      .catch(() => {
        commitPersisted(persistedRef, setPersisted, (p) => ({ next: { ...p, alerts: p.alerts.filter((a) => a !== alert) }, result: undefined }));
        showToast(SYNC_FAILED);
      });
  }, [showToast]);

  const removeAlert = useCallback((id: string) => {
    const removed = commitPersisted(persistedRef, setPersisted, (p) => {
      const result = removeAlertById(p.alerts, id);
      return { next: { ...p, alerts: result.alerts }, result: result.removed };
    });
    if (!removed) return;
    apiDelete(`/me/alerts/${id}`).catch(() => {
      commitPersisted(persistedRef, setPersisted, (p) => ({ next: { ...p, alerts: [...p.alerts, removed] }, result: undefined }));
      showToast(SYNC_FAILED);
    });
  }, [showToast]);
```

- [ ] **Step 4: Replace `toggleLogin` with real sign-in and logout**

Delete the `toggleLogin` callback and add in its place:

```ts
  const signIn = useCallback(async (path: AuthPath, email: string, password: string) => {
    adoptSession(await apiPost<UserRead>(path, { email, password })); // failures propagate to the dialog
    setAuthOpen(false);
    showToast("خوش اومدی!");
    const { saved, alerts } = persistedRef.current;
    try {
      adoptAccount(await apiPost<AccountState>("/me/import", { saved, alerts: alerts.map(toAlertBody) }));
    } catch {
      // ponytail: a failed import keeps this browser's lists until the next reload, which
      // replaces them with the server copy. Add a retry queue if that loss ever matters.
      showToast(SYNC_FAILED);
    }
  }, [adoptSession, adoptAccount, showToast]);

  const login = useCallback((email: string, password: string) => signIn("/auth/login", email, password), [signIn]);
  const register = useCallback((email: string, password: string) => signIn("/auth/register", email, password), [signIn]);

  const logout = useCallback(async () => {
    try { await apiPost<void>("/auth/logout", {}); } catch { showToast("خروج انجام نشد؛ دوباره امتحان کن"); return; }
    adoptSession(null);
    commitPersisted(persistedRef, setPersisted, (p) => ({ next: clearAccount(p), result: undefined }));
    setBellOpen(false);
    showToast("خارج شدی");
  }, [adoptSession, showToast]);

  const openAuth = useCallback(() => { setBellOpen(false); setAuthOpen(true); }, []);
  const closeAuth = useCallback(() => setAuthOpen(false), []);
```

Replace the `value` memo with:

```ts
  const value = useMemo<AppStateValue>(() => ({
    ...persisted, user, loggedIn: user !== null, authReady, authOpen, bellOpen, chatOpen, chatMessages, chatBusy, avatarAnimation, toast,
    toggleCompare, removeFromCompare, toggleSaved, addAlert, removeAlert, login, register, logout, openAuth, closeAuth, setBellOpen, setChatOpen, sendChat, showToast,
  }), [persisted, user, authReady, authOpen, bellOpen, chatOpen, chatMessages, chatBusy, avatarAnimation, toast, toggleCompare, removeFromCompare, toggleSaved, addAlert, removeAlert, login, register, logout, openAuth, closeAuth, sendChat, showToast]);
```

- [ ] **Step 5: Create the auth dialog**

Create `frontend/src/components/AuthDialog.tsx`:

```tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { AUTH_ERROR_TEXT, MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH } from "@/lib/account";
import { ApiError } from "@/lib/api/client";
import { useAppState } from "@/state/AppState";
import { errorText, SERVICE_UNAVAILABLE } from "./ErrorBanner";
import styles from "./AuthDialog.module.css";

type Mode = "login" | "register";
const TABS: { mode: Mode; label: string }[] = [{ mode: "login", label: "ورود" }, { mode: "register", label: "ثبت‌نام" }];

/** Branches on `ApiError.code`; a 422 shows the backend's own message, the rest the shared banner copy. */
const messageFor = (error: unknown): string =>
  error instanceof ApiError ? AUTH_ERROR_TEXT[error.code] ?? errorText(error) : SERVICE_UNAVAILABLE;

export function AuthDialog() {
  const { authOpen, closeAuth, login, register } = useAppState();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [mode, setMode] = useState<Mode>("login");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Native <dialog>: showModal() brings the focus trap, Escape and the backdrop for free.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (authOpen && !dialog.open) dialog.showModal();
    if (!authOpen && dialog.open) dialog.close();
  }, [authOpen]);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget; // gone after the first await
    const data = new FormData(form);
    setBusy(true);
    setError("");
    try {
      await (mode === "login" ? login : register)(String(data.get("email")), String(data.get("password")));
      form.reset();
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "email_taken") setMode("login");
      setError(messageFor(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <dialog ref={dialogRef} className={styles.dialog} onClose={closeAuth} aria-labelledby="auth-title">
      <div className={styles.head}>
        <h2 id="auth-title" className={styles.title}>حساب کاربری</h2>
        <button type="button" className={styles.close} onClick={closeAuth} aria-label="بستن">×</button>
      </div>
      <div className={styles.tabs} role="tablist">
        {TABS.map((tab) => (
          <button key={tab.mode} type="button" role="tab" aria-selected={mode === tab.mode}
            className={`${styles.tab} ${mode === tab.mode ? styles.tabActive : ""}`}
            onClick={() => { setMode(tab.mode); setError(""); }}>{tab.label}</button>
        ))}
      </div>
      <form className={styles.form} onSubmit={submit}>
        <label className={styles.field}>ایمیل
          <input name="email" type="email" required autoComplete="email" dir="ltr" />
        </label>
        <label className={styles.field}>رمز عبور
          <input name="password" type="password" required dir="ltr"
            minLength={mode === "register" ? MIN_PASSWORD_LENGTH : undefined} maxLength={MAX_PASSWORD_LENGTH}
            autoComplete={mode === "register" ? "new-password" : "current-password"} />
        </label>
        {error && <p className={styles.error} role="alert">{error}</p>}
        <button type="submit" className={styles.submit} disabled={busy}>{mode === "login" ? "ورود" : "ساخت حساب"}</button>
      </form>
    </dialog>
  );
}
```

Create `frontend/src/components/AuthDialog.module.css`:

```css
.dialog {
  width: min(380px, calc(100vw - 32px));
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  color: var(--ink);
  box-shadow: 0 12px 32px rgba(23, 32, 51, 0.12);
}

.dialog::backdrop {
  background: rgba(23, 32, 51, 0.45);
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
}

.close {
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 8px;
  background: var(--fill);
  color: var(--ink-2);
  font-size: 18px;
}

.tabs {
  display: flex;
  gap: 4px;
  padding: 4px;
  margin-bottom: 16px;
  border-radius: 10px;
  background: var(--fill);
}

.tab {
  flex: 1;
  height: 34px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  font-size: 13px;
  font-weight: 600;
}

.tabActive {
  background: var(--surface);
  color: var(--ink);
}

.form {
  display: grid;
  gap: 12px;
}

.field {
  display: grid;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2);
}

.field input {
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  font: inherit;
  font-weight: 400;
}

.field input:focus-visible {
  outline: 2px solid var(--red);
  outline-offset: 1px;
}

.error {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--red-soft);
  color: var(--red-ink);
  font-size: 13px;
}

.submit {
  height: 40px;
  border: 0;
  border-radius: 8px;
  background: var(--red);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
}

.submit:hover {
  background: var(--red-dark);
}

.submit:disabled {
  opacity: 0.6;
}
```

In `frontend/src/app/layout.tsx`, import it (`import { AuthDialog } from "@/components/AuthDialog";`, in alphabetical position before `ChatPanel`) and render it after `<ChatPanel />`:

```tsx
          <ChatPanel />
          <AuthDialog />
          <Toast />
```

- [ ] **Step 6: Wire the header**

In `frontend/src/components/Header.tsx`, replace the `useAppState()` destructuring with:

```tsx
  const { compare, alerts, user, loggedIn, bellOpen, chatOpen, setBellOpen, setChatOpen, openAuth, logout } = useAppState();
```

and replace the `{loggedIn ? … : …}` block with:

```tsx
            {user
              ? (
                <details className={styles.userMenu}>
                  <summary className={styles.user} title={user.email}>
                    <span className={styles.userBadge}>{user.email.charAt(0).toUpperCase()}</span>
                  </summary>
                  <div className={styles.menu}>
                    <div className={styles.menuEmail} dir="ltr">{user.email}</div>
                    <button type="button" className={styles.menuItem} onClick={logout}>خروج</button>
                  </div>
                </details>
              )
              : <button className={styles.login} onClick={openAuth}>ورود</button>}
```

(`loggedIn` is still used by the bell dot above it.)

Append to `frontend/src/components/Header.module.css`, before the `@media (max-width: 767px)` block:

```css
/* Native <details>: the menu opens and closes with no JavaScript. */
.userMenu {
  position: relative;
}

.userMenu > summary {
  list-style: none;
  cursor: pointer;
}

.userMenu > summary::-webkit-details-marker {
  display: none;
}

.menu {
  position: absolute;
  top: 46px;
  left: 0;
  min-width: 200px;
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  box-shadow: 0 12px 32px rgba(23, 32, 51, 0.12);
}

.menuEmail {
  padding: 6px 8px 10px;
  color: var(--muted);
  font-size: 12px;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
}

.menuItem {
  width: 100%;
  height: 34px;
  border: 0;
  border-radius: 8px;
  background: var(--fill);
  color: var(--ink);
  font-size: 13px;
  font-weight: 600;
}
```

In the existing `.user` rule, change `padding: 0 6px 0 12px;` to `padding: 0 6px;` — the name span next to the badge is gone.

- [ ] **Step 7: Wire the alerts dropdown**

In `frontend/src/components/AlertsDropdown.tsx`:

- Replace the destructuring with `const { alerts, loggedIn, removeAlert, openAuth } = useAppState();`
- Change the login button to `onClick={openAuth}`.
- Replace the row's remove button with one keyed by the server id (an optimistic alert has no id for a moment and cannot be removed yet):

```tsx
          <button className={styles.remove} disabled={!a.id} onClick={() => a.id && removeAlert(a.id)} title="حذف">×</button>
```

- Change the row key from `key={i}` to `key={a.id ?? i}`.

- [ ] **Step 8: Verify**

Run (from `frontend/`):
```bash
bun run lint && bunx tsc --noEmit && bun test
grep -rn "toggleLogin" src || echo "no toggleLogin left"
```
Expected: lint and `tsc` clean, all tests pass, and `no toggleLogin left`.

Then check it in a browser against the dev stack (`./.scripts/dev.sh`, open `http://localhost`): «ورود» opens the dialog; registering closes it and shows the email's first letter in the header; a listing saved while logged in is still saved after a reload; «خروج» clears it; logging in with a wrong password shows «ایمیل یا رمز اشتباه است»; Escape closes the dialog.

- [ ] **Step 9: Commit**

```bash
cd .. && git add frontend/src/state/AppState.tsx frontend/src/components/AuthDialog.tsx frontend/src/components/AuthDialog.module.css frontend/src/components/Header.tsx frontend/src/components/Header.module.css frontend/src/components/AlertsDropdown.tsx frontend/src/app/layout.tsx
git commit -m "feat(frontend): replace the fake login with real accounts"
```

---

### Task 14: Smoke step and final verification

**Files:**
- Modify: `.scripts/smoke.sh`

- [ ] **Step 1: Add the "account" step**

In `.scripts/smoke.sh`, insert before the final `echo` / `echo "SMOKE PASSED…"` lines:

```bash
step "account"
SMOKE_EMAIL="smoke+$(date +%s)@example.com"
SMOKE_PASSWORD="smoke-$(date +%s)-pass" # generated per run: no credential literal in the repo
BOOKMARK="button[title='نشان‌کردن']"
"${AB[@]}" open "$BASE_URL/results?q=$(encode "$QUERY")"
"${AB[@]}" wait "a[href^='/listing/']"
LISTING_URL="$BASE_URL$(first_href "a[href^='/listing/']")"
"${AB[@]}" find role button click --name "ورود"
"${AB[@]}" find role tab click --name "ثبت‌نام"
"${AB[@]}" find label "ایمیل" fill "$SMOKE_EMAIL"
"${AB[@]}" find label "رمز عبور" fill "$SMOKE_PASSWORD"
"${AB[@]}" press Enter
"${AB[@]}" wait "summary[title='$SMOKE_EMAIL']"
echo "ok: registered and logged in"
"${AB[@]}" open "$LISTING_URL"
"${AB[@]}" wait "$BOOKMARK"
"${AB[@]}" click "$BOOKMARK"
"${AB[@]}" wait "$BOOKMARK[aria-pressed='true']"
"${AB[@]}" open "$LISTING_URL" # a fresh load: the saved state can only come from the server
"${AB[@]}" wait "$BOOKMARK[aria-pressed='true']"
echo "ok: the saved listing survived a reload"
"${AB[@]}" click "summary[title='$SMOKE_EMAIL']"
"${AB[@]}" find role button click --name "خروج"
"${AB[@]}" wait "$BOOKMARK[aria-pressed='false']"
echo "ok: logout cleared the saved listing"
```

- [ ] **Step 2: Run the smoke script against the running stack**

```bash
docker compose -f .docker/compose.yml -f .docker/compose.dev.yml up -d --build
./.scripts/smoke.sh
```
Expected: every earlier step still prints `ok:` and the run ends with `SMOKE PASSED against http://localhost`. If an `agent-browser` subcommand in the new step is rejected, run `agent-browser --help` and adapt that one line — the assertions (selector waits) are what matter.

- [ ] **Step 3: Run the Definition of Done (CLAUDE.md §14)**

```bash
(cd backend && uv run ruff check . && uv run black --check . && uv run pytest -q)
(cd frontend && bun run lint && bunx tsc --noEmit && bun test)
pre-commit run --all-files
docker compose -f .docker/compose.yml build
./.scripts/sonar.sh
```
Expected: all green; the Sonar gate passes (new-code coverage ≥ 80 %). `pre-commit` includes Gitleaks — it must report no leaks (`JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` are empty in `example.env`).

Then tick the spec's §8 security checklist item by item against the code; each item names the test that proves it:

| Checklist item | Proof |
|---|---|
| Passwords never logged; `SecretStr` everywhere | `test_passwords_never_appear_in_repr` |
| Cookie flags and refresh path | `test_register_logs_in_and_sets_both_cookies` |
| Expired token + live cookie → `token_expired` | `test_an_expired_access_token_says_token_expired` |
| JSON-only mutations, no CORS | `grep -rn "CORSMiddleware" backend` prints nothing |
| Identical credential failures | `test_unknown_email_and_wrong_password_fail_identically` |
| `/auth/*` rate-limited | Task 10 Step 3 |
| Empty secrets in `example.env` | Gitleaks in `pre-commit` |
| `algorithms=["HS256"]` pinned | `test_an_unsigned_token_is_rejected` |

- [ ] **Step 4: Refresh the code graph and commit**

```bash
graphify update .
git add .scripts/smoke.sh
git commit -m "test(smoke): cover sign-up, a server-side save and logout"
```

`graphify-out/` is untracked in this repo — do not stage it.

---

## Out of scope (Spec 5 — admin panel)

Do not build these here: the admin UI and its CRUD endpoints, a `/login` page with redirect, the «پنل مدیریت» menu link, user management (disable, promote, reset password), and a change-password form. `require_admin` and `users.token_version` exist so Spec 5 can plug into them.
