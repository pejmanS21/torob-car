# CLAUDE.md

Guidance for Claude Code (and any AI agent) working in this repository. Read this
before making changes. Follow the conventions here unless a human instruction in the
current task explicitly overrides them.

---

## 1. Project Overview

This is a **monolith fullstack** application kept in a single repository:

- **Backend** — Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic.
- **Frontend** — Next.js (App Router), TypeScript, managed with Bun.
- **Edge** — **Traefik v3 reverse proxy** is the single entry point, configured
  entirely by container labels. It is the *only* service that publishes a host port;
  backend, frontend, database and Redis are reachable only on the internal network.
- **Cache / LLM** — Redis caches parsed intents and ranked result lists; Pydantic AI
  turns free text into a typed `SearchIntent` (Gemini in development, any
  OpenAI-compatible API in production). The LLM never writes SQL.
- **Delivery** — Dockerized, orchestrated with Compose, shipped via GitHub Actions
  to Docker Hub.

The backend exposes a versioned REST API (`/api/v1`) that the frontend is designed
to consume; the frontend renders only what the API returns (no synthetic data)
(Spec 3). Traefik routes `/api` (and `/health`) to the backend and everything else to
the frontend, so the whole app is served from one origin.

---

## 2. Repository Structure

```
.
├── CLAUDE.md
├── README.md
├── example.env                  # Template for .env — copy, never commit real secrets
├── .pre-commit-config.yaml      # Pre-commit hooks
├── sonar-project.properties     # SonarQube scan config (see §12/§13)
├── .github/
│   └── workflows/
│       ├── ci.yml               # Lint + test (backend & frontend)
│       ├── security.yml         # Semgrep + Gitleaks
│       └── docker-publish.yml   # Build & push images to Docker Hub
├── .docker/
│   ├── backend.Dockerfile       # Multi-stage, uv-based
│   ├── frontend.Dockerfile      # Multi-stage (see §11.2)
│   ├── compose.yml              # Base / production-like stack (Traefik + backend + frontend + db + redis)
│   ├── compose.dev.yml          # Dev overrides (hot reload, bind mounts, Traefik dashboard)
│   ├── compose.test.yml         # Loopback-only throwaway Postgres for pytest (127.0.0.1:54329)
│   └── compose.sonar.yml        # Loopback-only local SonarQube (127.0.0.1:9000)
├── .scripts/                    # Setup / helper scripts (bash)
│   ├── setup.sh                 # Bootstrap: deps, .env, pre-commit install
│   ├── dev.sh                   # Bring up the dev stack
│   ├── lint.sh                  # Run all linters/formatters locally
│   ├── test-db.sh               # Start/stop the throwaway Postgres pytest needs
│   ├── ingest.sh                # Run the CSV ingest CLI inside the backend container
│   └── sonar.sh                 # Coverage + local SonarQube scan, exits non-zero on gate failure
├── backend/                     # ← Python app root AND working dir for backend cmds
│   ├── pyproject.toml           # Deps + tool config (uv, ruff, black, pytest)
│   ├── uv.lock                  # Committed lockfile
│   ├── alembic.ini
│   ├── main.py                  # App factory, lifespan, router registration
│   ├── enums.py                 # Shared enums (single source of truth)
│   ├── errors.py                # Custom exceptions + exception handlers
│   ├── core/
│   │   ├── config.py            # Settings via pydantic-settings
│   │   ├── security.py
│   │   ├── logging.py
│   │   ├── cache.py              # Thin async Redis wrapper (get_json / set_json / incr)
│   │   └── text.py               # normalize_persian() — the single text normaliser
│   ├── db/
│   │   ├── base.py              # DeclarativeBase
│   │   ├── session.py           # Async engine + session factory
│   │   └── migrations/          # Alembic env.py + versions/
│   ├── api/
│   │   ├── health.py            # Liveness / readiness
│   │   └── v1/
│   │       ├── router.py        # Aggregates all v1 endpoint routers
│   │       └── endpoints/       # One thin module per resource
│   ├── models/                  # SQLAlchemy ORM models (persistence layer)
│   ├── schemas/                 # Pydantic models (transport layer)
│   ├── services/                # Business logic (classes)
│   ├── repositories/            # Data access (classes, one per aggregate)
│   ├── ranking/                 # Pure-Python ranking + price estimator — NO I/O imports
│   ├── ingest/                  # CSV → DB pipeline + CLI
│   ├── llm/                     # Pydantic AI agent, rules fallback, eval
│   ├── dependencies/            # FastAPI Depends providers (DI wiring)
│   └── tests/                   # pytest suite, mirrors package layout
└── frontend/                    # ← Next.js app root AND working dir for frontend cmds
    ├── package.json
    ├── next.config.ts           # Must set `output: "standalone"` for Docker
    ├── tsconfig.json
    ├── bun.lock                 # Committed lockfile
    └── src/
        ├── app/                 # App Router routes, layouts, pages
        ├── components/          # Reusable UI components
        ├── lib/                 # Typed API client, utilities
        └── hooks/               # Custom React hooks
```

