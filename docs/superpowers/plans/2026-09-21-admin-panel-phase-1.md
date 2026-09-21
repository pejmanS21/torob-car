# Admin Panel — Phase 1 (Foundation + User Administration) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the guarded `/api/v1/admin` surface and the `/admin` UI, with full user administration and an audit trail behind a hardened admin session.

**Architecture:** Tokens gain an `auth_at` claim recording the last real password entry; `refresh` copies it through untouched so a silently refreshing session never renews admin freshness. Two dependencies read it — `require_admin` (60 min) guards the whole admin router, `require_fresh_admin` (5 min) guards destructive routes. Every admin mutation writes an `admin_audit` row in the same transaction as the change.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic, PyJWT; Next.js 16 App Router, TypeScript strict, Bun.

**Spec:** `docs/superpowers/specs/2026-09-21-torobcar-admin-panel-design.md` — read §3 (privilege boundary), §4 (data model), §5 (API), §8 (frontend), §10 (security checklist) before starting. This plan implements **Phase 1 only** (spec §12).

## Global Constraints

- Branch: `feat/admin-panel`, already checked out off `feat/accounts-auth`. Never commit to `main`.
- **NEVER `git add -A` or `git add .`** — the tree has untracked directories (`graphify-out/`, `brag-output/`, `prototype/`, `output/`). Commit with an explicit pathspec: `git commit -m "msg" -- <paths>`. A pathspec-only commit cannot include brand-new untracked files, so first `git add` ONLY the exact new filenames, verify with `git status --short`, then commit with the full pathspec.
- Backend commands run from `backend/`, frontend from `frontend/`. `uv` and `bun` only — never `pip`/`npm`/`yarn`/`pnpm`. Never hand-edit `uv.lock` or `bun.lock`.
- The throwaway Postgres for pytest is at `127.0.0.1:54329`; start it once with `./.scripts/test-db.sh` if it is not already up. Mark DB-backed test modules `pytestmark = pytest.mark.db`.
- Full type hints; functions ≤ ~30 lines; no business logic in endpoints; **no SQLAlchemy outside `repositories/`**; config read only through `core/config.py`.
- Before every backend commit: `uv run ruff check . --fix && uv run black .` clean. Before every frontend commit: `bun run lint && bunx tsc --noEmit` clean.
- **Exact values (spec §3.3):** `ADMIN_SESSION_MINUTES=60`, `ADMIN_REAUTH_MINUTES=5`. Access token 15 min, refresh 30 days, both cookies `Max-Age` 30 days — unchanged from Spec 4.
- **Error codes** (the frontend branches on these, never on message text): `admin_reauth_required` (403), `cannot_modify_self` (409), `last_admin` (409), plus Spec 4's existing set.
- Tests never hash at production cost — use `fast_auth_settings()` from `tests/support.py`.
- Test emails use `@example.com`; pydantic's `EmailStr` rejects `.test` domains.
- Deliberate simplifications get a `# ponytail:` comment naming the ceiling and upgrade path.
- Commit messages are conventional commits ending with:
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`

## File Structure

**Backend — created**

| File | Responsibility |
|---|---|
| `backend/models/admin_audit.py` | The append-only audit ORM row |
| `backend/db/migrations/versions/0004_admin_audit.py` | Creates `admin_audit` |
| `backend/repositories/admin_audit_repository.py` | Append + paginated read; no update/delete path exists |
| `backend/repositories/admin_user_repository.py` | Admin-side user queries: search, counts, the active-admin lock |
| `backend/schemas/admin.py` | `AdminUserRow`, `AdminUserDetail`, `AdminUserUpdate`, `AdminPasswordReset`, `AuditRow`, `AdminStats` |
| `backend/services/audit_recorder.py` | `AuditRecorder` — the one way an audit row is written |
| `backend/services/admin_user_service.py` | Lockout guards + audited user mutations |
| `backend/api/v1/admin/__init__.py`, `router.py`, `users.py`, `audit.py`, `stats.py` | Thin controllers; `require_admin` mounted router-level |

**Backend — modified:** `core/security.py`, `core/config.py`, `enums.py`, `errors.py`, `models/__init__.py`, `services/auth_service.py`, `dependencies/providers.py`, `api/v1/router.py`, `api/v1/endpoints/auth.py`, `example.env`.

**Frontend — created:** `src/app/login/page.tsx`, `src/app/admin/layout.tsx`, `src/app/admin/page.tsx`, `src/app/admin/users/page.tsx`, `src/app/admin/users/[id]/page.tsx`, `src/components/ReauthPrompt.tsx` (+ CSS modules), `src/lib/admin.ts` (+ test).
**Frontend — modified:** `src/lib/api/types.ts`, `src/lib/api/client.ts`, `src/components/Header.tsx`, `src/state/AppState.tsx`.

---

### Task 1: The `auth_at` claim in the token layer

**Files:**
- Modify: `backend/core/security.py`
- Test: `backend/tests/core/test_security.py`

**Interfaces:**
- Produces: `TokenClaims(user_id: uuid.UUID, token_version: int, role: UserRole | None, auth_at: int)`; `encode_token` writes claim `"at"`; `decode_token` reads it, defaulting a **missing** claim to `0`; `issue_token_pair` carries `auth_at` into both tokens unchanged.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/core/test_security.py`:

```python
def test_auth_at_round_trips_through_a_token() -> None:
    claims = TokenClaims(uuid.UUID(int=1), 3, UserRole.ADMIN, auth_at=1_700_000_000)
    token = encode_token(claims, TokenType.ACCESS, SECRET, ONE_MINUTE)
    assert decode_token(token, SECRET, TokenType.ACCESS).auth_at == 1_700_000_000


def test_a_token_minted_before_this_feature_decodes_as_stale() -> None:
    """No `at` claim means the token predates admin hardening. Defaulting to 0 fails
    every freshness window, which forces exactly one re-authentication."""
    payload = {"sub": str(uuid.UUID(int=1)), "ver": 0, "typ": "access", "exp": 9999999999}
    legacy = jwt.encode(payload, SECRET, algorithm="HS256")
    assert decode_token(legacy, SECRET, TokenType.ACCESS).auth_at == 0


def test_both_tokens_in_a_pair_carry_the_same_auth_at() -> None:
    claims = TokenClaims(uuid.UUID(int=1), 0, UserRole.ADMIN, auth_at=1_700_000_000)
    pair = issue_token_pair(claims, SECRET, ONE_MINUTE, ONE_MINUTE)
    access = decode_token(pair.access, SECRET, TokenType.ACCESS)
    refresh = decode_token(pair.refresh, SECRET, TokenType.REFRESH)
    assert access.auth_at == refresh.auth_at == 1_700_000_000
    assert refresh.role is None  # unchanged from spec 4


def test_a_non_numeric_auth_at_is_rejected() -> None:
    payload = {"sub": str(uuid.UUID(int=1)), "ver": 0, "typ": "access",
               "exp": 9999999999, "at": "not-a-number"}
    forged = jwt.encode(payload, SECRET, algorithm="HS256")
    with pytest.raises(NotAuthenticatedError):
        decode_token(forged, SECRET, TokenType.ACCESS)
```

The existing tests construct `TokenClaims(...)` positionally with three arguments and will now fail to build — that is expected and is part of this step. Update every existing construction in this file to pass `auth_at=0` (or any fixed int), including the module-level `CLAIMS` constant and the helpers inside `test_token_types_are_not_interchangeable` and `test_a_signed_token_with_malformed_claims_is_not_authenticated`.

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `backend/`): `uv run pytest tests/core/test_security.py -q`
Expected: FAIL — `TypeError: TokenClaims.__init__() got an unexpected keyword argument 'auth_at'`.

- [ ] **Step 3: Implement**

In `backend/core/security.py`:

Add the field to the dataclass:

```python
@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    token_version: int
    role: UserRole | None
    auth_at: int  # unix seconds of the last real password entry; 0 = never/stale
```

In `encode_token`, add the claim to the payload dict (after `"typ"`):

```python
        "at": claims.auth_at,
```

In `_claims_from`, read it with a default so pre-feature tokens decode rather than 500:

```python
def _claims_from(payload: dict[str, Any]) -> TokenClaims:
    role = payload.get("role")
    try:
        return TokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            token_version=int(payload["ver"]),
            role=UserRole(role) if role is not None else None,
            # A token minted before admin hardening has no "at" claim. 0 fails every
            # freshness window, costing one re-authentication — never a 500.
            auth_at=int(payload.get("at", 0)),
        )
    except (TypeError, ValueError) as error:  # a signed token with malformed claims
        raise NotAuthenticatedError() from error
```

`issue_token_pair` needs no change: `replace(claims, role=None)` already carries `auth_at` through.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/core/test_security.py -q`
Expected: PASS (16 tests — the 12 existing plus 4 new).

- [ ] **Step 5: Commit**

```bash
uv run ruff check . --fix && uv run black .
cd .. && git commit -m "feat(backend): add an auth_at freshness claim to tokens

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -- backend/core/security.py backend/tests/core/test_security.py
```

---

### Task 2: Settings, enums and errors for the admin surface

**Files:**
- Modify: `backend/core/config.py`, `backend/enums.py`, `backend/errors.py`, `example.env`
- Test: `backend/tests/core/test_config.py`, `backend/tests/test_errors.py`

**Interfaces:**
- Produces: `Settings.admin_session_minutes: int = 60`, `Settings.admin_reauth_minutes: int = 5`; `enums.AdminAction` (StrEnum); errors `AdminReauthRequiredError()`, `CannotModifySelfError()`, `LastAdminError()` — all taking no constructor arguments.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/core/test_config.py`:

```python
def test_admin_window_defaults_match_the_spec(clean_env: None) -> None:
    settings = Settings(_env_file=None, env="development")
    assert settings.admin_session_minutes == 60
    assert settings.admin_reauth_minutes == 5
```

Note the existing `clean_env` fixture is required — without it a populated `.env` exported by `.scripts/sonar.sh` leaks in and the assertion fails.