**Never edit generated/managed files**: `__pycache__/`, `*.pyc`, `uv.lock`,
`bun.lock`, `.next/`, and applied Alembic version files. **Never commit `.env`**
(it is gitignored; `example.env` is the template). Add a repo-root `.dockerignore`
that excludes `node_modules/`, `.venv/`, `.next/`, and `__pycache__/`.

---

## 3. Tech Stack

| Area              | Choice                                  |
| ----------------- | --------------------------------------- |
| Backend language  | Python 3.14                             |
| Backend framework | FastAPI                                 |
| Validation        | Pydantic v2 / pydantic-settings         |
| ORM               | SQLAlchemy 2.0 (async)                  |
| Migrations        | Alembic                                 |
| Database          | PostgreSQL 18 (`pgvector/pgvector:pg18`, `pg_trgm`); UUIDv8 primary keys |
| Backend pkg mgr   | **uv**                                  |
| Lint              | **Ruff**                                |
| Format            | **Black**                               |
| Tests             | **pytest** (+ pytest-asyncio)           |
| Frontend          | Next.js + TypeScript                    |
| Frontend pkg mgr  | **Bun**                                 |
| Containers        | Docker + Compose (`.docker/`)           |
| Reverse proxy     | **Traefik v3** — single entry point, only exposed port |
| Cache             | Redis 8 (no persistence)                |
| LLM               | Pydantic AI (`pydantic-ai-slim[google,openai]`) |
| CI/CD             | GitHub Actions                          |
| Security scans    | **Semgrep** (SAST) + **Gitleaks** (secrets) |
| Code quality      | SonarQube Community Build (local) + Semgrep + Gitleaks |
| Registry          | Docker Hub (`pejmans21/...`)            |

---

## 4. Environment Variables

`example.env` is the committed template. Copy it to `.env` (gitignored) before
running anything locally or via Compose:

```bash
cp example.env .env
```

Representative keys:

```dotenv
# Backend
ENV=development
DATABASE_URL=postgresql+asyncpg://app:app@db:5432/app
TEST_DATABASE_URL=postgresql+asyncpg://app:app@127.0.0.1:54329/app_test
REDIS_URL=redis://redis:6379/0
# LLM — Gemini in development, any OpenAI-compatible API in production.
# Empty LLM_API_KEY falls back to the deterministic rules parser.
LLM_PROVIDER=google
LLM_MODEL=gemini-3.7-flash
LLM_API_KEY=
LLM_BASE_URL=
# Frontend — Server Components call the backend directly on the Compose network;
# the browser uses /api/v1 on the same origin through Traefik (no variable needed).
API_INTERNAL_URL=http://backend:8000
# Postgres (consumed by the db service in compose)
POSTGRES_USER=app
POSTGRES_PASSWORD=app
POSTGRES_DB=app
# SonarQube (local developer tool)
SONAR_TOKEN=
```

Because everything sits behind Traefik, browser requests are **same-origin**
(`/api/v1`, added in `frontend/src/lib/api/base.ts` only). Server-side calls from
Next.js (Server Components) run inside the network and hit the backend directly at
`API_INTERNAL_URL` (`http://backend:8000`) — never the public host.

Backend code reads config **only** through `core/config.py` (a `Settings` class);
never read `os.environ` elsewhere.

---

## 5. Common Commands

> Use the package managers below. Do **not** call `pip`, `python -m venv`, `npm`,
> `yarn`, or `pnpm` in this repo.

### Backend (uv) — run from `backend/`

```bash
uv sync                      # Install/refresh deps into the venv
uv add <pkg>                 # Add a runtime dependency
uv add --dev <pkg>           # Add a dev/test dependency
uv lock                      # Refresh uv.lock after editing pyproject.toml
uv run fastapi dev main.py   # Run the API with hot reload (dev)
uv run fastapi run main.py   # Run the API (production-style)
uv run pytest                # Run the test suite
uv run pytest path::test_x   # Run a single test
uv run ruff check .          # Lint
uv run ruff check . --fix    # Lint + autofix
uv run black .               # Format
uv run python -m llm.eval    # Live LLM accuracy eval (needs LLM_API_KEY; never in CI)
```

### Database / Migrations (Alembic) — run from `backend/`

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head           # Apply migrations
uv run alembic downgrade -1           # Roll back one revision
uv run alembic current                # Show current revision
```

### Frontend (Bun) — run from `frontend/`

```bash
bun install                  # Install dependencies
bun run dev                  # Start Next.js dev server
bun run build                # Production build (standalone)
bun run start                # Serve the production build
bun run lint                 # ESLint
bun test                     # Run frontend tests
```

### Docker / Compose — run from the repo root

```bash
# Production-like stack
docker compose -f .docker/compose.yml up --build

# Dev stack (hot reload + bind mounts; base file + overrides)
docker compose -f .docker/compose.yml -f .docker/compose.dev.yml up --build

# Tear down (keep volumes)
docker compose -f .docker/compose.yml down
```

The whole app is reachable at **`http://localhost`** (Traefik, port 80). The backend
and frontend do **not** publish host ports — `http://localhost:8000` /
`http://localhost:3000` will not work, by design.

### Quality & Security (local)

```bash
pre-commit install           # Install git hooks (run once after cloning)
pre-commit run --all-files   # Run every hook against the whole repo
docker run --rm -v "$PWD:/repo:ro" zricethezav/gitleaks:v8.30.0 detect --source /repo --no-banner  # Scan working tree for secrets
semgrep ci                   # Run Semgrep with the project ruleset
./.scripts/sonar.sh          # Coverage + local SonarQube quality gate
```

### Setup scripts (`.scripts/`)

```bash
./.scripts/setup.sh          # Bootstrap a fresh clone
./.scripts/dev.sh            # Start the dev stack
./.scripts/lint.sh           # Run all linters/formatters
./.scripts/test-db.sh        # Start the throwaway Postgres that `uv run pytest` needs
./.scripts/ingest.sh <csv>   # Load a Divar CSV (runs inside the backend container)
./.scripts/sonar.sh          # Coverage + local SonarQube scan (needs SONAR_TOKEN)
./.scripts/smoke.sh          # agent-browser acceptance run against the running stack
```

---

## 6. Backend Conventions

The backend is **object-oriented** and follows a strict **layered architecture**.
Data flows in one direction; each layer only talks to the layer directly beneath it.

```
HTTP Request
   ↓
api/v1/endpoints/   (controllers — thin, no business logic)
   ↓  depends on
services/           (business logic — classes, orchestration, rules)
   ↓  depends on
repositories/       (data access — classes, all SQLAlchemy queries live here)
   ↓  depends on
models/             (SQLAlchemy ORM)
```

`schemas/` (Pydantic) is the contract at the API boundary. ORM models never leave
the repository/service layer untranslated — convert to a Pydantic schema before
returning from an endpoint.

### 6.1 Clean Code Rules (non-negotiable)

- **Single Responsibility** — every function does exactly one thing. If a function
  needs the word "and" to be described, split it.
- **Clear, intention-revealing names** — no abbreviations, no single letters
  (except trivial loop indices). Functions are **verbs** (`create_user`,
  `calculate_total`); classes are **nouns** (`UserService`, `OrderRepository`).
- **Type hints everywhere** — every function signature is fully annotated. Use
  modern syntax: `list[int]`, `str | None`, `dict[str, Any]`.
- **No business logic in endpoints** — controllers parse input, call a service, and
  shape the response. Nothing else.
- **No raw SQL or ORM queries outside `repositories/`.** Even the readiness
  check's database ping lives in `repositories/health_repository.py`.
- **Dependency injection** via FastAPI `Depends`. Classes receive their
  collaborators through `__init__`; do not instantiate dependencies inside methods.
- **Prefer composition over inheritance.** Use inheritance only for genuine
  is-a relationships (e.g. a shared `BaseRepository`).