Append to `backend/tests/test_errors.py`, extending the existing parametrised case list with these three entries and importing the three classes:

```python
        (AdminReauthRequiredError(), 403, "admin_reauth_required"),
        (CannotModifySelfError(), 409, "cannot_modify_self"),
        (LastAdminError(), 409, "last_admin"),
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/core/test_config.py tests/test_errors.py -q`
Expected: FAIL — `ImportError: cannot import name 'AdminReauthRequiredError'`.

- [ ] **Step 3: Add the enum**

Append to `backend/enums.py`:

```python
class AdminAction(StrEnum):
    USER_DISABLED = "user_disabled"
    USER_ENABLED = "user_enabled"
    USER_PROMOTED = "user_promoted"
    USER_DEMOTED = "user_demoted"
    USER_PASSWORD_RESET = "user_password_reset"
    USER_DELETED = "user_deleted"
```

Only the phase-1 members. `listing_hidden`, `listing_unhidden`, `catalog_updated` and `ingest_requested` arrive with their own phases — adding them now would be a vocabulary nothing writes.

- [ ] **Step 4: Add the errors**

Append to `backend/errors.py`, after `AlertNotFoundError`:

```python
class AdminReauthRequiredError(AppError):
    status_code = 403
    code = "admin_reauth_required"

    def __init__(self) -> None:
        # Distinct from permission_denied: the caller IS an admin, their password
        # entry is just too old. The UI shows a password prompt, not a dead end.
        super().__init__("Re-authentication required")


class CannotModifySelfError(AppError):
    status_code = 409
    code = "cannot_modify_self"

    def __init__(self) -> None:
        super().__init__("An admin cannot disable, demote or delete themselves")


class LastAdminError(AppError):
    status_code = 409
    code = "last_admin"

    def __init__(self) -> None:
        super().__init__("The last active admin cannot be disabled, demoted or deleted")
```

- [ ] **Step 5: Add the settings**

In `backend/core/config.py`, add two fields after `admin_password`:

```python
    admin_session_minutes: int = 60
    admin_reauth_minutes: int = 5
```

In `example.env`, after the `ADMIN_PASSWORD=` line:

```dotenv
# Admin panel — how long after a password entry admin routes stay reachable, and the
# tighter window destructive actions require. A refresh does NOT renew either.
ADMIN_SESSION_MINUTES=60
ADMIN_REAUTH_MINUTES=5
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/core/test_config.py tests/test_errors.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
uv run ruff check . --fix && uv run black .
cd .. && git commit -m "feat(backend): add admin window settings, actions and errors

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -- backend/core/config.py backend/enums.py backend/errors.py backend/tests/core/test_config.py backend/tests/test_errors.py example.env
```

---

### Task 3: Thread `auth_at` through `AuthService`, add `reauth`

**Files:**
- Modify: `backend/services/auth_service.py`, `backend/schemas/auth.py`
- Test: `backend/tests/services/test_auth_service.py`

**Interfaces:**
- Consumes: `TokenClaims(..., auth_at)` from Task 1.
- Produces: `AuthService._issue(user: User, auth_at: int) -> AuthResult`; `AuthService.reauth(user_id: uuid.UUID, payload: ReauthRequest) -> AuthResult`; `schemas.auth.ReauthRequest {password: SecretStr}`; module helper `_now() -> int`.

**The one rule this task exists to enforce:** `refresh` passes the OLD token's `auth_at` through unchanged. Every other issuing path — register, authenticate, change_password, reauth — sets it to now, because each of those follows a real password entry. If `refresh` reset it, a 30-day refresh cookie would keep admin access alive forever and the freshness windows would mean nothing.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/services/test_auth_service.py`:

```python
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
    with pytest.raises(AccountDisabledError):
        await _service(users).reauth(uuid.UUID(int=42), ReauthRequest(password=PASSWORD))


async def test_changing_the_password_restamps_auth_at() -> None:
    user = _user()
    service = _service(_users(get_by_id=user))
    change = PasswordChange(current=PASSWORD, new="a brand new password")
    result = await service.change_password(user.id, change)
    claims = decode_token(result.tokens.access, TEST_JWT_SECRET, TokenType.ACCESS)
    assert claims.auth_at > 0  # they just proved they know the password
```

Add `ReauthRequest` to the `schemas.auth` import line and `TokenClaims` to the `core.security` import line at the top of the file.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/services/test_auth_service.py -q`
Expected: FAIL — `ImportError: cannot import name 'ReauthRequest'`.

- [ ] **Step 3: Add the schema**

In `backend/schemas/auth.py`, after `PasswordChange`:

```python
class ReauthRequest(BaseModel):
    password: GivenPassword
```

`GivenPassword` (no minimum length) is deliberate and matches `LoginRequest`: a short wrong guess must fail as 401 `invalid_credentials`, never a 422 that reveals the password policy.

- [ ] **Step 4: Implement the service changes**

In `backend/services/auth_service.py`:

Add a module-level helper beside the other helpers:

```python
def _now() -> int:
    """Unix seconds — the unit of the `auth_at` claim."""
    return int(time.time())
```

and `import time` at the top.

Change `_issue` to take the stamp explicitly, so no caller can forget to decide:

```python
    def _issue(self, user: User, auth_at: int) -> AuthResult:
        claims = TokenClaims(user.id, user.token_version, user.role, auth_at)
        tokens = issue_token_pair(
            claims,
            self._secret,
            timedelta(minutes=self._settings.access_token_minutes),
            timedelta(days=self._settings.refresh_token_days),
        )
        return AuthResult(UserRead.model_validate(user), tokens)
```

Update the four existing call sites:
- in `register`: `return self._issue(user, _now())`
- in `authenticate`: `return self._issue(user, _now())`
- in `change_password`: `return self._issue(user, _now())`
- in `refresh`: `return self._issue(user, claims.auth_at)` — **the critical one.** Add above it:

```python
        # Carry the ORIGINAL auth_at through. A refresh proves the session is alive,
        # not that the human is present, so it must not renew admin freshness.
```

Add the new method after `change_password`:

```python
    async def reauth(self, user_id: uuid.UUID, payload: ReauthRequest) -> AuthResult:
        """Re-stamp `auth_at` after a real password entry. Deliberately does NOT bump
        `token_version`: proving you are present should not sign out your other
        devices, unlike a password change."""
        user = await self._load(user_id)
        password = payload.password.get_secret_value()
        if not await _in_hash_pool(verify_password, password, user.password_hash):
            raise InvalidCredentialsError()
        return self._issue(user, _now())
```

Add `ReauthRequest` to the `schemas.auth` import.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/services/test_auth_service.py tests/core -q`
Expected: PASS. `_load` already raises `AccountDisabledError`, so the disabled-account test passes without extra code.

- [ ] **Step 6: Run the full suite — this task changes a shared signature**

Run: `uv run pytest -q`
Expected: 343+ passed. Any failure is a `_issue` call site you missed.

- [ ] **Step 7: Commit**

```bash
uv run ruff check . --fix && uv run black .
cd .. && git commit -m "feat(backend): stamp auth_at on password entry, preserve it on refresh

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -- backend/services/auth_service.py backend/schemas/auth.py backend/tests/services/test_auth_service.py
```

---

### Task 4: The `admin_audit` table and migration 0004

**Files:**
- Create: `backend/models/admin_audit.py`, `backend/db/migrations/versions/0004_admin_audit.py`
- Modify: `backend/models/__init__.py`
- Test: `backend/tests/db/test_schema.py`

**Interfaces:**
- Consumes: `enums.AdminAction` (Task 2); `db.base.Base`, `UUIDPrimaryKeyMixin`, `enum_type`; `models.user.utc_now`.
- Produces: `models.admin_audit.AdminAudit` with `actor_id`, `actor_email`, `action`, `target_type`, `target_id`, `summary`, `created_at`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/db/test_schema.py`:

```python
@pytest.mark.db
async def test_admin_audit_survives_its_actor(session: AsyncSession) -> None:
    """Deleting an admin must never erase the record of what they did, so actor_id is
    ON DELETE SET NULL and the email is denormalised onto the row."""
    rows = await session.execute(
        text(
            "SELECT confdeltype FROM pg_constraint "
            "WHERE conrelid = 'admin_audit'::regclass AND contype = 'f'"
        )
    )
    assert [r[0] for r in rows] == ["n"]  # 'n' = SET NULL, not 'c' = CASCADE
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/db/test_schema.py -q`
Expected: FAIL — `relation "admin_audit" does not exist`.

- [ ] **Step 3: Create the model**

`backend/models/admin_audit.py`:

```python
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, UUIDPrimaryKeyMixin, enum_type
from enums import AdminAction
from models.user import EMAIL_MAX_LENGTH, utc_now