- **Keep functions short** (aim ≤ ~30 lines). Extract private helpers (prefixed `_`)
  rather than growing one method.
- **Fail loudly** — raise specific exceptions from `errors.py`, never return `None`
  to signal an error, never swallow exceptions silently.
- **No magic values** — use the enums in `enums.py` or named constants.

### 6.2 Reference Patterns

**Repository** — owns persistence, no business rules:

```python
class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def add(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user
```

**Service** — owns business logic, depends on repositories:

```python
class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def get_user(self, user_id: int) -> UserRead:
        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return UserRead.model_validate(user)
```

**Endpoint** — thin controller, wires DI, returns schemas:

```python
@router.get("/{user_id}", response_model=UserRead)
async def read_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
) -> UserRead:
    return await service.get_user(user_id)
```

### 6.3 Pydantic (v2)

- Request/response models live in `schemas/`, separate from ORM `models/`.
- Use distinct schemas per operation when they differ: `UserCreate`, `UserUpdate`,
  `UserRead`.
- Read models that map from ORM objects set
  `model_config = ConfigDict(from_attributes=True)`.
- All app configuration goes through `Settings(BaseSettings)` in `core/config.py`.

### 6.4 SQLAlchemy (2.0, async)

- Use the 2.0 typed declarative style: `Mapped[...]` + `mapped_column(...)`.
- All models inherit a single `Base(DeclarativeBase)` from `db/base.py`.
- Sessions are async (`AsyncSession`), provided via a `get_session` dependency;
  repositories receive the session, never create their own engine.
- Keep the session scoped per request; commit at the boundary, not in repositories.

**Primary keys — always UUIDv8.** Every table's primary key is a `UUID` column
(Postgres native `uuid` type) holding a **UUIDv8** value. Generate it **in the
application** with Python 3.14's `uuid.uuid8()` — Postgres 18 ships native
`uuidv7()`/`uuidv4()` but has **no** `uuidv8()` generator, so the DB cannot produce
it server-side. Define the key once in a shared mixin so every model is consistent:

```python
# db/ids.py
import time
import uuid

def new_uuid8() -> uuid.UUID:
    """Time-ordered UUIDv8: a 48-bit millisecond timestamp in the leading field,
    pseudo-random in the rest. Keeps index locality (sortable inserts) while
    staying inside the application-defined v8 space."""
    timestamp_ms = (time.time_ns() // 1_000_000) & 0xFFFFFFFFFFFF
    return uuid.uuid8(a=timestamp_ms)
```

```python
# db/base.py
import uuid
from sqlalchemy import Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from db.ids import new_uuid8

class Base(DeclarativeBase):
    pass

class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),                 # → native `uuid` column on Postgres
        primary_key=True,
        default=new_uuid8,      # generated app-side, never server_default
    )
```

> **Why the timestamp prefix:** a bare `uuid.uuid8()` is fully random and is *not*
> time-ordered, which scatters inserts across the index — the exact problem
> sequential keys are meant to avoid. Seeding the leading 48 bits with a timestamp
> (above) restores sortability. UUIDv8 is the "application-defined" version by
> design, so this layout is ours to choose; keep `new_uuid8()` the single place it
> lives. If you ever want standards-native, DB-generated time-ordered keys instead,
> Postgres 18's `uuidv7()` (+ Python `uuid.uuid7()`) is the drop-in alternative —
> but the repo standard is UUIDv8 unless that changes here.

### 6.5 Errors

- Define domain exceptions in `errors.py` (e.g. `UserNotFoundError`,
  `DuplicateResourceError`), each carrying enough context to build an HTTP response.
- Register exception handlers in `main.py` that translate them into structured JSON
  with the correct status code. Endpoints never build error responses by hand.

---

## 7. Frontend Conventions

- **App Router** under `src/app`. Default to Server Components; add `"use client"`
  only when interactivity, state, or browser APIs require it.
- **TypeScript strict mode** — no `any` unless unavoidable and commented.
- Components are small and single-purpose; co-locate component-specific styles.
- All backend calls go through the typed client in `src/lib/api/` (`apiGet`,
  `apiPost`, `useApi`); `base.ts` is the only place the `/api/v1` prefix and
  `API_INTERNAL_URL` are known. Every fetch is `cache: "no-store"`.
- `src/lib/api/types.ts` mirrors `backend/schemas/*.py` by hand — change both together.
- The UI never invents data: loading skeletons, the backend's 422 message inline, and
  «سرویس جست‌وجو در دسترس نیست» with retry for everything else. Branch on
  `ApiError.code`/`status`, never on message text.
- Server Components that fetch on every request call **`await connection()`** first —
  Next 16 would otherwise prerender them (and hit the API) at build time.
- Keep server-only secrets out of `NEXT_PUBLIC_*` variables.
- `next.config.ts` must set `output: "standalone"` so the Docker image stays small.
- Run `bun run lint` before considering frontend work done.

---

## 8. Testing

- Tests use **pytest** under `backend/tests/`, mirroring the package structure
  (`tests/services/test_user_service.py`, etc.).
- Use `pytest-asyncio` for async tests.
- Test each layer in isolation: mock the repository when testing a service; use a
  test database/transaction for repository tests.
- Name tests for the behavior under test: `test_get_user_raises_when_not_found`.
- Add/update tests in the same change as the code. A change is not done until
  `uv run pytest` passes.
- Repository and API tests need `./.scripts/test-db.sh`. Tests never call a real LLM
  (`ALLOW_MODEL_REQUESTS = False`). Ranking changes must keep the golden queries in
  `tests/api/test_search_api.py` green — the verdict thresholds they check
  (`cheap ≤ −5%`, `expensive ≥ +6%`) are the single `CHEAP_DIFF_PCT` /
  `EXPENSIVE_DIFF_PCT` constants in `ranking/weights.py`.

---

## 9. Linting & Formatting

Two tools, clear division of labor — run both before finishing backend work:

- **Ruff** = linting (and import sorting): `uv run ruff check . --fix`.
- **Black** = formatting: `uv run black .`.

Keep Ruff's formatter **off** (Black owns formatting) so they never conflict.
Recommended `pyproject.toml` snippet:

```toml
[tool.black]
line-length = 88
target-version = ["py314"]

[tool.ruff]
line-length = 88
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "SIM"]
```

---

## 10. Pre-commit

Hooks run automatically on `git commit` after `pre-commit install`. They enforce the
backend formatting/linting rules and block committed secrets. The file is
`.pre-commit-config.yaml` — pre-commit's default name, so no `-c` flag is needed.

Reference config (pin to current tags; run `pre-commit autoupdate` to refresh):

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: [--maxkb=1024]
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.16.8
    hooks:
      - id: ruff            # lint only (Black handles formatting)
        args: [--fix]
        files: ^backend/
  - repo: https://github.com/psf/black
    rev: 26.5.1
    hooks:
      - id: black
        files: ^backend/
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.30.0
    hooks:
      - id: gitleaks
```

Semgrep is intentionally CI-only (heavier); it does not run as a pre-commit hook.

---

## 11. Docker (`.docker/`)

Build context for every Dockerfile is the **repo root** (so they can copy `backend/`
and `frontend/`). Compose passes `context: ..`.

**Port policy:** only the `traefik` service publishes a host port (`80`, and `443` if
you add TLS). `backend`, `frontend`, `db`, and `redis` use `expose` (internal network
only) and are never mapped to the host. Everything is served behind Traefik.

**Loopback-only developer-tool exceptions:** three tools outside the application
stack bind a port on `127.0.0.1` only, never `0.0.0.0`, so they stay unreachable off
the host and don't count against the "only the edge publishes a port" rule:

- `.docker/compose.test.yml` — throwaway Postgres for pytest, `127.0.0.1:54329`.
- `.docker/compose.sonar.yml` — local SonarQube, `127.0.0.1:9000`.
- `.docker/compose.dev.yml` — the Traefik dashboard, `127.0.0.1:8080` (dev only).

### 11.1 `backend.Dockerfile` (reference)

```dockerfile
FROM python:3.14-slim AS base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

FROM base AS builder
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM base AS runtime
WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]
```

### 11.2 `frontend.Dockerfile` (actual)

`bun run build` segfaults under Bun's Node-compat shim in this container (Next 16 +
Turbopack, confirmed on linux/arm64). Bun still installs dependencies fine, so `deps`
keeps `oven/bun:1`; the `builder` and `runtime` stages run on `node:22-slim` and build
with `next` directly instead of through `bun run`:

```dockerfile
FROM oven/bun:1 AS deps
WORKDIR /app
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile

FROM node:22-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./
ENV NEXT_PUBLIC_API_URL=/api
RUN node node_modules/.bin/next build

FROM node:22-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
```

> Requires `output: "standalone"` in `next.config.ts`. Upgrade path: retry
> `bun run build` for the builder stage when a Bun release fixes the crash.
>
> `compose.dev.yml` builds the dev frontend from the `builder` stage as image
> `pejmans21/torobcar-frontend-dev` and runs
> `node node_modules/.bin/next dev --hostname 0.0.0.0 --port 3000` — the `builder`
> stage still has Bun's full `node_modules` install (no `next` CLI survives into the
> pruned `runtime` stage).

### 11.3 Traefik (actual — configured entirely by container labels)

Traefik is the single public entry point; there is no separate Dockerfile or config
file — everything is Docker-provider labels on `backend` and `frontend` in
`compose.yml`:

```yaml
traefik:
  image: traefik:v3
  command:
    - --providers.docker=true
    - --providers.docker.exposedbydefault=false
    - --entrypoints.web.address=:80
  ports: ["80:80"] # the ONLY published port
  volumes: ["/var/run/docker.sock:/var/run/docker.sock:ro"]

backend:
  labels:
    - traefik.enable=true
    - traefik.http.services.backend.loadbalancer.server.port=8000
    # Explicit priorities: Traefik's default (rule length) would rank the long
    # `api` rule above `api-search`, and the rate limit would never apply.
    - traefik.http.routers.api-search.rule=PathPrefix(`/api/v1/search`)
    - traefik.http.routers.api-search.priority=100
    - traefik.http.routers.api-search.entrypoints=web
    - traefik.http.routers.api-search.service=backend
    - traefik.http.routers.api-search.middlewares=search-ratelimit
    - traefik.http.middlewares.search-ratelimit.ratelimit.average=10
    - traefik.http.middlewares.search-ratelimit.ratelimit.burst=20
    # LLM-backed and estimator routes: tighter limit, same explicit priority tier.
    - traefik.http.routers.api-assistant.rule=PathPrefix(`/api/v1/assistant`) || PathPrefix(`/api/v1/estimates`)
    - traefik.http.routers.api-assistant.priority=100
    - traefik.http.routers.api-assistant.entrypoints=web
    - traefik.http.routers.api-assistant.service=backend
    - traefik.http.routers.api-assistant.middlewares=assistant-ratelimit
    - traefik.http.middlewares.assistant-ratelimit.ratelimit.average=5
    - traefik.http.middlewares.assistant-ratelimit.ratelimit.burst=10
    - traefik.http.routers.api.rule=PathPrefix(`/api`) || PathPrefix(`/health`)
    - traefik.http.routers.api.priority=50
    - traefik.http.routers.api.entrypoints=web
    - traefik.http.routers.api.service=backend

frontend:
  labels:
    - traefik.enable=true
    - traefik.http.services.frontend.loadbalancer.server.port=3000
    - traefik.http.routers.frontend.rule=PathPrefix(`/`)
    - traefik.http.routers.frontend.priority=1
    - traefik.http.routers.frontend.entrypoints=web