class AdminAudit(UUIDPrimaryKeyMixin, Base):
    """Append-only. There is no update or delete path anywhere in the codebase, and
    rows are written in the same transaction as the change they describe."""

    __tablename__ = "admin_audit"

    # SET NULL, never CASCADE: deleting an admin must not erase their history.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    # Denormalised so the row stays readable after the actor is deleted.
    actor_email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH))
    action: Mapped[AdminAction] = mapped_column(enum_type(AdminAction), index=True)
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
```

Add to `backend/models/__init__.py`: `from models.admin_audit import AdminAudit`, and `"AdminAudit"` in `__all__` (keep both lists alphabetical).

- [ ] **Step 4: Write the migration**

`backend/db/migrations/versions/0004_admin_audit.py`:

```python
"""add the admin audit trail

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ADMIN_ACTION = sa.Enum(
    "user_disabled",
    "user_enabled",
    "user_promoted",
    "user_demoted",
    "user_password_reset",
    "user_deleted",
    name="adminaction",
    native_enum=False,
    length=32,
)


def upgrade() -> None:
    op.create_table(
        "admin_audit",
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_email", sa.String(length=320), nullable=False),
        sa.Column("action", _ADMIN_ACTION, nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admin_audit_actor_id"), "admin_audit", ["actor_id"])
    op.create_index(op.f("ix_admin_audit_action"), "admin_audit", ["action"])
    op.create_index(op.f("ix_admin_audit_created_at"), "admin_audit", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_audit_created_at"), table_name="admin_audit")
    op.drop_index(op.f("ix_admin_audit_action"), table_name="admin_audit")
    op.drop_index(op.f("ix_admin_audit_actor_id"), table_name="admin_audit")
    op.drop_table("admin_audit")
```

- [ ] **Step 5: Run the schema tests**

Run: `uv run pytest tests/db/test_schema.py -q`
Expected: PASS, including the pre-existing `test_models_and_migrations_do_not_drift`. If drift is reported, fix the **migration** to match the model, never the reverse.

- [ ] **Step 6: Verify the downgrade against the TEST database only**

Run (from `backend/`):
```bash
uv run python - <<'EOF'
from alembic import command
from alembic.config import Config
from core.config import get_settings

url = get_settings().test_database_url
assert "54329" in url, f"refusing to touch a non-test database: {url}"
config = Config("alembic.ini")
config.set_main_option("script_location", "db/migrations")
config.attributes["database_url"] = url
command.downgrade(config, "0003")
command.upgrade(config, "head")
print("downgrade + upgrade ok")
EOF
```
Expected: `downgrade + upgrade ok`. The assert is a guard — never run a downgrade against `DATABASE_URL`.

- [ ] **Step 7: Commit**

```bash
uv run ruff check . --fix && uv run black .
cd .. && git add backend/models/admin_audit.py backend/db/migrations/versions/0004_admin_audit.py
git commit -m "feat(backend): add the append-only admin audit table

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -- backend/models/admin_audit.py backend/models/__init__.py backend/db/migrations/versions/0004_admin_audit.py backend/tests/db/test_schema.py
```

---

### Task 5: `AdminAuditRepository` and `AdminUserRepository`

**Files:**
- Create: `backend/repositories/admin_audit_repository.py`, `backend/repositories/admin_user_repository.py`
- Test: `backend/tests/repositories/test_admin_repositories.py`

**Interfaces:**
- Consumes: `models.admin_audit.AdminAudit` (Task 4); existing `models.user.User`, `models.saved_listing.SavedListing`, `models.price_alert.PriceAlert`.
- Produces:
  - `AdminAuditRepository(session)`: `async add(entry) -> AdminAudit`; `async list_page(limit, offset, action, actor_id) -> list[AdminAudit]`; `async count(action, actor_id) -> int`
  - `AdminUserRepository(session)`: `async search(term, role, is_active, limit, offset) -> list[User]`; `async count(term, role, is_active) -> int`; `async lock_active_admin_ids() -> list[uuid.UUID]`; `async remove(user) -> None`; `async saved_and_alert_counts(user_id) -> tuple[int, int]`

`lock_active_admin_ids` issues `SELECT … FOR UPDATE` over the active admin rows. That row lock is what makes the last-admin guard safe: two concurrent demotions serialise instead of both reading "two admins" and both proceeding.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/repositories/test_admin_repositories.py`:

```python
import uuid

import pytest
from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from enums import AdminAction, UserRole
from models.admin_audit import AdminAudit
from models.user import User
from repositories.admin_audit_repository import AdminAuditRepository
from repositories.admin_user_repository import AdminUserRepository
from repositories.user_repository import UserRepository

pytestmark = pytest.mark.db


async def _user(
    session: AsyncSession, email: str, role: UserRole = UserRole.USER
) -> User:
    created = await UserRepository(session).create_if_absent(email, "hash", role)
    assert created is not None
    return created


def _entry(actor: User, action: AdminAction) -> AdminAudit:
    return AdminAudit(
        actor_id=actor.id,
        actor_email=actor.email,
        action=action,
        target_type="user",
        target_id=str(uuid.UUID(int=7)),
        summary={"before": {"is_active": True}, "after": {"is_active": False}},
    )


async def test_audit_rows_come_back_newest_first_and_filter_by_action(
    session: AsyncSession,
) -> None:
    audit = AdminAuditRepository(session)
    admin = await _user(session, "admin@example.com", UserRole.ADMIN)
    await audit.add(_entry(admin, AdminAction.USER_DISABLED))
    await audit.add(_entry(admin, AdminAction.USER_PROMOTED))
    newest_first = await audit.list_page(50, 0, None, None)
    assert [row.action for row in newest_first] == [
        AdminAction.USER_PROMOTED,
        AdminAction.USER_DISABLED,
    ]
    assert len(await audit.list_page(50, 0, AdminAction.USER_PROMOTED, None)) == 1
    assert await audit.count(AdminAction.USER_PROMOTED, None) == 1


async def test_removing_the_actor_keeps_the_audit_row_readable(
    session: AsyncSession,
) -> None:
    audit = AdminAuditRepository(session)
    admin = await _user(session, "admin@example.com", UserRole.ADMIN)
    await audit.add(_entry(admin, AdminAction.USER_DELETED))
    await session.execute(sql_delete(User).where(User.id == admin.id))
    await session.flush()
    rows = await audit.list_page(50, 0, None, None)
    assert len(rows) == 1
    assert rows[0].actor_id is None  # SET NULL, not cascaded away
    assert rows[0].actor_email == "admin@example.com"  # still says who did it


async def test_user_search_matches_a_partial_email_and_filters(
    session: AsyncSession,
) -> None:
    users = AdminUserRepository(session)
    await _user(session, "driver@example.com")
    await _user(session, "admin@example.com", UserRole.ADMIN)
    assert len(await users.search("driv", None, None, 50, 0)) == 1
    assert len(await users.search(None, UserRole.ADMIN, None, 50, 0)) == 1
    assert await users.count(None, None, None) == 2


async def test_lock_active_admin_ids_sees_only_active_admins(
    session: AsyncSession,
) -> None:
    users = AdminUserRepository(session)
    admin = await _user(session, "admin@example.com", UserRole.ADMIN)
    retired = await _user(session, "old@example.com", UserRole.ADMIN)
    retired.is_active = False
    await _user(session, "driver@example.com")
    await session.flush()
    assert await users.lock_active_admin_ids() == [admin.id]


async def test_counts_and_removal(session: AsyncSession) -> None:
    users = AdminUserRepository(session)
    user = await _user(session, "driver@example.com")
    assert await users.saved_and_alert_counts(user.id) == (0, 0)
    await users.remove(user)
    assert await users.search("driver", None, None, 50, 0) == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/repositories/test_admin_repositories.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'repositories.admin_audit_repository'`.

- [ ] **Step 3: Implement the audit repository**

`backend/repositories/admin_audit_repository.py`:

```python
import uuid

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums import AdminAction
from models.admin_audit import AdminAudit


class AdminAuditRepository:
    """Append and read only. There is deliberately no mutating method — an audit trail
    that can be rewritten is worth nothing."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: AdminAudit) -> AdminAudit:
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_page(
        self,
        limit: int,
        offset: int,
        action: AdminAction | None,
        actor_id: uuid.UUID | None,
    ) -> list[AdminAudit]:
        found = await self._session.scalars(
            select(AdminAudit)
            .where(*self._conditions(action, actor_id))
            .order_by(AdminAudit.created_at.desc(), AdminAudit.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(found)

    async def count(
        self, action: AdminAction | None, actor_id: uuid.UUID | None
    ) -> int:
        total = await self._session.scalar(
            select(func.count())
            .select_from(AdminAudit)
            .where(*self._conditions(action, actor_id))
        )
        return total or 0

    @staticmethod
    def _conditions(
        action: AdminAction | None, actor_id: uuid.UUID | None
    ) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if action is not None:
            conditions.append(AdminAudit.action == action)
        if actor_id is not None:
            conditions.append(AdminAudit.actor_id == actor_id)
        return conditions
```

- [ ] **Step 4: Implement the user repository**

`backend/repositories/admin_user_repository.py`:

```python
import uuid

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums import UserRole
from models.price_alert import PriceAlert
from models.saved_listing import SavedListing
from models.user import User


class AdminUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self,
        term: str | None,
        role: UserRole | None,
        is_active: bool | None,
        limit: int,
        offset: int,
    ) -> list[User]:
        found = await self._session.scalars(
            select(User)
            .where(*self._conditions(term, role, is_active))
            .order_by(User.created_at.desc(), User.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(found)

    async def count(
        self, term: str | None, role: UserRole | None, is_active: bool | None
    ) -> int:
        total = await self._session.scalar(
            select(func.count())
            .select_from(User)
            .where(*self._conditions(term, role, is_active))
        )
        return total or 0

    async def lock_active_admin_ids(self) -> list[uuid.UUID]:
        """SELECT ... FOR UPDATE over the active admins. The row lock is what makes the
        last-admin guard safe: two concurrent demotions serialise here instead of both
        reading "two admins" and both going ahead."""
        found = await self._session.scalars(
            select(User.id)
            .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
            .order_by(User.id)
            .with_for_update()
        )
        return list(found)

    async def remove(self, user: User) -> None:
        await self._session.delete(user)
        await self._session.flush()

    async def saved_and_alert_counts(self, user_id: uuid.UUID) -> tuple[int, int]:
        saved = await self._session.scalar(
            select(func.count())
            .select_from(SavedListing)
            .where(SavedListing.user_id == user_id)
        )
        alerts = await self._session.scalar(
            select(func.count())
            .select_from(PriceAlert)
            .where(PriceAlert.user_id == user_id)
        )
        return saved or 0, alerts or 0

    @staticmethod
    def _conditions(
        term: str | None, role: UserRole | None, is_active: bool | None
    ) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if term:
            conditions.append(User.email.ilike(f"%{term}%"))
        if role is not None:
            conditions.append(User.role == role)
        if is_active is not None:
            conditions.append(User.is_active.is_(is_active))
        return conditions
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/repositories/test_admin_repositories.py -q`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
uv run ruff check . --fix && uv run black .
cd .. && git add backend/repositories/admin_audit_repository.py backend/repositories/admin_user_repository.py backend/tests/repositories/test_admin_repositories.py
git commit -m "feat(backend): add admin audit and admin user repositories

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -- backend/repositories/admin_audit_repository.py backend/repositories/admin_user_repository.py backend/tests/repositories/test_admin_repositories.py
```

---

### Task 6: `AuditRecorder` and `AdminUserService`

**Files:**
- Create: `backend/schemas/admin.py`, `backend/services/audit_recorder.py`, `backend/services/admin_user_service.py`
- Test: `backend/tests/services/test_admin_user_service.py`

**Interfaces:**
- Consumes: both repositories (Task 5); `UserRepository.get_by_id` / `.replace_password` (Spec 4); `core.security.hash_password`; `CannotModifySelfError`, `LastAdminError` (Task 2).
- Produces:
  - `schemas.admin`: `AdminUserRow`, `AdminUserDetail`, `AdminUserPage`, `AdminUserUpdate`, `AdminPasswordReset`, `AuditRow`, `AuditPage`, `AdminStats`, `MAX_PAGE_SIZE = 100`
  - `AuditRecorder(repository)`: `async record(*, actor, action, target_type, target_id, summary) -> None`; `async recent(limit) -> list[AuditRow]`
  - `AdminUserService(users, admin_users, audit, settings)`: `list_users`, `get_user`, `update_user`, `reset_password`, `remove_user`

**The two guards this task exists for**, both checked in the service inside the same transaction as the write:
- An admin may not disable, demote or remove **themselves** → `CannotModifySelfError`.
- The **last active admin** may not be disabled, demoted or removed → `LastAdminError`.

Without them one click locks every human out permanently — and Spec 4's startup bootstrap cannot rescue it, because `ensure_admin` only creates the account when the email is *absent* and leaves a disabled or demoted row untouched.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/services/test_admin_user_service.py`:

```python
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from core.security import verify_password
from enums import AdminAction, UserRole
from errors import CannotModifySelfError, LastAdminError, NotAuthenticatedError
from models.user import User
from repositories.admin_user_repository import AdminUserRepository
from repositories.user_repository import UserRepository
from schemas.admin import AdminPasswordReset, AdminUserUpdate
from schemas.auth import UserRead
from services.admin_user_service import AdminUserService
from services.audit_recorder import AuditRecorder
from tests.support import fast_auth_settings

ACTOR_ID = uuid.UUID(int=1)
TARGET_ID = uuid.UUID(int=2)


def _row(
    user_id: uuid.UUID, role: UserRole = UserRole.USER, active: bool = True
) -> User:
    return User(
        id=user_id,
        email=f"user-{user_id.int}@example.com",
        password_hash="hash",
        role=role,
        is_active=active,
        token_version=0,
        created_at=datetime.now(UTC),
        last_login_at=None,
    )


def _actor() -> UserRead:
    return UserRead.model_validate(_row(ACTOR_ID, UserRole.ADMIN))


class Doubles:
    def __init__(self, target: User | None, active_admin_ids: list[uuid.UUID]) -> None:
        self.users = AsyncMock(spec=UserRepository)
        self.admin_users = AsyncMock(spec=AdminUserRepository)
        self.audit = AsyncMock(spec=AuditRecorder)
        self.users.get_by_id.return_value = target
        self.admin_users.lock_active_admin_ids.return_value = active_admin_ids
        self.admin_users.saved_and_alert_counts.return_value = (0, 0)
        self.service = AdminUserService(
            self.users, self.admin_users, self.audit, fast_auth_settings()
        )


async def test_an_admin_cannot_disable_themselves() -> None:
    doubles = Doubles(_row(ACTOR_ID, UserRole.ADMIN), [ACTOR_ID, TARGET_ID])
    with pytest.raises(CannotModifySelfError):
        await doubles.service.update_user(
            _actor(), ACTOR_ID, AdminUserUpdate(is_active=False)
        )
    doubles.audit.record.assert_not_awaited()


async def test_an_admin_cannot_remove_themselves() -> None:
    doubles = Doubles(_row(ACTOR_ID, UserRole.ADMIN), [ACTOR_ID, TARGET_ID])
    with pytest.raises(CannotModifySelfError):
        await doubles.service.remove_user(_actor(), ACTOR_ID)
    doubles.admin_users.remove.assert_not_awaited()


@pytest.mark.parametrize(
    "update", [AdminUserUpdate(is_active=False), AdminUserUpdate(role=UserRole.USER)]
)
async def test_the_last_active_admin_cannot_be_demoted_or_disabled(
    update: AdminUserUpdate,
) -> None:
    doubles = Doubles(_row(TARGET_ID, UserRole.ADMIN), [TARGET_ID])
    with pytest.raises(LastAdminError):
        await doubles.service.update_user(_actor(), TARGET_ID, update)
    doubles.audit.record.assert_not_awaited()


async def test_demoting_an_admin_is_allowed_while_another_remains() -> None:
    doubles = Doubles(_row(TARGET_ID, UserRole.ADMIN), [ACTOR_ID, TARGET_ID])
    await doubles.service.update_user(
        _actor(), TARGET_ID, AdminUserUpdate(role=UserRole.USER)
    )
    assert doubles.audit.record.call_args.kwargs["action"] is AdminAction.USER_DEMOTED


async def test_disabling_a_plain_user_never_consults_the_admin_lock() -> None:
    doubles = Doubles(_row(TARGET_ID), [ACTOR_ID])
    await doubles.service.update_user(
        _actor(), TARGET_ID, AdminUserUpdate(is_active=False)
    )
    doubles.admin_users.lock_active_admin_ids.assert_not_awaited()
    assert doubles.audit.record.call_args.kwargs["action"] is AdminAction.USER_DISABLED


async def test_resetting_a_password_hashes_it_and_revokes_existing_tokens() -> None:
    doubles = Doubles(_row(TARGET_ID), [ACTOR_ID])
    await doubles.service.reset_password(
        _actor(), TARGET_ID, AdminPasswordReset(new="a brand new password")
    )
    _, stored_hash = doubles.users.replace_password.call_args.args
    assert verify_password("a brand new password", stored_hash)
    assert (
        doubles.audit.record.call_args.kwargs["action"]
        is AdminAction.USER_PASSWORD_RESET
    )


async def test_the_reset_password_never_reaches_the_audit_summary() -> None:
    doubles = Doubles(_row(TARGET_ID), [ACTOR_ID])
    await doubles.service.reset_password(
        _actor(), TARGET_ID, AdminPasswordReset(new="a brand new password")
    )
    assert "a brand new password" not in str(
        doubles.audit.record.call_args.kwargs["summary"]
    )


async def test_acting_on_a_missing_user_raises() -> None:
    doubles = Doubles(None, [ACTOR_ID])
    with pytest.raises(NotAuthenticatedError):
        await doubles.service.get_user(TARGET_ID)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/services/test_admin_user_service.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'schemas.admin'`.

- [ ] **Step 3: Implement the schemas**

`backend/schemas/admin.py`:

```python
import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from enums import AdminAction, UserRole
from schemas.auth import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH

MAX_PAGE_SIZE = 100


class AdminUserRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class AdminUserDetail(AdminUserRow):
    saved_count: int
    alert_count: int


class AdminUserPage(BaseModel):
    items: list[AdminUserRow]
    total: int


class AdminUserUpdate(BaseModel):
    """Both fields optional: a request may change activity, role, or both."""

    is_active: bool | None = None
    role: UserRole | None = None


class AdminPasswordReset(BaseModel):
    new: Annotated[
        SecretStr, Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    ]


class AuditRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_email: str
    action: AdminAction
    target_type: str
    target_id: str | None
    summary: dict[str, Any]
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditRow]
    total: int


class AdminStats(BaseModel):
    users_total: int
    users_active: int
    admins_active: int
    listings_total: int
    newest_listing_fetched_at: datetime | None
    recent_audit: list[AuditRow]
```

- [ ] **Step 4: Implement the recorder**

`backend/services/audit_recorder.py`:

```python
from typing import Any

from enums import AdminAction
from models.admin_audit import AdminAudit
from repositories.admin_audit_repository import AdminAuditRepository
from schemas.admin import AuditRow
from schemas.auth import UserRead


class AuditRecorder:
    """The single way an audit row is written. Callers pass an already-redacted
    summary — nothing here inspects it, so a secret placed in a summary would be
    stored verbatim. Keeping secrets out is the calling service's job."""

    def __init__(self, repository: AdminAuditRepository) -> None:
        self._repository = repository

    async def record(
        self,
        *,
        actor: UserRead,
        action: AdminAction,
        target_type: str,
        target_id: str | None,
        summary: dict[str, Any],
    ) -> None:
        await self._repository.add(
            AdminAudit(
                actor_id=actor.id,
                actor_email=actor.email,
                action=action,
                target_type=target_type,
                target_id=target_id,
                summary=summary,
            )
        )

    async def recent(self, limit: int) -> list[AuditRow]:
        rows = await self._repository.list_page(limit, 0, None, None)
        return [AuditRow.model_validate(row) for row in rows]
```

- [ ] **Step 5: Implement the service**

`backend/services/admin_user_service.py`:

```python
"""User administration. Every mutation is guarded against lockout and audited in the
same transaction as the change itself."""

import asyncio
import uuid
from typing import Any

from core.config import Settings
from core.security import hash_password
from enums import AdminAction, UserRole
from errors import CannotModifySelfError, LastAdminError, NotAuthenticatedError
from models.user import User
from repositories.admin_user_repository import AdminUserRepository
from repositories.user_repository import UserRepository
from schemas.admin import (
    AdminPasswordReset,
    AdminUserDetail,
    AdminUserPage,
    AdminUserRow,
    AdminUserUpdate,
)
from schemas.auth import UserRead
from services.audit_recorder import AuditRecorder

TARGET_USER = "user"


class AdminUserService:
    def __init__(
        self,
        users: UserRepository,
        admin_users: AdminUserRepository,
        audit: AuditRecorder,
        settings: Settings,
    ) -> None:
        self._users = users
        self._admin_users = admin_users
        self._audit = audit
        self._settings = settings

    async def list_users(
        self,
        term: str | None,
        role: UserRole | None,
        is_active: bool | None,
        limit: int,
        offset: int,
    ) -> AdminUserPage:
        rows = await self._admin_users.search(term, role, is_active, limit, offset)
        return AdminUserPage(
            items=[AdminUserRow.model_validate(row) for row in rows],
            total=await self._admin_users.count(term, role, is_active),
        )

    async def get_user(self, user_id: uuid.UUID) -> AdminUserDetail:
        return await self._detail(await self._load(user_id))

    async def update_user(
        self, actor: UserRead, user_id: uuid.UUID, payload: AdminUserUpdate
    ) -> AdminUserDetail:
        user = await self._load(user_id)
        before = {"is_active": user.is_active, "role": user.role.value}
        if _removes_admin_access(payload):
            await self._guard_lockout(actor, user)
        if payload.is_active is not None:
            user.is_active = payload.is_active
        if payload.role is not None:
            user.role = payload.role
        after = {"is_active": user.is_active, "role": user.role.value}
        await self._audit.record(
            actor=actor,
            action=_action_for(before, after),
            target_type=TARGET_USER,
            target_id=str(user.id),
            summary={"email": user.email, "before": before, "after": after},
        )
        return await self._detail(user)

    async def reset_password(
        self, actor: UserRead, user_id: uuid.UUID, payload: AdminPasswordReset
    ) -> None:
        user = await self._load(user_id)
        password = payload.new.get_secret_value()
        new_hash = await asyncio.to_thread(
            hash_password, password, self._settings.scrypt_n
        )
        # replace_password also bumps token_version, signing the user out everywhere.
        await self._users.replace_password(user, new_hash)
        await self._audit.record(
            actor=actor,
            action=AdminAction.USER_PASSWORD_RESET,
            target_type=TARGET_USER,
            target_id=str(user.id),
            # The new password is deliberately absent — only the fact of the reset.
            summary={"email": user.email},
        )

    async def remove_user(self, actor: UserRead, user_id: uuid.UUID) -> None:
        user = await self._load(user_id)
        await self._guard_lockout(actor, user)
        summary = {"email": user.email, "role": user.role.value}
        await self._admin_users.remove(user)
        await self._audit.record(
            actor=actor,
            action=AdminAction.USER_DELETED,
            target_type=TARGET_USER,
            target_id=str(user_id),
            summary=summary,
        )

    async def _guard_lockout(self, actor: UserRead, user: User) -> None:
        """Only called when an action would remove an admin's access."""
        if user.id == actor.id:
            raise CannotModifySelfError()
        if user.role is not UserRole.ADMIN:
            return  # a plain user can never be the last admin
        remaining = await self._admin_users.lock_active_admin_ids()
        if not [admin_id for admin_id in remaining if admin_id != user.id]:
            raise LastAdminError()

    async def _load(self, user_id: uuid.UUID) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotAuthenticatedError()
        return user

    async def _detail(self, user: User) -> AdminUserDetail:
        saved, alerts = await self._admin_users.saved_and_alert_counts(user.id)
        return AdminUserDetail(
            **AdminUserRow.model_validate(user).model_dump(),
            saved_count=saved,
            alert_count=alerts,
        )


def _removes_admin_access(payload: AdminUserUpdate) -> bool:
    losing_role = payload.role is not None and payload.role is not UserRole.ADMIN
    return payload.is_active is False or losing_role


def _action_for(before: dict[str, Any], after: dict[str, Any]) -> AdminAction:
    if before["role"] != after["role"]:
        return (
            AdminAction.USER_PROMOTED
            if after["role"] == UserRole.ADMIN.value
            else AdminAction.USER_DEMOTED
        )
    return AdminAction.USER_ENABLED if after["is_active"] else AdminAction.USER_DISABLED
```

Note the repository method is `remove`, not `delete`: `delete` is already imported from SQLAlchemy in several modules here and shadowing it invites confusion. The audit action stays `USER_DELETED` because that is the vocabulary the spec fixed.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/services/test_admin_user_service.py -q`
Expected: PASS (9 tests — the parametrised case counts twice).

- [ ] **Step 7: Commit**

```bash
uv run ruff check . --fix && uv run black .
cd .. && git add backend/schemas/admin.py backend/services/audit_recorder.py backend/services/admin_user_service.py backend/tests/services/test_admin_user_service.py
git commit -m "feat(backend): add admin user service with lockout guards and audit

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -- backend/schemas/admin.py backend/services/audit_recorder.py backend/services/admin_user_service.py backend/tests/services/test_admin_user_service.py
```

---

### Task 7: Freshness dependencies and the `/auth/reauth` endpoint

**Files:**
- Modify: `backend/dependencies/providers.py`, `backend/api/v1/endpoints/auth.py`
- Test: `backend/tests/api/test_auth_api.py`

**Interfaces:**
- Consumes: `TokenClaims.auth_at` (Task 1), `AuthService.reauth` + `ReauthRequest` (Task 3), `AdminReauthRequiredError` (Task 2), `Settings.admin_session_minutes` / `.admin_reauth_minutes` (Task 2).
- Produces in `dependencies/providers.py`: `require_admin` (now freshness-checked), `require_fresh_admin`, `FreshAdminDep`, `get_admin_user_service`, `get_audit_recorder`. Route `POST /api/v1/auth/reauth`.

**Existing-code note:** the auth endpoints in this repo carry **no `response_model=` argument** — a Sonar cleanup removed them because they duplicated the return annotation. Follow that: declare the return type and nothing else.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/api/test_auth_api.py`:

```python
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
```

Ensure this file imports `TokenClaims` and `encode_token` from `core.security`, and `TokenType`, `UserRole` from `enums`.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/api/test_auth_api.py -q`
Expected: FAIL — `/auth/reauth` and `/api/v1/admin/stats` both 404.

- [ ] **Step 3: Add the dependencies**

In `backend/dependencies/providers.py`, add `import time` and these imports:

```python
from errors import AdminReauthRequiredError
from repositories.admin_audit_repository import AdminAuditRepository
from repositories.admin_user_repository import AdminUserRepository
from services.admin_user_service import AdminUserService
from services.audit_recorder import AuditRecorder
```

Replace the existing `require_admin` with this pair and append the service providers:

```python
def _require_fresh_enough(auth_at: int, window_minutes: int) -> None:
    """`auth_at` is stamped only by a real password entry — a refresh carries the old
    value through. So this measures time since the human was last present, not since
    the session was last active."""
    if int(time.time()) - auth_at > window_minutes * 60:
        raise AdminReauthRequiredError()


async def require_admin(
    current: CurrentUserDep,
    settings: SettingsDep,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserRead:
    _require_fresh_enough(current.auth_at, settings.admin_session_minutes)
    return await service.require_admin(current.user_id)


async def require_fresh_admin(
    current: CurrentUserDep,
    settings: SettingsDep,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserRead:
    _require_fresh_enough(current.auth_at, settings.admin_reauth_minutes)
    return await service.require_admin(current.user_id)


# Only the destructive routes need the actor injected; reads are covered by the
# router-level guard alone, so there is deliberately no plain `AdminDep`.
FreshAdminDep = Annotated[UserRead, Depends(require_fresh_admin)]


def get_audit_recorder(session: SessionDep) -> AuditRecorder:
    return AuditRecorder(AdminAuditRepository(session))


def get_admin_user_service(
    session: SessionDep, settings: SettingsDep
) -> AdminUserService:
    return AdminUserService(
        UserRepository(session),
        AdminUserRepository(session),
        AuditRecorder(AdminAuditRepository(session)),
        settings,
    )
```

- [ ] **Step 4: Add the endpoint**

In `backend/api/v1/endpoints/auth.py`, add `ReauthRequest` to the `schemas.auth` import and append:

```python
@router.post("/reauth")
async def reauth(
    payload: ReauthRequest,
    response: Response,
    current: CurrentUserDep,
    service: ServiceDep,
    settings: SettingsDep,
) -> UserRead:
    """Re-stamp admin freshness after a password entry. Deliberately does not bump
    token_version, so the user's other devices stay signed in."""
    result = await service.reauth(current.user_id, payload)
    _set_auth_cookies(response, result.tokens, settings)
    return result.user
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/api/test_auth_api.py -q`
Expected: the two reauth-only tests PASS; `test_reauth_restores_a_stale_admin_window` still fails on the missing `/api/v1/admin/stats`, which Task 8 adds. That is expected — do not chase it here.

- [ ] **Step 6: Commit**

```bash
uv run ruff check . --fix && uv run black .
cd .. && git commit -m "feat(backend): add admin freshness dependencies and /auth/reauth

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -- backend/dependencies/providers.py backend/api/v1/endpoints/auth.py backend/tests/api/test_auth_api.py
```

---

### Task 8: The admin router and its endpoints

**Files:**
- Create: `backend/api/v1/admin/__init__.py`, `router.py`, `users.py`, `audit.py`, `stats.py` (all under `backend/api/v1/admin/`)
- Modify: `backend/api/v1/router.py`
- Test: `backend/tests/api/test_admin_api.py`

**Interfaces:**
- Consumes: `require_admin`, `FreshAdminDep`, `get_admin_user_service`, `get_audit_recorder` (Task 7); `AdminUserService` (Task 6); `AdminAuditRepository` (Task 5); the pre-existing `ListingRepository.count()` and `.newest_fetched_at()`.
- Produces: every route under `/api/v1/admin` listed in spec §5 for phase 1.

**How the router-level guard works.** `require_admin` is attached to the router itself, so a route added later is guarded whether or not its author remembers. Routes that also need the actor's identity declare `actor: FreshAdminDep`; FastAPI caches dependency results within a request, so `require_admin` still executes exactly once.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/api/test_admin_api.py`:

```python
"""Admin API. The first test is the important one: it proves no route escapes the guard."""

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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/api/test_admin_api.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.v1.admin'`.

- [ ] **Step 3: Create the router package**

`backend/api/v1/admin/__init__.py` — empty file.

`backend/api/v1/admin/router.py`:

```python
from fastapi import APIRouter, Depends

from api.v1.admin import audit, stats, users
from dependencies.providers import require_admin

# Router-level guard: a route added later is protected whether or not its author
# remembers to ask for it. FastAPI caches the result within a request, so routes that
# additionally declare FreshAdminDep do not re-run the database read.
router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)
router.include_router(users.router)
router.include_router(audit.router)
router.include_router(stats.router)
```

`backend/api/v1/admin/users.py`:

```python
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from dependencies.providers import FreshAdminDep, get_admin_user_service
from enums import UserRole
from schemas.admin import (
    MAX_PAGE_SIZE,
    AdminPasswordReset,
    AdminUserDetail,
    AdminUserPage,
    AdminUserUpdate,
)
from services.admin_user_service import AdminUserService

router = APIRouter(prefix="/users")
ServiceDep = Annotated[AdminUserService, Depends(get_admin_user_service)]


@router.get("")
async def list_users(
    service: ServiceDep,
    term: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminUserPage:
    return await service.list_users(term, role, is_active, limit, offset)


@router.get("/{user_id}")
async def read_user(user_id: uuid.UUID, service: ServiceDep) -> AdminUserDetail:
    return await service.get_user(user_id)


@router.patch("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    actor: FreshAdminDep,
    service: ServiceDep,
) -> AdminUserDetail:
    return await service.update_user(actor, user_id, payload)


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    user_id: uuid.UUID,
    payload: AdminPasswordReset,
    actor: FreshAdminDep,
    service: ServiceDep,
) -> None:
    await service.reset_password(actor, user_id, payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(
    user_id: uuid.UUID, actor: FreshAdminDep, service: ServiceDep
) -> None:
    await service.remove_user(actor, user_id)
```

`backend/api/v1/admin/audit.py`:

```python
import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from dependencies.providers import SessionDep
from enums import AdminAction
from repositories.admin_audit_repository import AdminAuditRepository
from schemas.admin import MAX_PAGE_SIZE, AuditPage, AuditRow

router = APIRouter(prefix="/audit")


@router.get("")
async def list_audit(
    session: SessionDep,
    action: AdminAction | None = None,
    actor_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditPage:
    repository = AdminAuditRepository(session)
    rows = await repository.list_page(limit, offset, action, actor_id)
    return AuditPage(
        items=[AuditRow.model_validate(row) for row in rows],
        total=await repository.count(action, actor_id),
    )
```

`backend/api/v1/admin/stats.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.providers import SessionDep, get_audit_recorder
from enums import UserRole
from repositories.admin_user_repository import AdminUserRepository
from repositories.listing_repository import ListingRepository
from schemas.admin import AdminStats
from services.audit_recorder import AuditRecorder

RECENT_AUDIT_LIMIT = 10

router = APIRouter(prefix="/stats")
RecorderDep = Annotated[AuditRecorder, Depends(get_audit_recorder)]


@router.get("")
async def read_stats(session: SessionDep, audit: RecorderDep) -> AdminStats:
    users = AdminUserRepository(session)
    listings = ListingRepository(session)
    return AdminStats(
        users_total=await users.count(None, None, None),
        users_active=await users.count(None, None, True),
        admins_active=await users.count(None, UserRole.ADMIN, True),
        listings_total=await listings.count(),
        newest_listing_fetched_at=await listings.newest_fetched_at(),
        recent_audit=await audit.recent(RECENT_AUDIT_LIMIT),
    )
```

In `backend/api/v1/router.py`, add `from api.v1.admin.router import router as admin_router` and `router.include_router(admin_router)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/api/test_admin_api.py tests/api/test_auth_api.py -q`
Expected: PASS, including `test_reauth_restores_a_stale_admin_window` from Task 7, which needed `/admin/stats` to exist.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: 343 plus the new tests, all passing.

- [ ] **Step 6: Commit**

```bash
uv run ruff check . --fix && uv run black .
cd .. && git add backend/api/v1/admin backend/tests/api/test_admin_api.py
git commit -m "feat(backend): add the guarded admin router with user, audit and stats routes

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -- backend/api/v1/admin backend/api/v1/router.py backend/tests/api/test_admin_api.py
```

---

### Task 9: Frontend admin types and helpers

**Files:**
- Create: `frontend/src/lib/admin.ts`, `frontend/src/lib/admin.test.ts`
- Modify: `frontend/src/lib/api/types.ts`, `frontend/src/lib/api/client.ts`

**Interfaces:**
- Produces:
  - `lib/api/types.ts`: `AdminAction`, `AdminUserRow`, `AdminUserDetail`, `AdminUserPage`, `AdminUserUpdate`, `AuditRow`, `AuditPage`, `AdminStats`
  - `lib/api/client.ts`: `apiPatch<T = void>(path, body?, signal?)`
  - `lib/admin.ts`: `ADMIN_ERROR_TEXT`, `needsReauth(error)`, `describeAudit(row)`

- [ ] **Step 1: Add the types and `apiPatch`**

Append to `frontend/src/lib/api/types.ts` (these mirror `backend/schemas/admin.py` by hand — change both together):

```ts
/** Mirrors backend `schemas/admin.py`. */
export type AdminAction =
  | "user_disabled" | "user_enabled" | "user_promoted"
  | "user_demoted" | "user_password_reset" | "user_deleted";
export interface AdminUserRow { id: string; email: string; role: UserRole; is_active: boolean; created_at: string; last_login_at: string | null; }
export interface AdminUserDetail extends AdminUserRow { saved_count: number; alert_count: number; }
export interface AdminUserPage { items: AdminUserRow[]; total: number; }
export interface AdminUserUpdate { is_active?: boolean; role?: UserRole; }
export interface AuditRow { id: string; actor_id: string | null; actor_email: string; action: AdminAction; target_type: string; target_id: string | null; summary: Record<string, unknown>; created_at: string; }
export interface AuditPage { items: AuditRow[]; total: number; }
export interface AdminStats { users_total: number; users_active: number; admins_active: number; listings_total: number; newest_listing_fetched_at: string | null; recent_audit: AuditRow[]; }
```

Spec 4 added `apiPut` and `apiDelete` but no PATCH. Add this beside `apiPut` in `frontend/src/lib/api/client.ts`:

```ts
export function apiPatch<T = void>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, withJson("PATCH", body, signal));
}
```

- [ ] **Step 2: Write the failing tests**

Create `frontend/src/lib/admin.test.ts`:

```ts
import { expect, test } from "bun:test";
import { ApiError } from "./api/client";
import { ADMIN_ERROR_TEXT, describeAudit, needsReauth } from "./admin";
import type { AuditRow } from "./api/types";

const row = (action: AuditRow["action"]): AuditRow => ({
  id: "a", actor_id: "b", actor_email: "admin@example.com", action,
  target_type: "user", target_id: "c",
  summary: { email: "driver@example.com" }, created_at: "2026-09-21T00:00:00Z",
});

test("needsReauth fires only on the admin_reauth_required code", () => {
  expect(needsReauth(new ApiError(403, "admin_reauth_required", "x"))).toBe(true);
  expect(needsReauth(new ApiError(403, "permission_denied", "x"))).toBe(false);
  expect(needsReauth(new ApiError(401, "not_authenticated", "x"))).toBe(false);
  expect(needsReauth(new Error("boom"))).toBe(false);
});

test("every admin error code the UI can hit has Persian copy", () => {
  expect(Object.keys(ADMIN_ERROR_TEXT).sort()).toEqual([
    "admin_reauth_required", "cannot_modify_self", "last_admin", "permission_denied",
  ]);
  for (const text of Object.values(ADMIN_ERROR_TEXT)) expect(text.length).toBeGreaterThan(0);
});

test("describeAudit names the actor and the target", () => {
  const described = describeAudit(row("user_disabled"));
  expect(described).toContain("admin@example.com");
  expect(described).toContain("driver@example.com");
});

test("describeAudit falls back rather than throwing on an unknown action", () => {
  const unknown = { ...row("user_disabled"), action: "future_action" } as unknown as AuditRow;
  expect(describeAudit(unknown)).toContain("future_action");
});
```

- [ ] **Step 3: Run them to verify they fail**

Run (from `frontend/`): `bun test src/lib/admin.test.ts`
Expected: FAIL — `Cannot find module './admin'`.

- [ ] **Step 4: Implement**

Create `frontend/src/lib/admin.ts`:

```ts
import { ApiError } from "./api/client";
import type { AdminAction, AuditRow } from "./api/types";

/** Keyed by `ApiError.code`, never by message text — the project rule. */
export const ADMIN_ERROR_TEXT: Record<string, string> = {
  admin_reauth_required: "برای این کار باید رمزت رو دوباره وارد کنی",
  permission_denied: "دسترسی ادمین نداری",
  cannot_modify_self: "روی حساب خودت نمی‌تونی این کار رو انجام بدی",
  last_admin: "آخرین ادمین فعال رو نمی‌شه غیرفعال یا حذف کرد",
};

export const needsReauth = (error: unknown): boolean =>
  error instanceof ApiError && error.code === "admin_reauth_required";

const ACTION_TEXT: Record<AdminAction, string> = {
  user_disabled: "غیرفعال کرد",
  user_enabled: "فعال کرد",
  user_promoted: "ادمین کرد",
  user_demoted: "از ادمینی برداشت",
  user_password_reset: "رمز را بازنشانی کرد",
  user_deleted: "حذف کرد",
};

/** An unknown action falls back to the raw code rather than throwing: the backend
 *  vocabulary grows one phase at a time and a stale UI must not crash on a new one. */
export function describeAudit(row: AuditRow): string {
  const target =
    typeof row.summary.email === "string" ? row.summary.email : row.target_id ?? "—";
  return `${row.actor_email} — ${ACTION_TEXT[row.action] ?? row.action} — ${target}`;
}
```

- [ ] **Step 5: Verify and commit**

Run: `bun test src/lib/admin.test.ts && bun run lint && bunx tsc --noEmit`
Expected: PASS (4 tests), lint and tsc clean.

```bash
cd .. && git add frontend/src/lib/admin.ts frontend/src/lib/admin.test.ts
git commit -m "feat(frontend): add admin types, apiPatch and error copy helpers

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -- frontend/src/lib/admin.ts frontend/src/lib/admin.test.ts frontend/src/lib/api/types.ts frontend/src/lib/api/client.ts
```

---

### Task 10: The `/login` page and the admin menu link

**Files:**
- Create: `frontend/src/app/login/page.tsx`, `frontend/src/app/login/login.module.css`
- Modify: `frontend/src/components/Header.tsx`, `frontend/src/components/Header.module.css`

**Interfaces:**
- Consumes: `useAppState()` from Spec 4 — `user`, `authReady`, `login(email, password)`; `AUTH_ERROR_TEXT`, `MAX_PASSWORD_LENGTH` from `lib/account.ts`; `errorText`, `SERVICE_UNAVAILABLE` from `components/ErrorBanner`.
- Produces: the route `/login` honouring `?next=`, and a «پنل مدیریت» link shown only to admins.

This closes two items Spec 4 deferred. The existing `AuthDialog` stays — it serves the inline "log in to save an alert" flow; `/login` serves redirects from guarded routes, which a modal cannot do.

- [ ] **Step 1: Create the page**

`frontend/src/app/login/page.tsx`:

```tsx
"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { errorText, SERVICE_UNAVAILABLE } from "@/components/ErrorBanner";
import { AUTH_ERROR_TEXT, MAX_PASSWORD_LENGTH } from "@/lib/account";
import { ApiError } from "@/lib/api/client";
import { useAppState } from "@/state/AppState";
import styles from "./login.module.css";

const messageFor = (error: unknown): string =>
  error instanceof ApiError
    ? AUTH_ERROR_TEXT[error.code] ?? errorText(error)
    : SERVICE_UNAVAILABLE;

/** Only same-origin relative paths are honoured, so `?next=` cannot bounce a
 *  signed-in user to another site. */
const safeNext = (next: string | null): string =>
  next && next.startsWith("/") && !next.startsWith("//") ? next : "/";

function LoginForm() {
  const { user, authReady, login } = useAppState();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (authReady && user) router.replace(next);
  }, [authReady, user, next, router]);

  const submit = async (event: React.SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await login(data.get("email") as string, data.get("password") as string);
      router.replace(next);
    } catch (error_) {
      setError(messageFor(error_));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className={styles.form} onSubmit={submit}>
      <h1 className={styles.title}>ورود به ترب‌کار</h1>
      <label className={styles.field}>
        <span>ایمیل</span>
        <input name="email" type="email" required autoComplete="email" dir="ltr" />
      </label>
      <label className={styles.field}>
        <span>رمز عبور</span>
        <input name="password" type="password" required dir="ltr"
          maxLength={MAX_PASSWORD_LENGTH} autoComplete="current-password" />
      </label>
      {error && <p className={styles.error} role="alert">{error}</p>}
      <button type="submit" className={styles.submit} disabled={busy}>ورود</button>
    </form>
  );
}

export default function LoginPage() {
  // useSearchParams requires a Suspense boundary in the App Router.
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
```

`frontend/src/app/login/login.module.css`:

```css
.form {
  max-width: 380px;
  margin: 48px auto;
  padding: 24px;
  display: grid;
  gap: 14px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
}

.title {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 700;
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

- [ ] **Step 2: Add the admin link to the header menu**

In `frontend/src/components/Header.tsx`, inside the `<div className={styles.menu}>` block, above the «خروج» button:

```tsx
                    {user.role === "admin" && (
                      <Link href="/admin" className={styles.menuLink}>پنل مدیریت</Link>
                    )}
```

`Link` is already imported in this file. Append to `frontend/src/components/Header.module.css`:

```css
.menuLink {
  display: block;
  height: 34px;
  line-height: 34px;
  margin-bottom: 6px;
  border-radius: 8px;
  background: var(--fill);
  color: var(--ink);
  font-size: 13px;
  font-weight: 600;
  text-align: center;
  text-decoration: none;
}
```

- [ ] **Step 3: Verify and commit**

Run: `bun run lint && bunx tsc --noEmit && bun test`
Expected: clean, all tests pass.

```bash
cd .. && git add frontend/src/app/login
git commit -m "feat(frontend): add a login page with redirect and the admin menu link

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -- frontend/src/app/login frontend/src/components/Header.tsx frontend/src/components/Header.module.css
```

---

### Task 11: The `/admin` shell, dashboard, users screen and reauth prompt

**Files:**
- Create: `frontend/src/app/admin/layout.tsx`, `frontend/src/app/admin/page.tsx`, `frontend/src/app/admin/users/page.tsx`, `frontend/src/app/admin/admin.module.css`, `frontend/src/components/ReauthPrompt.tsx`, `frontend/src/components/ReauthPrompt.module.css`

**Interfaces:**
- Consumes: `apiGet`, `apiPost`, `apiPatch` from `lib/api/client`; `ADMIN_ERROR_TEXT`, `needsReauth`, `describeAudit` (Task 9); `useAppState()` for `user` / `authReady`; the existing `useApi` hook and `fa` formatter.

- [ ] **Step 1: Create the guard shell**

`frontend/src/app/admin/layout.tsx`:

```tsx
"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAppState } from "@/state/AppState";
import styles from "./admin.module.css";

const TABS = [
  { href: "/admin", label: "نمای کلی" },
  { href: "/admin/users", label: "کاربران" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, authReady } = useAppState();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (authReady && !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [authReady, user, pathname, router]);

  if (!authReady) return <p className={styles.state}>در حال بررسی دسترسی…</p>;
  if (!user) return null; // redirecting
  if (user.role !== "admin") return <p className={styles.state}>دسترسی ندارید</p>;

  return (
    <div className={styles.shell}>
      <nav className={styles.nav}>
        {TABS.map((tab) => (
          <Link key={tab.href} href={tab.href}
            className={`${styles.tab} ${pathname === tab.href ? styles.tabActive : ""}`}>
            {tab.label}
          </Link>
        ))}
      </nav>
      <section className={styles.body}>{children}</section>
    </div>
  );
}
```

- [ ] **Step 2: Create the reauth prompt**

`frontend/src/components/ReauthPrompt.tsx`:

```tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { SERVICE_UNAVAILABLE } from "@/components/ErrorBanner";
import { MAX_PASSWORD_LENGTH } from "@/lib/account";
import { ADMIN_ERROR_TEXT } from "@/lib/admin";
import { ApiError, apiPost } from "@/lib/api/client";
import styles from "./ReauthPrompt.module.css";

/** Shown when the API answers `admin_reauth_required`. On success the caller retries
 *  its action once; the admin is never signed out, only asked to prove presence. */
export function ReauthPrompt({ open, onDone, onCancel }: {
  open: boolean;
  onDone: () => void;
  onCancel: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const submit = async (event: React.SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await apiPost("/auth/reauth", { password: data.get("password") as string });
      onDone();
    } catch (error_) {
      setError(
        error_ instanceof ApiError
          ? ADMIN_ERROR_TEXT[error_.code] ?? "رمز اشتباه است"
          : SERVICE_UNAVAILABLE,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <dialog ref={dialogRef} className={styles.dialog} onClose={onCancel}>
      <form className={styles.form} onSubmit={submit}>
        <p className={styles.lead}>{ADMIN_ERROR_TEXT.admin_reauth_required}</p>
        <input name="password" type="password" required dir="ltr"
          maxLength={MAX_PASSWORD_LENGTH} autoComplete="current-password" />
        {error && <p className={styles.error} role="alert">{error}</p>}
        <div className={styles.actions}>
          <button type="button" onClick={onCancel} className={styles.cancel}>انصراف</button>
          <button type="submit" disabled={busy} className={styles.submit}>تأیید</button>
        </div>
      </form>
    </dialog>
  );
}
```

`frontend/src/components/ReauthPrompt.module.css`:

```css
.dialog {
  width: min(340px, calc(100vw - 32px));
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  color: var(--ink);
}

.dialog::backdrop {
  background: rgba(23, 32, 51, 0.45);
}

.form {
  display: grid;
  gap: 12px;
}

.lead {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.form input {
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  font: inherit;
}

.error {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--red-soft);
  color: var(--red-ink);
  font-size: 13px;
}

.actions {
  display: flex;
  gap: 8px;
}

.cancel,
.submit {
  flex: 1;
  height: 38px;
  border: 0;
  border-radius: 8px;
  font-weight: 600;
}

.cancel {
  background: var(--fill);
  color: var(--ink);
}

.submit {
  background: var(--red);
  color: #fff;
}

.submit:disabled {
  opacity: 0.6;
}
```

- [ ] **Step 3: Create the dashboard**

`frontend/src/app/admin/page.tsx`:

```tsx
"use client";
import { describeAudit } from "@/lib/admin";
import { apiGet } from "@/lib/api/client";
import type { AdminStats } from "@/lib/api/types";
import { useApi } from "@/lib/api/useApi";
import { fa } from "@/lib/format";
import styles from "./admin.module.css";

export default function AdminDashboard() {
  const stats = useApi("admin-stats", (signal) =>
    apiGet<AdminStats>("/admin/stats", {}, signal),
  );

  if (stats.loading) return <p className={styles.state}>در حال بارگذاری…</p>;
  if (stats.error || !stats.data) return <p className={styles.state}>آمار در دسترس نیست</p>;

  const tiles = [
    { label: "کاربران", value: stats.data.users_total },
    { label: "کاربران فعال", value: stats.data.users_active },
    { label: "ادمین‌های فعال", value: stats.data.admins_active },
    { label: "آگهی‌ها", value: stats.data.listings_total },
  ];

  return (
    <>
      <div className={styles.tiles}>
        {tiles.map((tile) => (
          <div key={tile.label} className={styles.tile}>
            <span className={styles.tileValue}>{fa(tile.value)}</span>
            <span className={styles.tileLabel}>{tile.label}</span>
          </div>
        ))}
      </div>
      <h2 className={styles.heading}>آخرین اقدام‌ها</h2>
      <ul className={styles.list}>
        {stats.data.recent_audit.map((row) => (
          <li key={row.id} className={styles.listRow}>{describeAudit(row)}</li>
        ))}
        {stats.data.recent_audit.length === 0 && (
          <li className={styles.listRow}>هنوز اقدامی ثبت نشده</li>
        )}
      </ul>
    </>
  );
}
```

- [ ] **Step 4: Create the users screen**

`frontend/src/app/admin/users/page.tsx`:

```tsx
"use client";
import { useCallback, useEffect, useState } from "react";
import { ReauthPrompt } from "@/components/ReauthPrompt";
import { ADMIN_ERROR_TEXT, needsReauth } from "@/lib/admin";
import { ApiError, apiGet, apiPatch } from "@/lib/api/client";
import type { AdminUserPage, AdminUserUpdate, UserRole } from "@/lib/api/types";
import { fa } from "@/lib/format";
import styles from "../admin.module.css";

export default function AdminUsers() {
  const [term, setTerm] = useState("");
  const [page, setPage] = useState<AdminUserPage | null>(null);
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState<(() => Promise<void>) | null>(null);

  const load = useCallback(async (search: string) => {
    setPage(await apiGet<AdminUserPage>("/admin/users", { term: search || undefined }));
  }, []);

  useEffect(() => { void load(""); }, [load]);

  /** Runs an action; on `admin_reauth_required` parks it for the prompt to retry. */
  const guarded = useCallback(async (action: () => Promise<void>) => {
    try {
      await action();
      setNotice("");
    } catch (error) {
      if (needsReauth(error)) { setPending(() => action); return; }
      setNotice(
        error instanceof ApiError
          ? ADMIN_ERROR_TEXT[error.code] ?? error.message
          : "انجام نشد",
      );
    }
  }, []);

  const update = (id: string, patch: AdminUserUpdate) =>
    guarded(async () => {
      await apiPatch(`/admin/users/${id}`, patch);
      await load(term);
    });

  return (
    <>
      <form className={styles.search}
        onSubmit={(event) => { event.preventDefault(); void load(term); }}>
        <input value={term} onChange={(event) => setTerm(event.target.value)}
          placeholder="جست‌وجوی ایمیل" dir="ltr" />
        <button type="submit">جست‌وجو</button>
      </form>
      {notice && <p className={styles.error} role="alert">{notice}</p>}
      <table className={styles.table}>
        <thead>
          <tr><th>ایمیل</th><th>نقش</th><th>وضعیت</th><th>اقدام</th></tr>
        </thead>
        <tbody>
          {(page?.items ?? []).map((row) => (
            <tr key={row.id}>
              <td dir="ltr">{row.email}</td>
              <td>{row.role === "admin" ? "ادمین" : "کاربر"}</td>
              <td>{row.is_active ? "فعال" : "غیرفعال"}</td>
              <td className={styles.rowActions}>
                <button type="button"
                  onClick={() => void update(row.id, { is_active: !row.is_active })}>
                  {row.is_active ? "غیرفعال" : "فعال"}
                </button>
                <button type="button"
                  onClick={() => void update(row.id, {
                    role: (row.role === "admin" ? "user" : "admin") as UserRole,
                  })}>
                  {row.role === "admin" ? "حذف ادمینی" : "ادمین کن"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {page && <p className={styles.total}>{`${fa(page.total)} کاربر`}</p>}
      <ReauthPrompt
        open={pending !== null}
        onCancel={() => setPending(null)}
        onDone={() => {
          const retry = pending;
          setPending(null);
          if (retry) void guarded(retry);
        }}
      />
    </>
  );
}
```

`frontend/src/app/admin/admin.module.css`:

```css
.shell {
  display: grid;
  gap: 16px;
  padding: 20px 0;
}

.state {
  padding: 32px;
  text-align: center;
  color: var(--muted);
}

.nav {
  display: flex;
  gap: 8px;
}

.tab {
  padding: 8px 14px;
  border-radius: 8px;
  background: var(--fill);
  color: var(--ink-2);
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
}

.tabActive {
  background: var(--red);
  color: #fff;
}

.body {
  display: grid;
  gap: 16px;
}

.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
}

.tile {
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  display: grid;
  gap: 4px;
}

.tileValue {
  font-size: 22px;
  font-weight: 700;
}

.tileLabel {
  font-size: 12px;
  color: var(--muted);
}

.heading {
  margin: 8px 0 0;
  font-size: 15px;
  font-weight: 700;
}

.list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 6px;
}

.listRow {
  padding: 10px 12px;
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  font-size: 13px;
}

.search {
  display: flex;
  gap: 8px;
}

.search input {
  flex: 1;
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  font: inherit;
}

.search button {
  height: 38px;
  padding: 0 16px;
  border: 0;
  border-radius: 8px;
  background: var(--red);
  color: #fff;
  font-weight: 600;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.table th,
.table td {
  padding: 10px;
  border-bottom: 1px solid var(--line-soft);
  text-align: start;
}

.rowActions {
  display: flex;
  gap: 6px;
}

.rowActions button {
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface);
  font-size: 12px;
}

.total {
  color: var(--muted);
  font-size: 12px;
}

.error {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--red-soft);
  color: var(--red-ink);
  font-size: 13px;
}
```

- [ ] **Step 5: Verify and commit**

Run: `bun run lint && bunx tsc --noEmit && bun test`
Expected: clean, all tests pass.

```bash
cd .. && git add frontend/src/app/admin frontend/src/components/ReauthPrompt.tsx frontend/src/components/ReauthPrompt.module.css
git commit -m "feat(frontend): add the admin shell, dashboard, users screen and reauth prompt

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -- frontend/src/app/admin frontend/src/components/ReauthPrompt.tsx frontend/src/components/ReauthPrompt.module.css
```

---

### Task 12: Documentation, verification and Definition of Done

**Files:**
- Modify: `CLAUDE.md`, `.scripts/smoke.sh`

- [ ] **Step 1: Document the admin surface**

In `CLAUDE.md` §1, after the **Accounts** bullet:

```markdown
- **Admin** — `/api/v1/admin` is guarded by a router-level `require_admin`; destructive
  routes additionally require `require_fresh_admin`. Tokens carry an `auth_at` claim
  stamped only by a real password entry — a refresh copies it through — so admin access
  expires after `ADMIN_SESSION_MINUTES` even on a live session. Every admin mutation
  writes an `admin_audit` row in the same transaction as the change.
```

In §4, after the `ADMIN_PASSWORD=` line, add `ADMIN_SESSION_MINUTES=60` and `ADMIN_REAUTH_MINUTES=5`.

In §2's repository tree, add `api/v1/admin/` with the comment `# Guarded admin API (router-level require_admin)`.

- [ ] **Step 2: Add the admin smoke step**

In `.scripts/smoke.sh`, before the final `echo "SMOKE PASSED…"` lines:

```bash
step "admin panel"
"${AB[@]}" open "$BASE_URL/admin"
"${AB[@]}" wait --load networkidle
expect_text "ورود به ترب‌کار" "/admin bounces an anonymous visitor to /login"
```

`expect_text` is the helper already defined at the top of the script; it screenshots and exits non-zero on failure.

- [ ] **Step 3: Run the full Definition of Done**

```bash
(cd backend && uv run ruff check . && uv run black --check . && uv run pytest -q)
(cd frontend && bun run lint && bunx tsc --noEmit && bun test)
pre-commit run --all-files
docker compose -f .docker/compose.yml build
```
Expected: all green.

- [ ] **Step 4: Verify against a running stack**

```bash
docker compose -f .docker/compose.yml -f .docker/compose.dev.yml up -d --build
./.scripts/smoke.sh
```

Then check these by hand — none can be asserted from the test suite alone:
1. Log in as the `ADMIN_EMAIL` account → «پنل مدیریت» appears in the header menu; a non-admin account does not see it.
2. `/admin` as an anonymous visitor redirects to `/login?next=%2Fadmin`, and logging in returns you to `/admin`.
3. Disable a user in the panel, then confirm that user's next `POST /api/v1/auth/refresh` returns `403 account_disabled`.
4. Set `ADMIN_REAUTH_MINUTES=1` in `.env`, restart, wait a minute, then attempt a role change → the reauth prompt appears and entering the password completes the action. Restore the value afterwards.
5. The dashboard's «آخرین اقدام‌ها» lists the actions from steps 3–4 with the correct actor email.

- [ ] **Step 5: Run the quality gate and refresh the graph**

```bash
./.scripts/sonar.sh     # needs SONAR_TOKEN in .env; the gate must PASS
graphify update .
```

`graphify-out/` is untracked — do not stage it.

- [ ] **Step 6: Commit**

```bash
git commit -m "docs(admin): document the admin surface and add its smoke step

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" -- CLAUDE.md .scripts/smoke.sh
```

---

## Out of scope (Phases 2 and 3)

Do not build these here. **Phase 2** adds `listing_moderation` (migration `0005`), the hidden-listing exclusion across every public read path, and catalog editing with cache invalidation. **Phase 3** adds `ingest_jobs` (migration `0006`), the in-process worker, the upload endpoint, the ingest screens, the dashboard's last-ingest tile and the dedicated `/admin/audit` screen.

The `AdminAction` enum deliberately carries only phase-1 members; each later phase adds its own. `require_admin` and `require_fresh_admin` are the hooks those phases plug into — a new admin route inherits the guard by being mounted on the same router.