```

> Router priorities are explicit, not left to Traefik's default (longest-rule-wins)
> ranking, because the `/api` catch-all rule is textually longer than `/api/v1/search`
> and would otherwise outrank it — silently skipping the rate-limit middleware.
> Traefik proxies WebSocket/HMR upgrades without extra configuration. For TLS, add a
> `websecure` entrypoint (`--entrypoints.websecure.address=:443`) and publish `443` on
> the `traefik` service only.

### 11.4 Compose (actual)

`compose.yml` defines five services — `traefik`, `backend`, `frontend`, `db`
(`pgvector/pgvector:pg18`), `redis`. **Only `traefik` maps a host port**; the rest
use `expose`. Each service reads `../.env` and images match the registry:

```yaml
name: torobcar
services:
  traefik:
    image: traefik:v3
    command:
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --entrypoints.web.address=:80
    ports: ["80:80"] # the ONLY published port
    volumes: ["/var/run/docker.sock:/var/run/docker.sock:ro"]
    depends_on: [backend, frontend]

  backend:
    build: { context: .., dockerfile: .docker/backend.Dockerfile }
    image: pejmans21/torobcar-backend
    env_file: ../.env
    expose: ["8000"] # internal only — no host mapping
    depends_on:
      db: { condition: service_healthy }
      redis: { condition: service_healthy }
    labels:
      - traefik.enable=true
      - traefik.http.services.backend.loadbalancer.server.port=8000
      # Explicit priorities: Traefik's default (rule length) would rank the long
      # `api` rule above `api-search`, and the rate limit would never apply.
      - traefik.http.routers.api-search.rule=PathPrefix(`/api/v1/search`)
      - traefik.http.routers.api-search.priority=100
      - traefik.http.routers.api-search.entrypoints=web
      - traefik.http.routers.api-search.service=backend
      - traefik.http.routers.api-search.middlewares=search-ratelimit
      - traefik.http.middlewares.search-ratelimit.ratelimit.average=10
      - traefik.http.middlewares.search-ratelimit.ratelimit.burst=20
      # LLM-backed and estimator routes: tighter limit, same explicit priority tier.
      - traefik.http.routers.api-assistant.rule=PathPrefix(`/api/v1/assistant`) || PathPrefix(`/api/v1/estimates`)
      - traefik.http.routers.api-assistant.priority=100
      - traefik.http.routers.api-assistant.entrypoints=web
      - traefik.http.routers.api-assistant.service=backend
      - traefik.http.routers.api-assistant.middlewares=assistant-ratelimit
      - traefik.http.middlewares.assistant-ratelimit.ratelimit.average=5
      - traefik.http.middlewares.assistant-ratelimit.ratelimit.burst=10
      - traefik.http.routers.api.rule=PathPrefix(`/api`) || PathPrefix(`/health`)
      - traefik.http.routers.api.priority=50
      - traefik.http.routers.api.entrypoints=web
      - traefik.http.routers.api.service=backend

  frontend:
    build: { context: .., dockerfile: .docker/frontend.Dockerfile }
    image: pejmans21/torobcar-frontend
    env_file: ../.env
    expose: ["3000"] # internal only — no host mapping
    depends_on: [backend]
    labels:
      - traefik.enable=true
      - traefik.http.services.frontend.loadbalancer.server.port=3000
      - traefik.http.routers.frontend.rule=PathPrefix(`/`)
      - traefik.http.routers.frontend.priority=1
      - traefik.http.routers.frontend.entrypoints=web

  db:
    image: pgvector/pgvector:pg18
    env_file: ../.env
    expose: ["5432"] # internal only — no host mapping
    # Postgres 18 image moved PGDATA; mount the PARENT dir, NOT .../data
    volumes: ["pgdata:/var/lib/postgresql"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]

  redis:
    image: redis:8-alpine
    command: ["redis-server", "--save", "", "--maxmemory", "256mb", "--maxmemory-policy", "allkeys-lru"]
    expose: ["6379"] # internal only — cache, no persistence
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]

volumes:
  pgdata:
```

`compose.dev.yml` overrides for local development — hot reload, bind mounts, and the
Traefik dashboard on `127.0.0.1:8080` (loopback-only, dev exception — see above).
Traefik still fronts everything (no extra publicly-reachable ports):

```yaml
services:
  traefik:
    command:
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --entrypoints.web.address=:80
      - --api.insecure=true # dashboard, development only
    ports: ["80:80", "127.0.0.1:8080:8080"]
  backend:
    command: sh -c "alembic upgrade head && fastapi dev main.py --host 0.0.0.0 --port 8000"
    volumes: ["../backend:/app", "/app/.venv"] # anonymous volume keeps the image's .venv
  frontend:
    build: { context: .., dockerfile: .docker/frontend.Dockerfile, target: builder }
    image: pejmans21/torobcar-frontend-dev
    command: node node_modules/.bin/next dev --hostname 0.0.0.0 --port 3000
    volumes: ["../frontend:/app", "/app/node_modules"]
```

**`.docker/compose.test.yml`** and **`.docker/compose.sonar.yml`** are separate
Compose projects (`torobcar-test`, `torobcar-sonar`) for developer tooling, not part
of the application stack — see the loopback-only exceptions above.

---

## 12. CI/CD (GitHub Actions)

Three workflows under `.github/workflows/`:

1. **`ci.yml`** — on every pull request and push to `main`. Two parallel jobs:
   - **backend**: a `pgvector/pgvector:pg18` service container (`TEST_DATABASE_URL`)
     → `astral-sh/setup-uv` → `uv sync` → `uv run ruff check .` →
     `uv run black --check .` → `uv run pytest --cov=. --cov-report=xml`.
   - **frontend**: `oven-sh/setup-bun` → `bun install` → `bun run lint` →
     `bunx tsc --noEmit` → `bun test`.
2. **`security.yml`** — on pull request, push to `main`, and a weekly schedule.
   Runs Semgrep and Gitleaks (see §13).
3. **`docker-publish.yml`** — on push to `main` and on `v*` tags. Builds and pushes
   two images (backend, frontend) to Docker Hub.

Gate publishing on green checks: mark the `ci.yml` and `security.yml` jobs as
**required status checks** in branch protection so images only ship from passing code.

**`docker-publish.yml`** (actual — matrix builds both images):

```yaml
name: docker-publish
on:
  push:
    branches: [main]
    tags: ["v*"]
permissions:
  contents: read
jobs:
  build-and-push:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        include:
          - { service: backend,  image: pejmans21/torobcar-backend,  dockerfile: .docker/backend.Dockerfile }
          - { service: frontend, image: pejmans21/torobcar-frontend, dockerfile: .docker/frontend.Dockerfile }
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ matrix.image }}
          tags: |
            type=ref,event=branch
            type=semver,pattern={{version}}
            type=sha
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: ${{ matrix.dockerfile }}
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

**Required repository secrets** (Settings → Secrets and variables → Actions):

- `DOCKERHUB_USERNAME` — the Docker Hub account (`pejmans21`).
- `DOCKERHUB_TOKEN` — a Docker Hub access token (not the password).

---

## 13. Security

Three complementary scanners:

- **Gitleaks** — secret detection. Runs as a pre-commit hook (blocks secrets before
  they land) **and** in `security.yml` (catches anything that slipped through).
- **Semgrep** — static analysis (SAST) for code vulnerabilities and anti-patterns.
  CI-only.
- **SonarQube Community Build** — local only, via `./.scripts/sonar.sh`. GitHub-hosted
  runners cannot reach a developer-machine server, and Community Build analyses one
  branch only (no PR/branch analysis), so it isn't in CI. Adds duplication,
  maintainability, reliability, coverage, and its own security rules; the built-in
  "Sonar way" quality gate must pass (new-code coverage ≥ 80%, duplication ≤ 3%, no
  new issues, all new security hotspots reviewed).

**`security.yml`** (reference):

```yaml
name: security
on:
  pull_request:
  push:
    branches: [main]
  schedule:
    - cron: "0 6 * * 1"   # weekly, Monday 06:00 UTC
permissions:
  contents: read
jobs:
  semgrep:
    runs-on: ubuntu-latest
    container: semgrep/semgrep
    steps:
      - uses: actions/checkout@v4
      - run: semgrep ci
        env:
          SEMGREP_RULES: "p/default p/python p/security-audit"
  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2
```

A finding from either scanner fails the workflow. Treat secret leaks as urgent:
rotate the credential immediately, then purge it from history — fixing the file
alone is not enough.

---

## 14. Definition of Done (checklist for any change)

- [ ] Code follows the layered architecture and clean-code rules in §6.
- [ ] All new/changed functions are fully type-hinted and single-purpose.
- [ ] New behavior is covered by pytest tests, and `uv run pytest` passes.
- [ ] `uv run ruff check .` and `uv run black .` are clean (backend).
- [ ] `bun run lint` is clean (frontend).
- [ ] `pre-commit run --all-files` passes.
- [ ] DB schema changes have a matching Alembic migration that applies cleanly.
- [ ] New tables use a UUIDv8 primary key via the shared mixin (no serial/bigint PKs).
- [ ] Affected Docker images build (`docker compose -f .docker/compose.yml build`).
- [ ] All traffic is routed through Traefik; only the `traefik` service publishes a
      host port (new services use `expose`, never `ports`).
- [ ] No Semgrep or Gitleaks findings.
- [ ] `./.scripts/sonar.sh` passes the quality gate.
- [ ] Ranking changes keep the golden-query suite green.
- [ ] Frontend changes keep `bunx tsc --noEmit` clean and `./.scripts/smoke.sh` passing
      against the running stack.
- [ ] No secrets, generated files, or lockfiles edited by hand.
