# Torobcar Backend — Search Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend that ingests the Divar vehicles CSV into Postgres and serves a soft-ranked, near-miss-aware search API behind Traefik, with Redis caching and Pydantic AI query parsing.

**Architecture:** Layered FastAPI app (endpoints → services → repositories → models). Search runs in four stages: resolve free-text vehicle mentions against a catalog (pg_trgm), fetch ≤ 5,000 candidates in one SQL query, rank them with a pure-Python `ListingRanker`, cache the ranked ID list in Redis for stable pagination. Free text becomes a typed `SearchIntent` via a Pydantic AI agent with a deterministic regex fallback. Price estimates and deal scores are precomputed at ingest.

**Tech Stack:** Python 3.14 · uv · FastAPI · Pydantic v2 · SQLAlchemy 2.0 async + asyncpg · Alembic · Postgres 18 (`pgvector/pgvector:pg18`, `pg_trgm`) · Redis 8 · `pydantic-ai-slim[google,openai]` 2.x · Traefik v3 · pytest + pytest-asyncio · Ruff · Black · SonarQube Community Build.

**Spec:** `docs/superpowers/specs/2026-09-18-torobcar-backend-search-core-design.md` — read it before starting. Section numbers below (§) refer to it.

## Global Constraints

- **Python 3.14**, managed with **uv** only. Never `pip`, `poetry`, `python -m venv`. All backend commands run from `backend/`. Never hand-edit `uv.lock`.
- Frontend tooling is **bun** only; the committed lockfile is `frontend/bun.lock`.
- Layered architecture (`CLAUDE.md` §6): endpoints contain no business logic; **no SQLAlchemy query outside `repositories/`**; services get collaborators through `__init__`; DI via FastAPI `Depends` using the `Annotated[...]` form.
- Every function fully type-hinted, modern syntax (`list[int]`, `str | None`). Functions ≤ ~30 lines, single-purpose, intention-revealing names, no single-letter names, no magic values (use `enums.py` or named constants).
- Fail loudly: raise exceptions from `errors.py`; never return `None` to signal an error; never swallow exceptions silently (the two deliberate exceptions — cache outage and LLM outage — log at WARNING and are commented as such).
- Config is read **only** in `core/config.py` (`Settings`). No `os.environ` elsewhere.
- Every table's primary key is a UUIDv8 from `db/ids.py::new_uuid8` via `UUIDPrimaryKeyMixin`.
- `ranking/` is **pure Python with no I/O**: it must not import `sqlalchemy`, `redis`, `fastapi`, or `pydantic_ai`.
- The LLM never writes SQL. Its only output type is `SearchIntent`.
- Money is integer **toman** everywhere in the backend and API.
- Only the `traefik` service publishes a host port in `.docker/compose.yml`. The two documented exceptions are loopback-bound developer tools in separate Compose projects: `.docker/compose.test.yml` (`127.0.0.1:54329`) and `.docker/compose.sonar.yml` (`127.0.0.1:9000`).
- Tests never call a real LLM: `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` is set in `tests/conftest.py`.
- `assets/*.csv` stays untracked (sellers' phone numbers). The committed fixture blanks `description`.
- `git add` explicit paths only — never `git add -A` / `git add .` (the repo has untracked `prototype/`, `brag-output/`, `graphify-out/`).
- Conventional commits, each ending with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- A backend task is done only when `uv run pytest`, `uv run ruff check .` and `uv run black --check .` pass.

## Facts verified while writing this plan (2026-09-18)

- `uv sync` on CPython 3.14.6 resolves and imports every dependency: fastapi 0.141, sqlalchemy 2.0.54, asyncpg 0.31, alembic 1.20, pydantic 2.13, pydantic-settings 2.15, redis 8.1, pydantic-ai-slim 2.45 (+ google-genai 2.24, openai 3.15), pytest 9.1, pytest-asyncio 1.4, pytest-cov 7.1, ruff 0.16.8, black 26.5.1. `uuid.uuid8` exists. **The spec's Python 3.14 risk is cleared.**
- Pydantic AI 2.45: `Agent(model, output_type=..., instructions=..., retries=...)`; `result.output`; `agent.override(model=...)`; `TestModel(custom_output_args={...})`; `FunctionModel(fn)` where `fn(messages, info)` returns `ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {...})])`; invalid structured output after retries raises `UnexpectedModelBehavior` (subclass of `AgentRunError`). Imports: `pydantic_ai.models.google.GoogleModel`, `pydantic_ai.providers.google.GoogleProvider`, `pydantic_ai.models.openai.OpenAIChatModel`, `pydantic_ai.providers.openai.OpenAIProvider`. Current Gemini flash id in the docs: `gemini-3.7-flash`. Set `PYDANTIC_AI_NO_BANNER=1` to silence the startup banner.
- Nothing infrastructural exists yet: no `backend/`, `.docker/`, `.github/`, `.scripts/`, `example.env`, pre-commit config or `.dockerignore`. `frontend/next.config.ts` already sets `output: "standalone"`.
- CSV vocabularies (all 14,652 rows): relative-time phrases are exactly `نیم ساعت پیش`, `N ساعت پیش`, `دیروز`, `پریروز`, `N روز پیش`, `هفته پیش`, `N هفته پیش`, `ماه پیش`, `N ماه پیش`, `سال پیش`, `N سال پیش`, always followed by ` در <city>[، <district>[، <street>]]`. Insurance is `N ماه`. Years are `NNNN`, `NNNN - NNNN`, `قبل از NNNN`, `قبل از NNNN - قبل از NNNN`, or `N,NNN`. Prices are `‏N,NNN,NNN تومان` (leading RLM). Image URLs are separated by ` | `.

## Deliberate deviations from the spec

Every item below was found by running the code against the real data or a real
Postgres 18 while writing this plan. Items 6–8 change ranking behaviour and are
recorded in the spec's §15 "Amendments".

1. **Test database** — spec §11 says "compose `db` locally", but `db` publishes no host port. The plan adds `.docker/compose.test.yml`: a throwaway Postgres on `127.0.0.1:54329` (tmpfs, separate Compose project).
2. **Ingest runs inside the backend container** (`.scripts/ingest.sh`), because `db` and `redis` are not reachable from the host.
3. **`قبل از Y` → `Y − 1`** for every year (766 rows across categories), not only `1366 → 1365`. Gregorian years (> 1420) are converted with `− 621`.
4. `cities.name_normalized` is added; `vehicle_catalog.brand` / `.model` are stored **normalised** (the raw string lives in `trim`).
5. The pre-commit file is named `.pre-commit-config.yaml` (pre-commit's default), resolving the `CLAUDE.md` §10 naming caveat.
6. **Deal-score slope 2.4 → 1.0.** The frontend's 2.4 was tuned on synthetic prices within ±10%. Real prices have an IQR of −10%…+12%, so 2.4 pins 25% of scores at the 5/99 clamp; 1.0 pins under 5% (quartiles 60/71/80).
7. **Suspect-price guard (new column `listings.price_suspect`).** 6.6% of cars and 22% of motorcycles are priced more than 40% under (or 100% over) their estimate — deposits and placeholders such as a 10,000,000-toman MVM X55 against a 4-billion estimate. Unguarded they become the "best deals" and exact matches for every budget query. Suspect listings keep their listed price in the API, but the ranker sees `price = NULL` (neutral, label «قیمت توافقی»), they get no `diff_pct` / `deal_score`, and `verdict = unknown`.
8. **Two ranking tiers ahead of `rank`.** (a) Exact matches precede near-misses for every sort, including relevance — with `rank` alone a great-deal near-miss outranks a poor-deal exact match. (b) Listings of the requested model precede listings that only share its brand — with `rank` alone Peugeot 405s outranked real 206s for a "206" query on the real data. `rank` still orders listings inside each tier.
9. **Upsert batches of 500, not 1,000** — asyncpg allows 32,767 bind parameters per statement and a listing row has ~35 columns.
10. **`GET /search` takes one query-parameter model (`SearchParams`)** — FastAPI cannot combine a query model with individual `Query()` parameters (it then expects a single `overrides` parameter and returns 422).
11. The committed fixture rounds coordinates to 3 decimals (~100 m) in addition to blanking free text.
12. **Search log line is simpler than spec §10**: `parsed_by`, `cache_hit`, `total`, `duration_ms` — no per-stage timings or query hash. Ranking measured 7 ms and the whole uncached search well under 100 ms on the real data, so stage timings would be noise today; add them in `SearchService._log` when a latency problem needs locating.
13. **14 golden API tests, not ~20** — each asserts a ranking property end-to-end; add one whenever a ranking bug is found.

**Not verified while planning:** the Docker/Traefik stack (Task 12). Its files follow
`CLAUDE.md` §11 and the Traefik v3 label syntax, but no container was started, so
Task 12 carries an explicit smoke test. Everything in Tasks 1–11 was executed:
174 tests green (90% coverage) against `pgvector/pgvector:pg18`, plus a full ingest
of the real CSV (14,652 rows, 0 rejects, 5.7 s, idempotent on re-run).

## File map

```
backend/
  pyproject.toml · .python-version · alembic.ini
  main.py                      app factory, lifespan, router + handler registration
  enums.py                     every enum (single source of truth)
  errors.py                    AppError hierarchy + exception handlers
  core/config.py               Settings / get_settings()
  core/logging.py              JSON logging + request-id middleware
  core/text.py                 normalize_persian, digit helpers, jalali_year
  core/cache.py                Cache (async Redis wrapper), DATA_VERSION_KEY
  db/ids.py · db/base.py · db/session.py
  db/migrations/env.py · script.py.mako · versions/0001_initial.py
  models/__init__.py · city.py · vehicle_catalog.py · listing.py
  schemas/search.py            VehicleMention, SearchIntent, SearchOverrides, SearchParams, IntentRead, SearchResponse
  schemas/listing.py           ListingCard, PriceBreakdown, ListingDetail
  schemas/facets.py            FacetCount, ModelFacet, Facets
  ranking/types.py             Candidate, VehicleTarget, ResolvedCity, RankingQuery, CriterionScore, RankedListing
  ranking/weights.py           RankingWeights, DEFAULT_WEIGHTS
  ranking/labels.py            Persian near-miss labels
  ranking/closeness.py         one pure function per criterion
  ranking/ranker.py            ListingRanker
  ranking/estimator.py         PriceEstimator
  ingest/normalizers.py        field parsers
  ingest/column_maps.py        per-category columns + value maps
  ingest/row_mapper.py         NormalizedListing, map_row
  ingest/report.py             IngestReport
  ingest/pipeline.py           IngestPipeline
  ingest/__main__.py           CLI
  repositories/city_repository.py · catalog_repository.py · listing_repository.py
  services/intent_chips.py     build_chips
  services/intent_resolver.py  IntentResolver, infer_level, mention_queries
  services/query_parser.py     QueryParser (cache → LLM → rules)
  services/listing_views.py    ORM → schema translation, verdict_of
  services/search_service.py   SearchService
  services/listing_service.py  ListingService (detail, batch, similar)
  services/facet_service.py    FacetService
  llm/model_factory.py · intent_agent.py · rules_parser.py · eval_cases.py · eval.py
  dependencies/providers.py    every Depends provider
  api/health.py · api/v1/router.py · api/v1/endpoints/{search,listings,facets}.py
  tests/                       mirrors the layout; support.py; fixtures/make_fixture.py + listings_sample.csv
.docker/   backend.Dockerfile · frontend.Dockerfile · compose.yml · compose.dev.yml · compose.test.yml · compose.sonar.yml
.scripts/  setup.sh · dev.sh · lint.sh · test-db.sh · ingest.sh · sonar.sh
.github/workflows/  ci.yml · security.yml · docker-publish.yml
example.env · .dockerignore · .pre-commit-config.yaml · sonar-project.properties
```

Every directory under `backend/` that holds Python modules (including every directory
under `backend/tests/`) needs an empty `__init__.py`. Each task lists the ones it adds.

**How to read the tasks:** all `uv run …` commands run from `backend/`. Code blocks are
final and already Black-formatted; copy them verbatim. `git` commands run from the
repo root (each commit step starts with `cd ..`).

---

### Task 1: Project init, enums and Persian text utilities

**Files:**
- Create: `backend/pyproject.toml`, `backend/.python-version`, `backend/enums.py`, `backend/core/__init__.py`, `backend/core/text.py`
- Create: `backend/tests/__init__.py`, `backend/tests/core/__init__.py`, `backend/tests/core/test_text.py`, `backend/tests/test_enums.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `enums.Category | Gearbox | Fuel | BodyCondition | EstimateBasis | SortKey | Verdict | LlmProvider | ParsedBy | MentionLevel | Criterion` (all `StrEnum`); `core.text.normalize_persian(text: str) -> str`; `core.text.to_ascii_digits(text: str) -> str`; `core.text.to_persian_digits(value: int | str) -> str`; `core.text.jalali_year(moment: date) -> int`.

- [ ] **Step 1: Create the uv project**

```bash
mkdir -p backend && cd backend
printf '3.14\n' > .python-version
```

Create `backend/pyproject.toml`:

```toml
[project]
name = "torobcar-backend"
version = "0.1.0"
description = "Torobcar search API"
requires-python = ">=3.14"
dependencies = []

[dependency-groups]
dev = []

[tool.uv]
package = false

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
testpaths = ["tests"]
markers = ["db: needs the Postgres test database (.docker/compose.test.yml)"]

[tool.coverage.run]
omit = ["tests/*", "db/migrations/*"]

[tool.black]
line-length = 88
target-version = ["py314"]

[tool.ruff]
line-length = 88
target-version = "py314"
extend-exclude = ["db/migrations/versions"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "SIM"]
```

Then add dependencies (uv writes the versions and `uv.lock`):

```bash
uv add "fastapi[standard]" "sqlalchemy[asyncio]" asyncpg alembic pydantic-settings redis "pydantic-ai-slim[google,openai]"
uv add --dev pytest pytest-asyncio pytest-cov ruff black
```

Expected: `uv.lock` and `.venv/` created, no resolution errors.

- [ ] **Step 2: Ignore Python artefacts**

Append to the repo-root `.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.coverage
coverage.xml
frontend/coverage/
.scannerwork/
```

- [ ] **Step 3: Write the failing tests**

Create empty `backend/core/__init__.py`, `backend/tests/__init__.py`, `backend/tests/core/__init__.py`.

`backend/tests/core/test_text.py`:

```python
from datetime import date

import pytest

from core.text import (
    jalali_year,
    normalize_persian,
    to_ascii_digits,
    to_persian_digits,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("پژو ۲۰۶ تیپ ۲", "پژو 206 تیپ 2"),
        ("كيا  ريو", "کیا ریو"),  # Arabic kaf/yeh + double space
        ("ام‌وی‌ام X22 Pro", "ام وی ام x22 pro"),  # ZWNJ → space, Latin lowercased
        ("‏۴,۳۰۰,۰۰۰ تومان", "4,300,000 تومان"),  # RLM stripped
        ("٢٠٦", "206"),  # Arabic-Indic digits
        ("  ", ""),
    ],
)
def test_normalize_persian(raw: str, expected: str) -> None:
    assert normalize_persian(raw) == expected


def test_to_ascii_digits_keeps_other_characters() -> None:
    assert to_ascii_digits("مدل ۱۳۹۸") == "مدل 1398"


def test_to_persian_digits_formats_ints_and_strings() -> None:
    assert to_persian_digits(1398) == "۱۳۹۸"
    assert to_persian_digits("1.2") == "۱.۲"


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (date(2026, 9, 18), 1405),
        (date(2026, 3, 21), 1405),  # Nowruz
        (date(2026, 3, 20), 1404),
        (date(2027, 1, 1), 1405),
    ],
)
def test_jalali_year(moment: date, expected: int) -> None:
    assert jalali_year(moment) == expected
```

`backend/tests/test_enums.py`:

```python
from enums import Category, LlmProvider, SortKey


def test_enum_values_are_stable_api_strings() -> None:
    assert Category.MOTORCYCLE.value == "motorcycle"
    assert SortKey.RELEVANCE.value == "relevance"
    assert LlmProvider("openai_compatible") is LlmProvider.OPENAI_COMPATIBLE
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `uv run pytest -q`
Expected: collection errors — `No module named 'core.text'` and `No module named 'enums'`.

- [ ] **Step 5: Implement**

`backend/enums.py`:

```python
"""Shared enums — the single source of truth for every closed vocabulary."""

from enum import StrEnum


class Category(StrEnum):
    LIGHT = "light"
    HEAVY = "heavy"
    MOTORCYCLE = "motorcycle"
    RENTAL = "rental"
    CLASSIC = "classic"


class Gearbox(StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class Fuel(StrEnum):
    PETROL = "petrol"
    DUAL_FACTORY = "dual_factory"
    DUAL_AFTERMARKET = "dual_aftermarket"
    HYBRID = "hybrid"
    PLUGIN_HYBRID = "plugin_hybrid"
    ELECTRIC = "electric"
    DIESEL = "diesel"


class BodyCondition(StrEnum):
    INTACT = "intact"
    NO_PAINT = "no_paint"
    MINOR_SCRATCHES = "minor_scratches"
    PARTIAL_PAINT = "partial_paint"
    HEAVY_PAINT = "heavy_paint"
    DROPPED = "dropped"
    ACCIDENT = "accident"
    ORIGINAL = "original"
    RESTORED = "restored"


class EstimateBasis(StrEnum):
    TRIM_YEAR = "trim_year"
    TRIM_NEAR_YEAR = "trim_near_year"
    MODEL_YEAR = "model_year"
    MODEL_NEAR_YEAR = "model_near_year"
    NONE = "none"


class SortKey(StrEnum):
    RELEVANCE = "relevance"
    DEAL = "deal"
    PRICE = "price"
    KM = "km"
    NEWEST = "newest"


class Verdict(StrEnum):
    CHEAP = "cheap"
    FAIR = "fair"
    EXPENSIVE = "expensive"
    UNKNOWN = "unknown"


class LlmProvider(StrEnum):
    GOOGLE = "google"
    OPENAI_COMPATIBLE = "openai_compatible"


class ParsedBy(StrEnum):
    LLM = "llm"
    RULES = "rules"


class MentionLevel(StrEnum):
    BRAND = "brand"
    MODEL = "model"
    TRIM = "trim"


class Criterion(StrEnum):
    VEHICLE = "vehicle"
    PRICE = "price"
    YEAR = "year"
    CITY = "city"
    KM = "km"
    GEARBOX = "gearbox"
    FUEL = "fuel"
    TEXT = "text"
    COLOR = "color"
```

`backend/core/text.py`:

```python
"""Persian text helpers. `normalize_persian` is the ONLY normaliser: ingest and
query parsing must both go through it, otherwise trigram matching silently degrades."""

from datetime import date

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_ASCII_DIGITS = "0123456789"
_NOWRUZ = (3, 21)
_JALALI_OFFSET_AFTER_NOWRUZ = 621
_JALALI_OFFSET_BEFORE_NOWRUZ = 622

_TO_ASCII_DIGITS = str.maketrans(
    _PERSIAN_DIGITS + _ARABIC_DIGITS, _ASCII_DIGITS + _ASCII_DIGITS
)
_TO_PERSIAN_DIGITS = str.maketrans(_ASCII_DIGITS, _PERSIAN_DIGITS)
_CHARACTER_FIXES = str.maketrans(
    {
        "ي": "ی",  # Arabic yeh
        "ك": "ک",  # Arabic kaf
        "‌": " ",  # ZWNJ → space
        "‏": None,  # right-to-left mark
        "‎": None,  # left-to-right mark
    }
)


def to_ascii_digits(text: str) -> str:
    return text.translate(_TO_ASCII_DIGITS)


def to_persian_digits(value: int | str) -> str:
    return str(value).translate(_TO_PERSIAN_DIGITS)


def normalize_persian(text: str) -> str:
    fixed = to_ascii_digits(text.translate(_CHARACTER_FIXES)).lower()
    return " ".join(fixed.split())


def jalali_year(moment: date) -> int:
    # ponytail: year-only conversion, exact to within Nowruz drifting by a day;
    # pull in a calendar library only if a full Jalali date is ever needed.
    after_nowruz = (moment.month, moment.day) >= _NOWRUZ
    offset = (
        _JALALI_OFFSET_AFTER_NOWRUZ if after_nowruz else _JALALI_OFFSET_BEFORE_NOWRUZ
    )
    return moment.year - offset
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run black --check .`
Expected: `13 passed`, no lint or format findings.

- [ ] **Step 7: Commit**

```bash
cd .. && git add .gitignore backend/pyproject.toml backend/uv.lock backend/.python-version backend/enums.py backend/core backend/tests
git commit -m "feat(backend): init uv project with enums and Persian text utilities

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Settings, logging, errors, app factory and liveness

**Files:**
- Create: `backend/core/config.py`, `backend/core/logging.py`, `backend/errors.py`, `backend/main.py`, `backend/api/__init__.py`, `backend/api/health.py`, `backend/api/v1/__init__.py`, `backend/api/v1/router.py`, `backend/api/v1/endpoints/__init__.py`
- Create: `example.env`
- Test: `backend/tests/conftest.py`, `backend/tests/core/test_config.py`, `backend/tests/test_errors.py`, `backend/tests/api/__init__.py`, `backend/tests/api/test_health.py`

**Interfaces:**
- Consumes: `enums.LlmProvider`.
- Produces: `core.config.Settings`, `core.config.get_settings() -> Settings` (lru-cached); `core.logging.configure_logging(level: str) -> None`, `core.logging.request_id_middleware`; `errors.AppError(message, context=None)` with class attrs `status_code` / `code`, subclasses `ListingNotFoundError(listing_id)`, `InvalidSearchError`, `ServiceUnavailableError`, `IngestError`; `errors.register_exception_handlers(app)`; `main.create_app() -> FastAPI`, `main.app`; `api.v1.router.router`; pytest fixtures `app` and `client`. Structured log fields are passed as `logger.info("event", extra={"fields": {...}})`.

- [ ] **Step 1: Write `example.env`** (repo root)

```dotenv
# Backend
ENV=development
LOG_LEVEL=INFO
DATABASE_URL=postgresql+asyncpg://app:app@db:5432/app
TEST_DATABASE_URL=postgresql+asyncpg://app:app@127.0.0.1:54329/app_test
REDIS_URL=redis://redis:6379/0
SEARCH_CACHE_TTL_SECONDS=600
INTENT_CACHE_TTL_SECONDS=86400

# LLM — development uses the Gemini API; production uses any OpenAI-compatible API
# (set LLM_PROVIDER=openai_compatible, LLM_BASE_URL=https://openrouter.ai/api/v1).
# With LLM_API_KEY empty, search runs on the deterministic rules parser.
LLM_PROVIDER=google
LLM_MODEL=gemini-3.7-flash
LLM_API_KEY=
LLM_BASE_URL=
LLM_TIMEOUT_SECONDS=4

# Frontend — same origin through Traefik
NEXT_PUBLIC_API_URL=/api

# Postgres (consumed by the db service)
POSTGRES_USER=app
POSTGRES_PASSWORD=app
POSTGRES_DB=app

# SonarQube (local developer tool)
SONAR_HOST_URL=http://localhost:9000
SONAR_TOKEN=
```

- [ ] **Step 2: Write the failing tests**

Create empty `backend/api/__init__.py`, `backend/api/v1/__init__.py`, `backend/api/v1/endpoints/__init__.py`, `backend/tests/api/__init__.py`.

`backend/tests/conftest.py` (grows in Tasks 3, 8 and 11):

```python
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic_ai import models

from main import create_app

models.ALLOW_MODEL_REQUESTS = False  # tests must never reach a real LLM


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
```

`backend/tests/core/test_config.py`:

```python
from core.config import Settings
from enums import LlmProvider


def test_settings_defaults_need_no_environment() -> None:
    settings = Settings(_env_file=None)
    assert settings.llm_provider is LlmProvider.GOOGLE
    assert settings.search_cache_ttl_seconds == 600
    assert settings.llm_api_key.get_secret_value() == ""


def test_settings_parse_provider_and_hide_the_key() -> None:
    settings = Settings(
        _env_file=None, llm_provider="openai_compatible", llm_api_key="sk-test"
    )
    assert settings.llm_provider is LlmProvider.OPENAI_COMPATIBLE
    assert "sk-test" not in repr(settings)
```

`backend/tests/test_errors.py`:

```python
import uuid

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from errors import ListingNotFoundError, register_exception_handlers


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

    return app


async def _get(path: str) -> tuple[int, dict]:
    transport = ASGITransport(app=_failing_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        response = await http.get(path)
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
```

`backend/tests/api/test_health.py`:

```python
from httpx import AsyncClient


async def test_liveness(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest -q`
Expected: `ModuleNotFoundError: No module named 'main'` during collection.

- [ ] **Step 4: Implement config, logging and errors**

`backend/core/config.py`:

```python
"""Application settings — the ONLY module allowed to read the environment."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from enums import LlmProvider


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    env: str = "development"
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`backend/core/logging.py`:

```python
"""JSON logging plus a request-id middleware. Pass structured fields with
`logger.info("search", extra={"fields": {...}})`."""

import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from fastapi import Request, Response

REQUEST_ID_HEADER = "X-Request-ID"
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _request_id.get(),
        }
        payload.update(getattr(record, "fields", {}))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
    token = _request_id.set(request_id)
    try:
        response = await call_next(request)
    finally:
        _request_id.reset(token)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response
```

`backend/errors.py`:

```python
"""Domain exceptions and the handlers that turn them into one JSON envelope:
{"error": {"code": ..., "message": ..., "details": ...}}"""

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}


class ListingNotFoundError(AppError):
    status_code = 404
    code = "listing_not_found"

    def __init__(self, listing_id: uuid.UUID) -> None:
        super().__init__("Listing not found", {"listing_id": str(listing_id)})


class InvalidSearchError(AppError):
    status_code = 422
    code = "invalid_search"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"


class IngestError(AppError):
    code = "ingest_failed"


def _envelope(status_code: int, code: str, message: str, details: Any) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details}}
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


async def _handle_app_error(_: Request, error: AppError) -> JSONResponse:
    return _envelope(error.status_code, error.code, error.message, error.context)


async def _handle_validation_error(
    _: Request, error: RequestValidationError
) -> JSONResponse:
    return _envelope(422, "validation_error", "Invalid request", error.errors())


async def _handle_http_error(_: Request, error: StarletteHTTPException) -> JSONResponse:
    return _envelope(error.status_code, "http_error", str(error.detail), {})


async def _handle_database_down(_: Request, error: OperationalError) -> JSONResponse:
    logger.error("database unavailable", exc_info=error)
    unavailable = ServiceUnavailableError("Database unavailable")
    return _envelope(unavailable.status_code, unavailable.code, unavailable.message, {})


async def _handle_unexpected(_: Request, error: Exception) -> JSONResponse:
    logger.error("unhandled exception", exc_info=error)
    return _envelope(500, AppError.code, "Internal server error", {})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(OperationalError, _handle_database_down)
    app.add_exception_handler(Exception, _handle_unexpected)
```

- [ ] **Step 5: Implement the first version of health, router and app**

These three files are replaced by their final versions in Task 11.

`backend/api/health.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def read_liveness() -> dict[str, str]:
    return {"status": "ok"}
```

`backend/api/v1/router.py`:

```python
"""Aggregates every v1 endpoint router. Endpoint routers are included in Task 11."""

from fastapi import APIRouter

router = APIRouter()
```

`backend/main.py`:

```python
from fastapi import FastAPI

from api.health import router as health_router
from api.v1.router import router as v1_router
from core.config import get_settings
from core.logging import configure_logging, request_id_middleware
from errors import register_exception_handlers

API_V1_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    configure_logging(get_settings().log_level)
    app = FastAPI(title="Torobcar API")
    app.middleware("http")(request_id_middleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(v1_router, prefix=API_V1_PREFIX)
    return app


app = create_app()
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run black --check .`
Expected: `20 passed`.

- [ ] **Step 7: Commit**

```bash
cd .. && git add example.env backend/core backend/errors.py backend/main.py backend/api backend/tests
git commit -m "feat(backend): add settings, JSON logging, error envelope and liveness

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Database foundation — test database, models, Alembic

**Files:**
- Create: `.docker/compose.test.yml`, `.scripts/test-db.sh`
- Create: `backend/db/__init__.py`, `backend/db/ids.py`, `backend/db/base.py`, `backend/db/session.py`, `backend/models/__init__.py`, `backend/models/city.py`, `backend/models/vehicle_catalog.py`, `backend/models/listing.py`
- Create: `backend/alembic.ini`, `backend/db/migrations/env.py`, `backend/db/migrations/script.py.mako`, `backend/db/migrations/versions/0001_initial.py` (autogenerated, then one line added)
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/db/__init__.py`, `backend/tests/db/test_schema.py`

**Interfaces:**
- Consumes: `core.config.get_settings`, enums.
- Produces: `db.ids.new_uuid8() -> uuid.UUID`; `db.base.Base`, `db.base.UUIDPrimaryKeyMixin`, `db.base.enum_type(enum_class) -> sqlalchemy.Enum` (VARCHAR-backed); `db.session.get_engine()`, `get_session_factory()`, `get_session()` (FastAPI dependency, commits on success); ORM models `City`, `VehicleCatalog`, `Listing` (relationships `Listing.city` / `Listing.catalog` are `lazy="raise"`); pytest fixtures `migrated_database_url` (session scope, runs Alembic) and `session` (function scope, always rolled back).

- [ ] **Step 1: Add the throwaway test database**

`.docker/compose.test.yml`:

```yaml
# Developer tool, NOT part of the application stack: a throwaway Postgres for pytest.
# Loopback-only port and tmpfs data — a documented exception to the "only Traefik
# publishes a port" rule, because the app's `db` service is unreachable from the host.
name: torobcar-test
services:
  test-db:
    image: pgvector/pgvector:pg18
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app_test
    ports: ["127.0.0.1:54329:5432"]
    tmpfs: ["/var/lib/postgresql"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d app_test"]
      interval: 2s
      timeout: 3s
      retries: 20
```

`.scripts/test-db.sh` (then `chmod +x .scripts/test-db.sh`):

```bash
#!/usr/bin/env bash
# Start (or stop with `down`) the throwaway Postgres used by `uv run pytest`.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-up}" == "down" ]]; then
  docker compose -f .docker/compose.test.yml down -v
else
  docker compose -f .docker/compose.test.yml up -d --wait
fi
```

Run: `./.scripts/test-db.sh`
Expected: the `torobcar-test-test-db-1` container is healthy.

- [ ] **Step 2: Write the failing tests**

Create empty `backend/db/__init__.py`, `backend/tests/db/__init__.py`.

Add to `backend/tests/conftest.py` — these imports at the top:

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import get_settings
```

and, below `models.ALLOW_MODEL_REQUESTS = False`:

```python
BACKEND_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def migrated_database_url() -> str:
    """Runs the real Alembic migrations once against the throwaway test database
    (start it with `./.scripts/test-db.sh`)."""
    url = get_settings().test_database_url
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "db" / "migrations"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    return url


@pytest.fixture
async def session(migrated_database_url: str) -> AsyncIterator[AsyncSession]:
    """A session inside one outer transaction that is always rolled back."""
    engine = create_async_engine(migrated_database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        ) as db_session:
            yield db_session
        await transaction.rollback()
    await engine.dispose()
```

`migrated_database_url` is a **sync** fixture on purpose: `db/migrations/env.py` calls
`asyncio.run`, which cannot run inside pytest-asyncio's event loop.

`backend/tests/db/test_schema.py`:

```python
import time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.ids import new_uuid8
from models.city import City

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


def test_new_uuid8_is_version_8_and_time_ordered() -> None:
    first = new_uuid8()
    time.sleep(0.002)
    second = new_uuid8()
    assert first.version == second.version == 8
    assert first < second


@pytest.mark.db
async def test_migration_installs_pg_trgm_and_the_trigram_indexes(
    session: AsyncSession,
) -> None:
    extensions = await session.scalars(text("SELECT extname FROM pg_extension"))
    assert "pg_trgm" in set(extensions)
    indexes = await session.scalars(
        text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
    )
    assert {"ix_listings_title_trgm", "ix_vehicle_catalog_trim_trgm"} <= set(indexes)


@pytest.mark.db
def test_models_and_migrations_do_not_drift(migrated_database_url: str) -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "db" / "migrations"))
    config.attributes["database_url"] = migrated_database_url
    command.check(config)  # raises if autogenerate would produce a new migration


@pytest.mark.db
async def test_primary_keys_are_generated_app_side(session: AsyncSession) -> None:
    city = City(name="شهر آزمایشی", name_normalized="شهر آزمایشی")
    session.add(city)
    await session.flush()
    assert city.id.version == 8
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/db -q`
Expected: `ModuleNotFoundError: No module named 'db.ids'`.

- [ ] **Step 4: Implement ids, base, session and models**

`backend/db/ids.py`:

```python
import time
import uuid

_TIMESTAMP_MASK = 0xFFFFFFFFFFFF
_NANOSECONDS_PER_MILLISECOND = 1_000_000


def new_uuid8() -> uuid.UUID:
    """Time-ordered UUIDv8: a 48-bit millisecond timestamp in the leading field,
    pseudo-random in the rest. Keeps index locality while staying inside the
    application-defined v8 space."""
    timestamp_ms = (time.time_ns() // _NANOSECONDS_PER_MILLISECOND) & _TIMESTAMP_MASK
    return uuid.uuid8(a=timestamp_ms)
```

`backend/db/base.py`:

```python
import uuid
from enum import StrEnum

from sqlalchemy import Enum, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from db.ids import new_uuid8

ENUM_COLUMN_LENGTH = 32


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),  # native `uuid` column on Postgres
        primary_key=True,
        default=new_uuid8,  # generated app-side, never server_default
    )


def enum_type(enum_class: type[StrEnum]) -> Enum:
    """VARCHAR-backed enum that stores `.value`. Not a native Postgres enum, so
    adding a member never needs a migration."""
    return Enum(
        enum_class,
        native_enum=False,
        length=ENUM_COLUMN_LENGTH,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )
```

`backend/db/session.py`:

```python
from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """One session per request; commit at the boundary, never in repositories."""
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

`backend/models/city.py`:

```python
from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, UUIDPrimaryKeyMixin


class City(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "cities"

    name: Mapped[str] = mapped_column(String(128), unique=True)
    name_normalized: Mapped[str] = mapped_column(String(128), index=True)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    listing_count: Mapped[int] = mapped_column(Integer, default=0)
```

`backend/models/vehicle_catalog.py`:

```python
from sqlalchemy import Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, UUIDPrimaryKeyMixin, enum_type
from enums import Category


class VehicleCatalog(UUIDPrimaryKeyMixin, Base):
    """One row per distinct Divar «برند و مدل» string. `trim` is the raw string;
    `brand` and `model` are normalised (see ingest.normalizers.split_brand_model)."""

    __tablename__ = "vehicle_catalog"
    __table_args__ = (
        UniqueConstraint("category", "trim", name="uq_vehicle_catalog_category_trim"),
        Index(
            "ix_vehicle_catalog_trim_trgm",
            "trim_normalized",
            postgresql_using="gin",
            postgresql_ops={"trim_normalized": "gin_trgm_ops"},
        ),
    )

    category: Mapped[Category] = mapped_column(enum_type(Category))
    brand: Mapped[str] = mapped_column(String(128), index=True)
    model: Mapped[str] = mapped_column(String(192))
    trim: Mapped[str] = mapped_column(String(255))
    trim_normalized: Mapped[str] = mapped_column(String(255))
    listing_count: Mapped[int] = mapped_column(Integer, default=0)
```

`backend/models/listing.py`:

```python
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, UUIDPrimaryKeyMixin, enum_type
from enums import BodyCondition, Category, EstimateBasis, Fuel, Gearbox
from models.city import City
from models.vehicle_catalog import VehicleCatalog


class Listing(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "listings"
    __table_args__ = (
        Index("ix_listings_category_catalog", "category", "catalog_id"),
        Index(
            "ix_listings_title_trgm",
            "title_normalized",
            postgresql_using="gin",
            postgresql_ops={"title_normalized": "gin_trgm_ops"},
        ),
    )

    token: Mapped[str] = mapped_column(String(64), unique=True)
    url: Mapped[str] = mapped_column(Text)
    category: Mapped[Category] = mapped_column(enum_type(Category))
    catalog_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vehicle_catalog.id")
    )
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id"), index=True)

    title: Mapped[str] = mapped_column(Text)
    title_normalized: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)

    year: Mapped[int | None] = mapped_column(Integer)
    km: Mapped[int | None] = mapped_column(Integer)
    price: Mapped[int | None] = mapped_column(BigInteger)  # toman
    gearbox: Mapped[Gearbox | None] = mapped_column(enum_type(Gearbox))
    fuel: Mapped[Fuel | None] = mapped_column(enum_type(Fuel))
    color: Mapped[str | None] = mapped_column(String(64))
    body_condition: Mapped[BodyCondition | None] = mapped_column(
        enum_type(BodyCondition)
    )
    insurance_months: Mapped[int | None] = mapped_column(Integer)
    vehicle_type: Mapped[str | None] = mapped_column(String(64))
    is_dealer: Mapped[bool] = mapped_column(Boolean, default=False)

    district: Mapped[str | None] = mapped_column(String(128))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    image_urls: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    thumbnail_urls: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    est_price: Mapped[int | None] = mapped_column(BigInteger)
    est_basis: Mapped[EstimateBasis] = mapped_column(
        enum_type(EstimateBasis), default=EstimateBasis.NONE
    )
    est_sample_size: Mapped[int] = mapped_column(Integer, default=0)
    km_factor: Mapped[float] = mapped_column(Float, default=1.0)
    insurance_factor: Mapped[float] = mapped_column(Float, default=1.0)
    diff_pct: Mapped[float | None] = mapped_column(Float)
    deal_score: Mapped[int | None] = mapped_column(Integer)
    price_suspect: Mapped[bool] = mapped_column(Boolean, default=False)

    # lazy="raise": async sessions cannot lazy-load; repositories must join explicitly.
    city: Mapped[City] = relationship(lazy="raise")
    catalog: Mapped[VehicleCatalog | None] = relationship(lazy="raise")
```

`backend/models/__init__.py`:

```python
"""Import every model so `Base.metadata` is complete for Alembic."""

from models.city import City
from models.listing import Listing
from models.vehicle_catalog import VehicleCatalog

__all__ = ["City", "Listing", "VehicleCatalog"]
```

- [ ] **Step 5: Configure Alembic**

`backend/alembic.ini`:

```ini
[alembic]
script_location = db/migrations
prepend_sys_path = .
path_separator = os
file_template = %%(rev)s_%%(slug)s

[loggers]
keys = root

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console

[handler_console]
class = StreamHandler
args = (sys.stderr,)
formatter = generic

[formatter_generic]
format = %(levelname)s [%(name)s] %(message)s
```

`backend/db/migrations/env.py`:

```python
"""Alembic environment (async). The database URL comes from Settings, or from
`config.attributes["database_url"]` when the test suite migrates the test database."""

import asyncio

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import models  # noqa: F401  (registers every table on Base.metadata)
from core.config import get_settings
from db.base import Base

target_metadata = Base.metadata


def _database_url() -> str:
    return context.config.attributes.get("database_url") or get_settings().database_url


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    engine = create_async_engine(_database_url(), poolclass=NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)
    await engine.dispose()


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(), target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(_run_async_migrations())
```

`backend/db/migrations/script.py.mako`:

```text
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Create the empty directory `backend/db/migrations/versions/`.

- [ ] **Step 6: Autogenerate the initial migration, then add the extension**

```bash
DATABASE_URL=postgresql+asyncpg://app:app@127.0.0.1:54329/app_test \
  uv run alembic revision --autogenerate -m "initial" --rev-id 0001
```

Expected: `db/migrations/versions/0001_initial.py` creating `cities`, `vehicle_catalog`,
`listings` and the indexes `ix_listings_title_trgm`, `ix_vehicle_catalog_trim_trgm`,
`ix_listings_category_catalog`.

The GIN trigram indexes need the `pg_trgm` extension, which autogenerate does not emit.
In `0001_initial.py`, make this the **first line of `upgrade()`**:

```python
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")  # needed by the GIN trigram indexes
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run black --check .`
Expected: `24 passed`. `test_models_and_migrations_do_not_drift` proves the migration matches the models.

- [ ] **Step 8: Commit**

```bash
cd .. && git add .docker/compose.test.yml .scripts/test-db.sh backend/alembic.ini backend/db backend/models backend/tests
git commit -m "feat(backend): add UUIDv8 models, async session and initial migration

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Ingest normalizers

**Files:**
- Create: `backend/ingest/__init__.py`, `backend/ingest/normalizers.py`
- Test: `backend/tests/ingest/__init__.py`, `backend/tests/ingest/test_normalizers.py`

**Interfaces:**
- Consumes: `core.text.normalize_persian`, `core.text.to_ascii_digits`.
- Produces (all pure): `parse_digits(raw) -> int | None`; `parse_price(raw) -> int | None` (None below `MIN_PLAUSIBLE_PRICE_TOMAN = 10_000_000`); `parse_km(raw) -> int | None` (None at or above `MAX_PLAUSIBLE_KM = 1_000_000`); `parse_year(raw) -> int | None`; `parse_insurance_months(raw) -> int | None`; `parse_posted_at(posted_raw, fetched_at) -> datetime | None`; `parse_district(posted_raw) -> str | None`; `parse_fetched_at(raw) -> datetime`; `parse_coordinate(raw) -> float | None`; `split_urls(raw) -> list[str]`; `split_brand_model(trim) -> BrandModel(brand, model)`; `is_catch_all_trim(trim) -> bool`.

Verified against all 14,652 real rows: 0 unparseable years, posted dates or insurance
values; 1,685 prices and 221 mileages nulled by rule.

- [ ] **Step 1: Write the failing tests**

Create empty `backend/ingest/__init__.py`, `backend/tests/ingest/__init__.py`.

`backend/tests/ingest/test_normalizers.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest

from ingest import normalizers
from ingest.normalizers import BrandModel

FETCHED_AT = datetime(2026, 9, 17, 20, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("‏۴,۳۰۰,۰۰۰,۰۰۰ تومان", 4_300_000_000),
        ("‏۱۰,۰۰۰,۰۰۰ تومان", 10_000_000),
        ("‏۵,۵۰۰,۰۰۰ تومان", None),  # placeholder below the plausible floor
        ("‏۱,۰۰۰ تومان", None),
        ("", None),
    ],
)
def test_parse_price(raw: str, expected: int | None) -> None:
    assert normalizers.parse_price(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("۶۲۰۰۰", 62_000), ("۰", 0), ("۱۰۰۰۰۰۰", None), ("", None)],
)
def test_parse_km_keeps_zero_and_drops_the_capped_value(
    raw: str, expected: int | None
) -> None:
    assert normalizers.parse_km(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("۱۴۰۱ - ۲۰۲۲", 1401),
        ("۱۳۹۵", 1395),
        ("قبل از ۱۳۶۶ - قبل از ۱۹۸۷", 1365),
        ("قبل از ۱۳۷۰", 1369),
        ("1,402", 1402),
        ("2010", 1389),  # Gregorian year converted
        ("", None),
        ("نامشخص", None),
    ],
)
def test_parse_year(raw: str, expected: int | None) -> None:
    assert normalizers.parse_year(raw) == expected


def test_parse_insurance_months() -> None:
    assert normalizers.parse_insurance_months("۱۲ ماه") == 12
    assert normalizers.parse_insurance_months("") is None
    assert normalizers.parse_insurance_months("۴۰ ماه") is None


@pytest.mark.parametrize(
    ("phrase", "hours"),
    [
        ("نیم ساعت پیش", 0.5),
        ("۳ ساعت پیش", 3),
        ("دیروز", 24),
        ("پریروز", 48),
        ("۴ روز پیش", 96),
        ("هفته پیش", 168),
        ("۲ هفته پیش", 336),
        ("ماه پیش", 720),
        ("۲ ماه پیش", 1440),
        ("سال پیش", 8760),
    ],
)
def test_parse_posted_at(phrase: str, hours: float) -> None:
    posted_at = normalizers.parse_posted_at(f"{phrase} در کرج، اسدآباد", FETCHED_AT)
    assert posted_at == FETCHED_AT - timedelta(hours=hours)


def test_parse_posted_at_returns_none_for_an_unknown_phrase() -> None:
    assert normalizers.parse_posted_at("لحظاتی پیش در تهران", FETCHED_AT) is None


@pytest.mark.parametrize(
    ("posted_raw", "district"),
    [
        ("۴ روز پیش در کرج، اسدآباد، خ مهر یکم", "اسدآباد"),
        ("دیروز در تهران، شهرک شریعتی", "شهرک شریعتی"),
        ("دیروز در تهران", None),
        ("", None),
    ],
)
def test_parse_district(posted_raw: str, district: str | None) -> None:
    assert normalizers.parse_district(posted_raw) == district


@pytest.mark.parametrize(
    ("trim", "expected"),
    [
        ("پژو 206 تیپ ۲", BrandModel("پژو", "پژو 206")),
        ("پراید 131 SE", BrandModel("پراید", "پراید 131")),
        ("ام‌وی‌ام X22 Pro IE", BrandModel("ام وی ام", "ام وی ام x22")),
        ("اس وای ام Galaxy NA 180", BrandModel("اس وای ام", "اس وای ام galaxy")),
        ("ایران خودرو ری را", BrandModel("ایران خودرو", "ایران خودرو ری")),
        ("سایر", BrandModel("سایر", "سایر")),
    ],
)
def test_split_brand_model(trim: str, expected: BrandModel) -> None:
    assert normalizers.split_brand_model(trim) == expected


def test_split_urls() -> None:
    assert normalizers.split_urls("https://a/1.webp | https://a/2.webp") == [
        "https://a/1.webp",
        "https://a/2.webp",
    ]
    assert normalizers.split_urls("") == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/ingest -q`
Expected: `ModuleNotFoundError: No module named 'ingest.normalizers'`.

- [ ] **Step 3: Implement**

`backend/ingest/normalizers.py`:

```python
"""Field parsers for raw Divar CSV values. Pure functions, no I/O."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.text import normalize_persian, to_ascii_digits

MIN_PLAUSIBLE_PRICE_TOMAN = 10_000_000
MAX_PLAUSIBLE_KM = 1_000_000
MIN_JALALI_YEAR = 1300
MAX_JALALI_YEAR = 1420
GREGORIAN_TO_JALALI_OFFSET = 621
MAX_INSURANCE_MONTHS = 12
URL_SEPARATOR = "|"
LOCATION_MARKER = " در "
LOCATION_SEPARATOR = "،"
BEFORE_YEAR_MARKER = "قبل از"
CATCH_ALL_MARKER = "سایر"

_FIXED_AGE_HOURS = {"نیم ساعت پیش": 0.5, "دیروز": 24.0, "پریروز": 48.0}
_UNIT_HOURS = {"ساعت": 1, "روز": 24, "هفته": 168, "ماه": 720, "سال": 8760}
_RELATIVE_AGE = re.compile(r"(?:(\d+) )?(ساعت|روز|هفته|ماه|سال) پیش")
_FOUR_DIGITS = re.compile(r"\d{4}")

# Brands written with spaces in Divar's «برند و مدل» strings (normalised form).
MULTI_TOKEN_BRANDS: tuple[str, ...] = (
    "اس وای ام", "ایران دوچرخ", "ایران خودرو", "کی تی ام", "کی ام سی", "کی وی",
    "جی ای سی", "جی پی ایکس", "جی سی موتور", "ام وی ام", "ام تک", "بی ای سی",
    "بی وای دی", "بی اس آ", "بی ام و", "ان اس یو", "ان ام بی", "تی وی اس", "به پر",
    "تک تاز", "گس گس", "سی اف موتو", "3 چرخ", "4 چرخ",
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class BrandModel:
    brand: str
    model: str


def parse_digits(raw: str) -> int | None:
    digits = re.sub(r"\D", "", to_ascii_digits(raw))
    return int(digits) if digits else None


def parse_price(raw: str) -> int | None:
    price = parse_digits(raw)
    if price is None or price < MIN_PLAUSIBLE_PRICE_TOMAN:
        return None
    return price


def parse_km(raw: str) -> int | None:
    km = parse_digits(raw)
    if km is None or km >= MAX_PLAUSIBLE_KM:
        return None
    return km


def parse_year(raw: str) -> int | None:
    text = to_ascii_digits(raw).replace(",", "")
    found = _FOUR_DIGITS.search(text)
    if found is None:
        return None
    year = int(found.group())
    if year > MAX_JALALI_YEAR:
        year -= GREGORIAN_TO_JALALI_OFFSET
    if BEFORE_YEAR_MARKER in text:
        year -= 1
    return year if MIN_JALALI_YEAR <= year <= MAX_JALALI_YEAR else None


def parse_insurance_months(raw: str) -> int | None:
    months = parse_digits(raw)
    if months is None or months > MAX_INSURANCE_MONTHS:
        return None
    return months


def parse_posted_at(posted_raw: str, fetched_at: datetime) -> datetime | None:
    phrase = normalize_persian(posted_raw.split(LOCATION_MARKER, 1)[0])
    hours = _FIXED_AGE_HOURS.get(phrase)
    if hours is None:
        matched = _RELATIVE_AGE.fullmatch(phrase)
        if matched is None:
            return None
        hours = float(int(matched.group(1) or 1) * _UNIT_HOURS[matched.group(2)])
    return fetched_at - timedelta(hours=hours)


def parse_district(posted_raw: str) -> str | None:
    _, marker, location = posted_raw.partition(LOCATION_MARKER)
    parts = [part.strip() for part in location.split(LOCATION_SEPARATOR)]
    return parts[1] if marker and len(parts) > 1 and parts[1] else None


def parse_fetched_at(raw: str) -> datetime:
    return datetime.fromtimestamp(int(raw), tz=UTC)


def parse_coordinate(raw: str) -> float | None:
    return float(raw) if raw.strip() else None


def split_urls(raw: str) -> list[str]:
    return [url.strip() for url in raw.split(URL_SEPARATOR) if url.strip()]


def split_brand_model(trim: str) -> BrandModel:
    """`پژو 206 تیپ ۲` → brand `پژو`, model `پژو 206` (both normalised).
    ponytail: token heuristic; irregular families mis-group. Upgrade path is the
    one-time LLM normalisation of the ~1,262 catalog strings in Spec 2."""
    normalized = normalize_persian(trim)
    for brand in MULTI_TOKEN_BRANDS:
        if normalized == brand or normalized.startswith(brand + " "):
            rest = normalized[len(brand) :].split()
            return BrandModel(brand, f"{brand} {rest[0]}" if rest else brand)
    first, *others = trim.split(" ")
    brand = normalize_persian(first)
    second = normalize_persian(others[0]) if others else ""
    return BrandModel(brand, f"{brand} {second}" if second else brand)


def is_catch_all_trim(trim: str) -> bool:
    return CATCH_ALL_MARKER in trim
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run black --check .`
Expected: `64 passed`.

- [ ] **Step 5: Commit**

```bash
cd .. && git add backend/ingest backend/tests/ingest
git commit -m "feat(ingest): add Divar CSV field normalizers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Column maps and row mapper

**Files:**
- Create: `backend/ingest/column_maps.py`, `backend/ingest/row_mapper.py`
- Test: `backend/tests/ingest/test_row_mapper.py`

**Interfaces:**
- Consumes: `ingest.normalizers`, enums, `errors.IngestError`.
- Produces: `column_maps.detect_category(row) -> Category | None`; `column_maps.COLUMN_MAPS: Mapping[Category, ColumnMap(price, year)]`; `column_maps.lookup_value(raw, vocabulary, column)` (raises `UnknownValueError`, an `IngestError`, on an unknown closed-vocabulary value — this aborts the whole run); `row_mapper.NormalizedListing` (Pydantic); `row_mapper.map_row(row: Mapping[str, str]) -> MappedRow(listing, nulled: tuple[str, ...])`; `row_mapper.RowRejectedError(reason)` (per-row, collected in the report); constants `NULLED_PRICE`, `NULLED_KM`, `NULLED_YEAR`, `NULLED_POSTED_AT`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/ingest/test_row_mapper.py`:

```python
import pytest

from enums import BodyCondition, Category, Fuel, Gearbox
from ingest.column_maps import UnknownValueError
from ingest.row_mapper import NULLED_KM, NULLED_PRICE, RowRejectedError, map_row

BASE_ROW = {
    "token": "tok001",
    "url": "https://divar.ir/v/-/tok001",
    "title": "پژو ۲۰۶ تیپ ۲ مدل ۹۸",
    "description": "متن آگهی",
    "city": "تهران",
    "posted_raw": "۳ ساعت پیش در تهران، پونک",
    "latitude": "35.76",
    "longitude": "51.33",
    "image_urls": "https://a/1.webp | https://a/2.webp",
    "thumbnail_urls": "https://a/t1.webp",
    "fetched_at": "1789660000",
    "webengage_cat_2": "cars",
    "webengage_cat_3": "light",
    "webengage_business_type": "personal",
    "برند و مدل": "پژو 206 تیپ ۲",
    "قیمت پایه": "‏۷۸۰,۰۰۰,۰۰۰ تومان",
    "مدل (سال تولید)": "۱۳۹۸ - ۲۰۱۹",
    "کارکرد": "۶۲۰۰۰",
    "گیربکس": "دنده‌ای",
    "نوع سوخت": "بنزین",
    "رنگ": "سفید",
    "مهلت بیمهٔ شخص ثالث": "۸ ماه",
    "مالکیت خودرو": "شخصی",
}


def row(**overrides: str) -> dict[str, str]:
    return {**BASE_ROW, **overrides}


def test_maps_a_passenger_car() -> None:
    mapped = map_row(BASE_ROW)
    listing = mapped.listing
    assert mapped.nulled == ()
    assert (listing.category, listing.brand, listing.model) == (
        Category.LIGHT,
        "پژو",
        "پژو 206",
    )
    assert (listing.price, listing.year, listing.km) == (780_000_000, 1398, 62_000)
    assert (listing.gearbox, listing.fuel) == (Gearbox.MANUAL, Fuel.PETROL)
    assert listing.title_normalized == "پژو 206 تیپ 2 مدل 98"
    assert listing.district == "پونک"
    assert listing.insurance_months == 8
    assert listing.is_dealer is False
    assert listing.image_urls == ["https://a/1.webp", "https://a/2.webp"]
    assert listing.attributes == {"مالکیت خودرو": "شخصی"}


def test_heavy_vehicle_reads_its_own_columns_and_has_no_catalog_entry() -> None:
    heavy = row(
        **{
            "webengage_cat_3": "heavy",
            "برند و مدل": "",
            "قیمت پایه": "",
            "قیمت": "‏۱,۷۰۰,۰۰۰,۰۰۰ تومان",
            "مدل (سال تولید)": "",
            "سال ساخت": "۱۳۸۸",
            "نوع وسیلهٔ نقلیه": "کامیون یا کامیونت",
            "وضعیت بدنه": "کاملا سالم",
        }
    )
    listing = map_row(heavy).listing
    assert listing.category is Category.HEAVY
    assert (listing.trim, listing.brand, listing.model) == (None, None, None)
    assert (listing.price, listing.year) == (1_700_000_000, 1388)
    assert listing.vehicle_type == "کامیون یا کامیونت"
    assert listing.body_condition is BodyCondition.INTACT


def test_motorcycle_is_detected_from_level_two() -> None:
    bike = row(webengage_cat_3="", webengage_cat_2="motorcycles")
    assert map_row(bike).listing.category is Category.MOTORCYCLE


def test_rental_keeps_the_rent_amount_out_of_price() -> None:
    rental = row(webengage_cat_3="rental", price_raw="‏۱۵,۰۰۰,۰۰۰ تومان")
    listing = map_row(rental).listing
    assert listing.price is None
    assert listing.attributes["price_raw"] == "‏۱۵,۰۰۰,۰۰۰ تومان"


def test_placeholder_price_and_capped_km_are_nulled_and_reported() -> None:
    mapped = map_row(row(**{"قیمت پایه": "‏۱,۰۰۰ تومان", "کارکرد": "۱۰۰۰۰۰۰"}))
    assert mapped.listing.price is None and mapped.listing.km is None
    assert set(mapped.nulled) == {NULLED_PRICE, NULLED_KM}


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"token": ""}, "missing_token"),
        ({"title": " "}, "missing_title"),
        ({"city": ""}, "missing_city"),
        ({"webengage_cat_3": "", "webengage_cat_2": "boats"}, "unknown_category"),
    ],
)
def test_unusable_rows_are_rejected(overrides: dict[str, str], reason: str) -> None:
    with pytest.raises(RowRejectedError) as rejected:
        map_row(row(**overrides))
    assert rejected.value.reason == reason


def test_unknown_vocabulary_value_aborts_loudly() -> None:
    with pytest.raises(UnknownValueError) as error:
        map_row(row(**{"نوع سوخت": "هیدروژن"}))
    assert error.value.context == {"column": "نوع سوخت", "value": "هیدروژن"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/ingest/test_row_mapper.py -q`
Expected: `ModuleNotFoundError: No module named 'ingest.column_maps'`.

- [ ] **Step 3: Implement**

`backend/ingest/column_maps.py`:

```python
"""Which CSV column means what, per vehicle category, plus closed value vocabularies.
Vocabulary keys are in `normalize_persian` form (ZWNJ → space)."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from core.text import normalize_persian
from enums import BodyCondition, Category, Fuel, Gearbox
from errors import IngestError

CATEGORY_LEVEL_3 = "webengage_cat_3"
CATEGORY_LEVEL_2 = "webengage_cat_2"
MOTORCYCLES_LEVEL_2 = "motorcycles"
TRIM_COLUMN = "برند و مدل"
KM_COLUMN = "کارکرد"
COLOR_COLUMN = "رنگ"
FUEL_COLUMN = "نوع سوخت"
BODY_COLUMN = "وضعیت بدنه"
INSURANCE_COLUMN = "مهلت بیمهٔ شخص ثالث"
VEHICLE_TYPE_COLUMN = "نوع وسیلهٔ نقلیه"
GEARBOX_COLUMNS = ("گیربکس", "نوع گیربکس")
BUSINESS_TYPE_COLUMN = "webengage_business_type"
PERSONAL_BUSINESS_TYPE = "personal"
RENT_PRICE_COLUMN = "price_raw"

ATTRIBUTE_COLUMNS: tuple[str, ...] = (
    "حجم موتور", "نوع استارت", "نوع کلاچ", "مالکیت خودرو", "مایل به معاوضه",
    "وضعیت سند و مدارک", "وضعیت فنی موتور", "وضعیت فنی موتور و گیربکس",
    "وضعیت لاستیک‌ها", "معاینه فنی", "فروش قسطی", "امکان خرید قسطی",
    "تخفیف بیمهٔ ثالث", "حواله", "مبلغ اجاره", "مبلغ ضمانت",
    "محدودیت کیلومتر (روزانه)", "نوع اجاره", "میزان فابریک بودن قطعات",
    "وضعیت بیمه", "بیمه شخص ثالث", "بیمهٔ شخص ثالث",
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class ColumnMap:
    price: str | None
    year: str


COLUMN_MAPS: Mapping[Category, ColumnMap] = {
    Category.LIGHT: ColumnMap(price="قیمت پایه", year="مدل (سال تولید)"),
    Category.HEAVY: ColumnMap(price="قیمت", year="سال ساخت"),
    Category.MOTORCYCLE: ColumnMap(price="قیمت", year="مدل (سال تولید)"),
    Category.RENTAL: ColumnMap(price=None, year="سال ساخت خودرو"),
    Category.CLASSIC: ColumnMap(price="قیمت", year="مدل (سال ساخت)"),
}

_CATEGORY_BY_LEVEL_3: Mapping[str, Category] = {
    "light": Category.LIGHT,
    "heavy": Category.HEAVY,
    "rental": Category.RENTAL,
    "classic": Category.CLASSIC,
}

GEARBOX_VALUES: Mapping[str, Gearbox] = {
    "دنده ای": Gearbox.MANUAL,
    "اتوماتیک": Gearbox.AUTOMATIC,
}
FUEL_VALUES: Mapping[str, Fuel] = {
    "بنزین": Fuel.PETROL,
    "دوگانه سوز شرکتی": Fuel.DUAL_FACTORY,
    "دوگانه سوز دستی": Fuel.DUAL_AFTERMARKET,
    "هیبرید": Fuel.HYBRID,
    "پلاگین هیبرید": Fuel.PLUGIN_HYBRID,
    "برق": Fuel.ELECTRIC,
    "گازوئیل": Fuel.DIESEL,
}
BODY_VALUES: Mapping[str, BodyCondition] = {
    "کاملا سالم": BodyCondition.INTACT,
    "بدون رنگ": BodyCondition.NO_PAINT,
    "خط و خش جزئی": BodyCondition.MINOR_SCRATCHES,
    "رنگ شدگی جزئی": BodyCondition.PARTIAL_PAINT,
    "رنگ شدگی زیاد": BodyCondition.HEAVY_PAINT,
    "زمین خوردگی": BodyCondition.DROPPED,
    "تصادفی": BodyCondition.ACCIDENT,
    "فابریک": BodyCondition.ORIGINAL,
    "بازسازی شده کامل": BodyCondition.RESTORED,
}


class UnknownValueError(IngestError):
    """A closed-vocabulary column held a value we have no enum for. Aborts the run:
    silently dropping it would hide a schema change in the source data."""

    def __init__(self, column: str, value: str) -> None:
        super().__init__(
            f"Unknown value in column {column!r}", {"column": column, "value": value}
        )


def detect_category(row: Mapping[str, str]) -> Category | None:
    category = _CATEGORY_BY_LEVEL_3.get(row.get(CATEGORY_LEVEL_3, ""))
    if category is None and row.get(CATEGORY_LEVEL_2) == MOTORCYCLES_LEVEL_2:
        return Category.MOTORCYCLE
    return category


def lookup_value[EnumT: StrEnum](
    raw: str, vocabulary: Mapping[str, EnumT], column: str
) -> EnumT | None:
    key = normalize_persian(raw)
    if not key:
        return None
    if key not in vocabulary:
        raise UnknownValueError(column, raw)
    return vocabulary[key]
```

`backend/ingest/row_mapper.py`:

```python
"""One raw CSV row → one validated NormalizedListing. The CSV is a trust boundary."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from core.text import normalize_persian
from enums import BodyCondition, Category, Fuel, Gearbox
from ingest import column_maps as columns
from ingest import normalizers

NULLED_PRICE = "price_placeholder"
NULLED_KM = "km_implausible"
NULLED_YEAR = "year_unparsed"
NULLED_POSTED_AT = "posted_at_unparsed"


class RowRejectedError(Exception):
    """The row cannot become a listing. Collected in the ingest report, not fatal."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class NormalizedListing(BaseModel):
    token: str = Field(min_length=1)
    url: str
    category: Category
    trim: str | None
    brand: str | None
    model: str | None
    city: str = Field(min_length=1)
    district: str | None
    title: str = Field(min_length=1)
    title_normalized: str
    description: str
    year: int | None
    km: int | None
    price: int | None
    gearbox: Gearbox | None
    fuel: Fuel | None
    color: str | None
    body_condition: BodyCondition | None
    insurance_months: int | None
    vehicle_type: str | None
    is_dealer: bool
    lat: float | None
    lng: float | None
    posted_at: datetime | None
    fetched_at: datetime
    image_urls: list[str]
    thumbnail_urls: list[str]
    attributes: dict[str, Any]


@dataclass(frozen=True, slots=True)
class MappedRow:
    listing: NormalizedListing
    nulled: tuple[str, ...]


def _text(row: Mapping[str, str], column: str) -> str:
    return (row.get(column) or "").strip()


def _optional(row: Mapping[str, str], column: str) -> str | None:
    return _text(row, column) or None


def _require(row: Mapping[str, str], column: str) -> str:
    value = _text(row, column)
    if not value:
        raise RowRejectedError(f"missing_{column}")
    return value


def _gearbox(row: Mapping[str, str]) -> Gearbox | None:
    for column in columns.GEARBOX_COLUMNS:
        gearbox = columns.lookup_value(
            _text(row, column), columns.GEARBOX_VALUES, column
        )
        if gearbox is not None:
            return gearbox
    return None


def _attributes(row: Mapping[str, str], category: Category) -> dict[str, Any]:
    names = list(columns.ATTRIBUTE_COLUMNS)
    if category is Category.RENTAL:
        names.append(columns.RENT_PRICE_COLUMN)
    return {name: _text(row, name) for name in names if _text(row, name)}


def _nulled(
    row: Mapping[str, str],
    listing: NormalizedListing,
    price_column: str | None,
    year_column: str,
) -> tuple[str, ...]:
    checks = (
        (
            NULLED_PRICE,
            price_column is not None and _text(row, price_column),
            listing.price,
        ),
        (NULLED_KM, _text(row, columns.KM_COLUMN), listing.km),
        (NULLED_YEAR, _text(row, year_column), listing.year),
        (NULLED_POSTED_AT, _text(row, "posted_raw"), listing.posted_at),
    )
    return tuple(name for name, raw, parsed in checks if raw and parsed is None)


def map_row(row: Mapping[str, str]) -> MappedRow:
    category = columns.detect_category(row)
    if category is None:
        raise RowRejectedError("unknown_category")
    column_map = columns.COLUMN_MAPS[category]
    trim = _optional(row, columns.TRIM_COLUMN)
    brand_model = normalizers.split_brand_model(trim) if trim else None
    fetched_at = normalizers.parse_fetched_at(_require(row, "fetched_at"))
    posted_raw = _text(row, "posted_raw")
    title = _require(row, "title")
    listing = NormalizedListing(
        token=_require(row, "token"),
        url=_text(row, "url"),
        category=category,
        trim=trim,
        brand=brand_model.brand if brand_model else None,
        model=brand_model.model if brand_model else None,
        city=_require(row, "city"),
        district=normalizers.parse_district(posted_raw),
        title=title,
        title_normalized=normalize_persian(title),
        description=_text(row, "description"),
        year=normalizers.parse_year(_text(row, column_map.year)),
        km=normalizers.parse_km(_text(row, columns.KM_COLUMN)),
        price=(
            normalizers.parse_price(_text(row, column_map.price))
            if column_map.price
            else None
        ),
        gearbox=_gearbox(row),
        fuel=columns.lookup_value(
            _text(row, columns.FUEL_COLUMN), columns.FUEL_VALUES, columns.FUEL_COLUMN
        ),
        color=_optional(row, columns.COLOR_COLUMN),
        body_condition=columns.lookup_value(
            _text(row, columns.BODY_COLUMN), columns.BODY_VALUES, columns.BODY_COLUMN
        ),
        insurance_months=normalizers.parse_insurance_months(
            _text(row, columns.INSURANCE_COLUMN)
        ),
        vehicle_type=_optional(row, columns.VEHICLE_TYPE_COLUMN),
        is_dealer=_text(row, columns.BUSINESS_TYPE_COLUMN)
        != columns.PERSONAL_BUSINESS_TYPE,
        lat=normalizers.parse_coordinate(_text(row, "latitude")),
        lng=normalizers.parse_coordinate(_text(row, "longitude")),
        posted_at=normalizers.parse_posted_at(posted_raw, fetched_at),
        fetched_at=fetched_at,
        image_urls=normalizers.split_urls(_text(row, "image_urls")),
        thumbnail_urls=normalizers.split_urls(_text(row, "thumbnail_urls")),
        attributes=_attributes(row, category),
    )
    return MappedRow(listing, _nulled(row, listing, column_map.price, column_map.year))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run black --check .`
Expected: `74 passed`.

- [ ] **Step 5: Commit**

```bash
cd .. && git add backend/ingest backend/tests/ingest
git commit -m "feat(ingest): map CSV rows to validated listings per vehicle category

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Price estimator and deal score

**Files:**
- Create: `backend/ranking/__init__.py`, `backend/ranking/estimator.py`
- Test: `backend/tests/ranking/__init__.py`, `backend/tests/ranking/test_estimator.py`

**Interfaces:**
- Consumes: enums only (pure Python).
- Produces: `EstimatorInput(listing_id, category, trim, model, year, km, price, insurance_months, body_condition)`; `Estimate(listing_id, est_price, est_basis, est_sample_size, km_factor, insurance_factor, diff_pct, deal_score, price_suspect)`; `PriceEstimator(rows, current_year).estimate_all() -> list[Estimate]`; `BODY_FACTORS`. The field order of `EstimatorInput` matters: Task 8's repository builds it positionally from a SQL row.

Measured on the real data: estimates for 83% of cars and 60% of motorcycles; 611
listings flagged `price_suspect`.

- [ ] **Step 1: Write the failing tests**

Create empty `backend/ranking/__init__.py`, `backend/tests/ranking/__init__.py`.

`backend/tests/ranking/test_estimator.py`:

```python
import uuid

import pytest

from enums import BodyCondition, Category, EstimateBasis
from ranking.estimator import EstimatorInput, PriceEstimator

CURRENT_YEAR = 1405
TRIM = "پژو 206 تیپ ۲"
MODEL = "پژو 206"


def make_row(price: int | None, **overrides: object) -> EstimatorInput:
    fields: dict[str, object] = {
        "listing_id": uuid.uuid4(),
        "category": Category.LIGHT,
        "trim": TRIM,
        "model": MODEL,
        "year": 1398,
        "km": None,
        "price": price,
        "insurance_months": None,
        "body_condition": None,
    }
    return EstimatorInput(**{**fields, **overrides})


def estimate_first(rows: list[EstimatorInput]) -> object:
    return PriceEstimator(rows, CURRENT_YEAR).estimate_all()[0]


def test_trim_year_median_excludes_the_listing_itself() -> None:
    target = make_row(900)
    peers = [make_row(price) for price in (700, 750, 800, 850, 1000)]
    estimate = estimate_first([target, *peers])
    assert estimate.est_basis is EstimateBasis.TRIM_YEAR
    assert estimate.est_sample_size == 5
    assert estimate.est_price == 800  # median of the five peers, not of all six


def test_falls_back_to_neighbouring_years_of_the_same_trim() -> None:
    target = make_row(800)
    peers = [make_row(800, year=year) for year in (1397, 1397, 1397, 1399, 1399)]
    assert estimate_first([target, *peers]).est_basis is EstimateBasis.TRIM_NEAR_YEAR


def test_falls_back_to_the_model_when_the_trim_is_thin() -> None:
    target = make_row(800)
    peers = [make_row(800, trim=f"پژو 206 تیپ {number}") for number in range(3, 8)]
    assert estimate_first([target, *peers]).est_basis is EstimateBasis.MODEL_YEAR


def test_no_estimate_without_enough_comparables() -> None:
    estimate = estimate_first([make_row(800), make_row(810)])
    assert estimate.est_basis is EstimateBasis.NONE
    assert estimate.est_price is None
    assert estimate.deal_score is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"category": Category.HEAVY},
        {"trim": "اسکوتر(سایر)"},
        {"price": None},
        {"year": None},
    ],
)
def test_rows_that_cannot_be_compared_get_no_estimate(overrides: dict) -> None:
    target = make_row(**{"price": 800, **overrides})
    shared = {key: value for key, value in overrides.items() if key != "price"}
    peers = [make_row(800, **shared) for _ in range(6)]
    assert estimate_first([target, *peers]).est_basis is EstimateBasis.NONE


def test_high_mileage_lowers_the_estimate_and_low_mileage_raises_it() -> None:
    peers = [make_row(800, km=100_000) for _ in range(6)]
    tired = estimate_first([make_row(800, km=200_000), *peers])
    fresh = estimate_first([make_row(800, km=50_000), *peers])
    assert tired.km_factor == pytest.approx(0.92)  # ratio clamped to +1.0
    assert fresh.km_factor == pytest.approx(1.04)  # ratio clamped to -0.5
    assert tired.est_price < 800 < fresh.est_price


def test_insurance_months_adjust_the_estimate() -> None:
    peers = [make_row(800) for _ in range(5)]
    estimate = estimate_first([make_row(800, insurance_months=12), *peers])
    assert estimate.insurance_factor == pytest.approx(1.012)


def test_cheaper_than_estimate_scores_higher() -> None:
    peers = [make_row(1000) for _ in range(5)]
    cheap = estimate_first([make_row(900), *peers])
    pricey = estimate_first([make_row(1100), *peers])
    assert cheap.diff_pct == pytest.approx(-10.0)
    assert cheap.deal_score == 82 and pricey.deal_score == 62


def test_body_condition_moves_the_deal_score_only_when_known() -> None:
    peers = [make_row(1000) for _ in range(5)]
    unknown = estimate_first([make_row(1000), *peers])
    crashed = estimate_first(
        [make_row(1000, body_condition=BodyCondition.ACCIDENT), *peers]
    )
    assert unknown.deal_score == 72
    assert crashed.deal_score == 54  # 72 + 90 * (0.72 - 0.92)


@pytest.mark.parametrize("price", [10, 590, 2100])
def test_implausible_price_is_flagged_not_rewarded(price: int) -> None:
    peers = [make_row(1000) for _ in range(5)]
    estimate = estimate_first([make_row(price), *peers])
    assert estimate.price_suspect is True
    assert estimate.deal_score is None and estimate.diff_pct is None
    assert estimate.est_price == 1000  # the estimate itself is still reported
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/ranking -q`
Expected: `ModuleNotFoundError: No module named 'ranking.estimator'`.

- [ ] **Step 3: Implement**

`backend/ranking/estimator.py`:

```python
"""Comparables-based price estimate and deal score. Pure Python, no I/O (spec §6.3)."""

import statistics
import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from enums import BodyCondition, Category, EstimateBasis

MIN_COMPARABLES = 5
NEAR_YEAR_SPAN = 1
FAR_YEAR_SPAN = 2
KM_WEIGHT = 0.08
KM_RATIO_FLOOR = -0.5
KM_RATIO_CEILING = 1.0
INSURANCE_NEUTRAL_MONTHS = 6
INSURANCE_WEIGHT_PER_MONTH = 0.002
DEAL_BASELINE = 72
# ponytail: slope fitted to the real price spread (IQR about -10%..+12%). The
# frontend's 2.4 saturates 25% of scores at the clamp; 1.0 saturates under 5%.
DEAL_DIFF_WEIGHT = 1.0
DEAL_KM_WEIGHT = 120
DEAL_BODY_WEIGHT = 90
DEAL_BODY_NEUTRAL = 0.92
DEAL_SCORE_MIN = 5
DEAL_SCORE_MAX = 99
CATCH_ALL_MARKER = "سایر"
# Beyond these bounds the listed price is a deposit, a typo or a placeholder, not a
# deal: 6.6% of cars and 22% of motorcycles in the first scrape.
SUSPECT_BELOW_PCT = -40.0
SUSPECT_ABOVE_PCT = 100.0
ESTIMATED_CATEGORIES = frozenset({Category.LIGHT, Category.MOTORCYCLE})

# Mirrors frontend/src/lib/catalog.ts BODIES where an equivalent exists.
BODY_FACTORS: Mapping[BodyCondition, float] = {
    BodyCondition.INTACT: 1.0,
    BodyCondition.NO_PAINT: 1.0,
    BodyCondition.ORIGINAL: 1.0,
    BodyCondition.MINOR_SCRATCHES: 0.98,
    BodyCondition.PARTIAL_PAINT: 0.94,
    BodyCondition.RESTORED: 0.9,
    BodyCondition.DROPPED: 0.85,
    BodyCondition.HEAVY_PAINT: 0.82,
    BodyCondition.ACCIDENT: 0.72,
}

type GroupKey = tuple[Category, str, int]


@dataclass(frozen=True, slots=True)
class EstimatorInput:
    listing_id: uuid.UUID
    category: Category
    trim: str | None
    model: str | None
    year: int | None
    km: int | None
    price: int | None
    insurance_months: int | None
    body_condition: BodyCondition | None


@dataclass(frozen=True, slots=True)
class Estimate:
    listing_id: uuid.UUID
    est_price: int | None
    est_basis: EstimateBasis
    est_sample_size: int
    km_factor: float
    insurance_factor: float
    diff_pct: float | None
    deal_score: int | None
    price_suspect: bool = False


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _is_comparable(row: EstimatorInput) -> bool:
    return (
        row.category in ESTIMATED_CATEGORIES
        and row.price is not None
        and row.year is not None
        and row.trim is not None
        and row.model is not None
        and CATCH_ALL_MARKER not in row.trim
    )


class PriceEstimator:
    def __init__(self, rows: Sequence[EstimatorInput], current_year: int) -> None:
        self._rows = rows
        self._current_year = current_year
        self._by_trim: dict[GroupKey, list[int]] = defaultdict(list)
        self._by_model: dict[GroupKey, list[int]] = defaultdict(list)
        self._expected_km = self._build_expected_km(rows)
        for row in filter(_is_comparable, rows):
            self._by_trim[(row.category, row.trim, row.year)].append(row.price)
            self._by_model[(row.category, row.model, row.year)].append(row.price)

    def estimate_all(self) -> list[Estimate]:
        return [self._estimate(row) for row in self._rows]

    def _build_expected_km(
        self, rows: Iterable[EstimatorInput]
    ) -> dict[tuple[Category, int], float]:
        by_age: dict[tuple[Category, int], list[int]] = defaultdict(list)
        for row in rows:
            if row.km is not None and row.year is not None:
                by_age[(row.category, self._current_year - row.year)].append(row.km)
        return {
            key: statistics.median(values)
            for key, values in by_age.items()
            if len(values) >= MIN_COMPARABLES
        }

    def _estimate(self, row: EstimatorInput) -> Estimate:
        km_factor = self._km_factor(row)
        insurance_factor = self._insurance_factor(row)
        base, basis, sample_size = self._base_price(row)
        if base is None or row.price is None:
            return self._no_estimate(row, km_factor, insurance_factor)
        est_price = base * km_factor * insurance_factor
        diff_pct = (row.price - est_price) / est_price * 100
        suspect = not SUSPECT_BELOW_PCT <= diff_pct <= SUSPECT_ABOVE_PCT
        score = (
            None
            if suspect
            else self._deal_score(diff_pct, km_factor, row.body_condition)
        )
        return Estimate(
            listing_id=row.listing_id,
            est_price=round(est_price),
            est_basis=basis,
            est_sample_size=sample_size,
            km_factor=km_factor,
            insurance_factor=insurance_factor,
            diff_pct=None if suspect else round(diff_pct, 1),
            deal_score=score,
            price_suspect=suspect,
        )

    @staticmethod
    def _no_estimate(
        row: EstimatorInput, km_factor: float, insurance_factor: float
    ) -> Estimate:
        return Estimate(
            listing_id=row.listing_id,
            est_price=None,
            est_basis=EstimateBasis.NONE,
            est_sample_size=0,
            km_factor=km_factor,
            insurance_factor=insurance_factor,
            diff_pct=None,
            deal_score=None,
        )

    def _base_price(
        self, row: EstimatorInput
    ) -> tuple[float | None, EstimateBasis, int]:
        if not _is_comparable(row):
            return None, EstimateBasis.NONE, 0
        attempts = (
            (self._by_trim, row.trim, 0, EstimateBasis.TRIM_YEAR),
            (self._by_trim, row.trim, NEAR_YEAR_SPAN, EstimateBasis.TRIM_NEAR_YEAR),
            (self._by_model, row.model, 0, EstimateBasis.MODEL_YEAR),
            (self._by_model, row.model, FAR_YEAR_SPAN, EstimateBasis.MODEL_NEAR_YEAR),
        )
        for groups, name, span, basis in attempts:
            prices = self._comparables(groups, row, name, span)
            if len(prices) >= MIN_COMPARABLES:
                return statistics.median(prices), basis, len(prices)
        return None, EstimateBasis.NONE, 0

    def _comparables(
        self,
        groups: Mapping[GroupKey, list[int]],
        row: EstimatorInput,
        name: str,
        span: int,
    ) -> list[int]:
        prices: list[int] = []
        for year in range(row.year - span, row.year + span + 1):
            prices.extend(groups.get((row.category, name, year), ()))
        prices.remove(row.price)  # leave-one-out: a listing never validates itself
        return prices

    def _km_factor(self, row: EstimatorInput) -> float:
        if row.km is None or row.year is None:
            return 1.0
        expected = self._expected_km.get((row.category, self._current_year - row.year))
        if not expected:
            return 1.0
        ratio = _clamp((row.km - expected) / expected, KM_RATIO_FLOOR, KM_RATIO_CEILING)
        return 1 - ratio * KM_WEIGHT

    @staticmethod
    def _insurance_factor(row: EstimatorInput) -> float:
        if row.insurance_months is None:
            return 1.0
        months_over_neutral = row.insurance_months - INSURANCE_NEUTRAL_MONTHS
        return 1 + months_over_neutral * INSURANCE_WEIGHT_PER_MONTH

    @staticmethod
    def _deal_score(
        diff_pct: float, km_factor: float, body: BodyCondition | None
    ) -> int:
        body_term = (
            DEAL_BODY_WEIGHT * (BODY_FACTORS[body] - DEAL_BODY_NEUTRAL) if body else 0.0
        )
        raw = (
            DEAL_BASELINE
            - DEAL_DIFF_WEIGHT * diff_pct
            + DEAL_KM_WEIGHT * (km_factor - 1)
            + body_term
        )
        return round(_clamp(raw, DEAL_SCORE_MIN, DEAL_SCORE_MAX))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run black --check .`
Expected: `89 passed`.

- [ ] **Step 5: Commit**

```bash
cd .. && git add backend/ranking backend/tests/ranking
git commit -m "feat(ranking): add comparables price estimator with suspect-price guard

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Ranking core — the sorting algorithm

**Files:**
- Create: `backend/ranking/weights.py`, `backend/ranking/types.py`, `backend/ranking/labels.py`, `backend/ranking/closeness.py`, `backend/ranking/ranker.py`
- Test: `backend/tests/ranking/test_ranker.py`

**Interfaces:**
- Consumes: enums, `core.text.to_persian_digits`. **Nothing else** — no SQLAlchemy, Redis, FastAPI or Pydantic AI import may appear under `ranking/`.
- Produces: `RankingWeights` / `DEFAULT_WEIGHTS`; dataclasses `VehicleTarget(level, brand, model=None, trim=None)`, `ResolvedCity(name, lat, lng)`, `RankingQuery(targets, year_min, year_max, price_min, price_max, km_max, cities, gearbox, fuel, colors, has_text, sort)`, `Candidate(id, brand, model, trim, year, km, price, city, lat, lng, gearbox, fuel, color, text_similarity, deal_score, posted_at)`, `CriterionScore`, `RankedListing(id, rank, match, is_exact, labels)`; `ListingRanker(weights=DEFAULT_WEIGHTS).rank(query, candidates, now) -> list[RankedListing]`; `labels.format_toman`, `labels.GEARBOX_NAMES`, `labels.FUEL_NAMES`. The field order of `Candidate` matters: Task 8's repository builds it positionally from a SQL row.

On the real CSV this ranks 163 candidates in 7 ms and returns only 206s, exact first,
for «۲۰۶ تیپ ۲ مدل ۹۸ زیر ۹۰۰ میلیون تهران».

- [ ] **Step 1: Write the failing tests**

`backend/tests/ranking/test_ranker.py`:

```python
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from enums import Fuel, Gearbox, MentionLevel, SortKey
from ranking import labels
from ranking.ranker import ListingRanker
from ranking.types import Candidate, RankingQuery, ResolvedCity, VehicleTarget

NOW = datetime(2026, 9, 17, 20, 0, tzinfo=UTC)
TEHRAN = ResolvedCity("تهران", 35.70, 51.40)
MILLION = 1_000_000
TRIM_2 = "پژو 206 تیپ ۲"
TRIM_5 = "پژو 206 تیپ ۵"

QUERY = RankingQuery(
    targets=(VehicleTarget(MentionLevel.TRIM, "پژو", "پژو 206", TRIM_2),),
    year_min=1398,
    year_max=1398,
    price_max=800 * MILLION,
    km_max=100_000,
    cities=(TEHRAN,),
    gearbox=Gearbox.MANUAL,
)
EXACT_MATCH = Candidate(
    id=uuid.UUID(int=1),
    brand="پژو",
    model="پژو 206",
    trim=TRIM_2,
    year=1398,
    km=60_000,
    price=780 * MILLION,
    city="تهران",
    lat=35.72,
    lng=51.42,
    gearbox=Gearbox.MANUAL,
    fuel=Fuel.PETROL,
    color="سفید",
    deal_score=70,
    posted_at=NOW - timedelta(hours=3),
)


def rank(query: RankingQuery, *candidates: Candidate) -> list:
    return ListingRanker().rank(query, candidates, NOW)


def variant(number: int, **changes: object) -> Candidate:
    return replace(EXACT_MATCH, id=uuid.UUID(int=number), **changes)


def test_exact_match_scores_full_match_and_has_no_labels() -> None:
    (result,) = rank(QUERY, EXACT_MATCH)
    assert result.match == 1.0
    assert result.is_exact is True
    assert result.labels == ()


DEGRADATIONS = {
    "older": {"year": 1397},
    "over_budget": {"price": 850 * MILLION},
    "other_trim": {"trim": TRIM_5},
    "karaj": {"city": "کرج", "lat": 35.83, "lng": 50.97},
    "high_km": {"km": 130_000},
    "automatic": {"gearbox": Gearbox.AUTOMATIC},
}


@pytest.mark.parametrize("changes", DEGRADATIONS.values(), ids=DEGRADATIONS.keys())
def test_degrading_any_single_criterion_never_raises_the_rank(changes: dict) -> None:
    results = rank(QUERY, variant(2, **changes), EXACT_MATCH)
    assert [result.id for result in results] == [EXACT_MATCH.id, uuid.UUID(int=2)]
    assert results[1].is_exact is False
    assert results[1].match < 1.0


def test_near_miss_labels_explain_the_two_biggest_gaps() -> None:
    near_miss = variant(2, year=1397, price=820 * MILLION, color="مشکی")
    (result,) = rank(QUERY, near_miss)
    # year costs 2.0 x 0.2 = 0.40 of weighted closeness, price only 2.5 x 0.1 = 0.25
    assert result.labels == ("یک سال قدیمی‌تر", "۲۰ میلیون بالاتر از بودجه")


def test_nearer_city_outranks_a_far_one() -> None:
    karaj = variant(2, city="کرج", lat=35.83, lng=50.97)
    mashhad = variant(3, city="مشهد", lat=36.30, lng=59.60)
    results = rank(QUERY, mashhad, karaj)
    assert [result.id for result in results] == [karaj.id, mashhad.id]
    assert "کیلومتر دورتر · کرج" in results[0].labels[0]


def test_unknown_price_is_neutral_and_never_beats_an_exact_priced_match() -> None:
    negotiable = variant(2, price=None, deal_score=None)
    results = rank(QUERY, negotiable, EXACT_MATCH)
    assert results[0].id == EXACT_MATCH.id
    assert results[1].labels == (labels.PRICE_UNKNOWN,)
    assert results[1].is_exact is False


def test_vehicle_levels() -> None:
    model_query = RankingQuery(
        targets=(VehicleTarget(MentionLevel.MODEL, "پژو", "پژو 206"),)
    )
    other_trim = variant(2, trim=TRIM_5)
    other_model = variant(3, model="پژو پارس", trim="پژو پارس سال")
    results = rank(model_query, other_trim, other_model)
    # a same-brand, other-model listing scores 0.3: under the 0.4 cutoff
    assert [result.id for result in results] == [other_trim.id]
    assert results[0].match == 1.0  # any trim satisfies a model-level query
    brand_query = RankingQuery(targets=(VehicleTarget(MentionLevel.BRAND, "پژو"),))
    matches = {result.match for result in rank(brand_query, other_trim, other_model)}
    assert matches == {1.0}


def test_exact_match_precedes_a_near_miss_with_a_better_deal() -> None:
    poor_deal_exact = variant(2, deal_score=20)
    great_deal_near_miss = variant(3, year=1397, deal_score=99)
    results = rank(QUERY, great_deal_near_miss, poor_deal_exact)
    assert results[0].rank < results[1].rank  # raw rank alone would flip them
    assert [result.id for result in results] == [
        poor_deal_exact.id,
        great_deal_near_miss.id,
    ]


def test_other_model_never_outranks_the_requested_model() -> None:
    great_deal_405 = variant(2, model="پژو 405", trim="پژو 405 GLX", deal_score=99)
    plain_206 = variant(3, year=1396, price=990 * MILLION, deal_score=40)
    results = rank(QUERY, great_deal_405, plain_206)
    assert [result.id for result in results] == [plain_206.id, great_deal_405.id]
    assert results[0].rank < results[1].rank  # the 405 has the higher raw rank…
    assert results[1].labels[0] == "مدل متفاوت · پژو 405"  # …and says why it is last


def test_results_below_the_match_cutoff_are_dropped() -> None:
    wrong = variant(
        2,
        model="پژو پارس",
        trim="پژو پارس سال",
        year=1390,
        price=1_200 * MILLION,
        gearbox=Gearbox.AUTOMATIC,
    )
    assert rank(QUERY, wrong) == []


def test_browse_mode_ranks_by_deal_and_freshness() -> None:
    good_deal = variant(2, deal_score=95)
    stale = variant(3, deal_score=95, posted_at=NOW - timedelta(days=30))
    results = rank(RankingQuery(), EXACT_MATCH, stale, good_deal)
    # a fresh fair deal beats a month-old great one: freshness decays over 14 days
    assert [result.id for result in results] == [good_deal.id, EXACT_MATCH.id, stale.id]
    assert results[0].match is None and results[0].is_exact is True


def test_explicit_sort_orders_inside_the_exact_tier_first() -> None:
    cheap_near_miss = variant(2, year=1396, price=500 * MILLION)
    pricey_exact = variant(3, price=790 * MILLION)
    query = replace(QUERY, sort=SortKey.PRICE)
    results = rank(query, cheap_near_miss, pricey_exact, EXACT_MATCH)
    assert [result.id for result in results] == [
        EXACT_MATCH.id,
        pricey_exact.id,
        cheap_near_miss.id,
    ]


def test_ranking_is_deterministic_for_ties() -> None:
    twin = variant(2)
    assert rank(QUERY, twin, EXACT_MATCH) == rank(QUERY, EXACT_MATCH, twin)


def test_format_toman_switches_to_billions() -> None:
    assert labels.format_toman(20 * MILLION) == "۲۰ میلیون"
    assert labels.format_toman(1_250 * MILLION) == "۱.۲۵ میلیارد"
    assert labels.format_toman(2_000 * MILLION) == "۲ میلیارد"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/ranking/test_ranker.py -q`
Expected: `ModuleNotFoundError: No module named 'ranking.labels'`.

- [ ] **Step 3: Implement**

`backend/ranking/weights.py`:

```python
"""Every tunable number of the ranking algorithm, in one frozen place (spec §7.4).
Changing a value here means re-running the golden-query suite."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from enums import Criterion


def _default_criterion_weights() -> Mapping[Criterion, float]:
    return MappingProxyType(
        {
            Criterion.VEHICLE: 3.0,
            Criterion.PRICE: 2.5,
            Criterion.YEAR: 2.0,
            Criterion.CITY: 1.5,
            Criterion.KM: 1.5,
            Criterion.GEARBOX: 1.0,
            Criterion.FUEL: 1.0,
            Criterion.TEXT: 1.0,
            Criterion.COLOR: 0.5,
        }
    )


@dataclass(frozen=True, slots=True)
class RankingWeights:
    criteria: Mapping[Criterion, float] = field(
        default_factory=_default_criterion_weights
    )
    match_share: float = 0.55
    deal_share: float = 0.30
    fresh_share: float = 0.15
    browse_deal_share: float = 0.67
    browse_fresh_share: float = 0.33
    min_match_score: float = 0.4
    unknown_closeness: float = 0.5
    neutral_deal: float = 0.5
    neutral_fresh: float = 0.5
    same_model_other_trim: float = 0.8
    same_brand_other_model: float = 0.3
    price_tolerance: float = 0.25
    km_tolerance: float = 0.5
    year_tolerance: int = 5
    city_radius_km: float = 300.0
    other_city_ceiling: float = 0.9
    freshness_decay_days: float = 14.0
    max_labels: int = 2


DEFAULT_WEIGHTS = RankingWeights()
```

`backend/ranking/types.py`:

```python
"""Plain data carried between the search stages. No behaviour, no I/O."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from enums import Criterion, Fuel, Gearbox, MentionLevel, SortKey


@dataclass(frozen=True, slots=True)
class VehicleTarget:
    level: MentionLevel
    brand: str
    model: str | None = None
    trim: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedCity:
    name: str
    lat: float | None
    lng: float | None


@dataclass(frozen=True, slots=True)
class RankingQuery:
    targets: tuple[VehicleTarget, ...] = ()
    year_min: int | None = None
    year_max: int | None = None
    price_min: int | None = None
    price_max: int | None = None
    km_max: int | None = None
    cities: tuple[ResolvedCity, ...] = ()
    gearbox: Gearbox | None = None
    fuel: Fuel | None = None
    colors: tuple[str, ...] = ()
    has_text: bool = False
    sort: SortKey = SortKey.RELEVANCE


@dataclass(frozen=True, slots=True)
class Candidate:
    id: uuid.UUID
    brand: str | None = None
    model: str | None = None
    trim: str | None = None
    year: int | None = None
    km: int | None = None
    price: int | None = None  # None when missing OR flagged price_suspect
    city: str | None = None
    lat: float | None = None
    lng: float | None = None
    gearbox: Gearbox | None = None
    fuel: Fuel | None = None
    color: str | None = None
    text_similarity: float | None = None
    deal_score: int | None = None
    posted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CriterionScore:
    criterion: Criterion
    closeness: float
    label: str | None = None


@dataclass(frozen=True, slots=True)
class RankedListing:
    id: uuid.UUID
    rank: float
    match: float | None
    is_exact: bool
    labels: tuple[str, ...]
```

`backend/ranking/labels.py`:

```python
"""Persian near-miss labels, built server-side: the frontend holds no ranking logic."""

from core.text import to_persian_digits
from enums import Fuel, Gearbox

TOMAN_PER_MILLION = 1_000_000
MILLIONS_PER_BILLION = 1_000
KM_PER_THOUSAND = 1_000

PRICE_UNKNOWN = "قیمت توافقی"
KM_UNKNOWN = "کارکرد نامشخص"

GEARBOX_NAMES = {Gearbox.MANUAL: "دنده‌ای", Gearbox.AUTOMATIC: "اتوماتیک"}
FUEL_NAMES = {
    Fuel.PETROL: "بنزینی",
    Fuel.DUAL_FACTORY: "دوگانه‌سوز شرکتی",
    Fuel.DUAL_AFTERMARKET: "دوگانه‌سوز دستی",
    Fuel.HYBRID: "هیبرید",
    Fuel.PLUGIN_HYBRID: "پلاگین هیبرید",
    Fuel.ELECTRIC: "برقی",
    Fuel.DIESEL: "گازوئیلی",
}


def format_toman(amount: int) -> str:
    millions = round(amount / TOMAN_PER_MILLION)
    if millions >= MILLIONS_PER_BILLION:
        billions = f"{millions / MILLIONS_PER_BILLION:.2f}".rstrip("0").rstrip(".")
        return f"{to_persian_digits(billions)} میلیارد"
    return f"{to_persian_digits(millions)} میلیون"


def over_budget(amount: int) -> str:
    return f"{format_toman(amount)} بالاتر از بودجه"


def under_budget(amount: int) -> str:
    return f"{format_toman(amount)} پایین‌تر از بازهٔ قیمت"


def year_gap(years: int, *, older: bool) -> str:
    count = "یک" if years == 1 else to_persian_digits(years)
    return f"{count} سال {'قدیمی‌تر' if older else 'جدیدتر'}"


def over_km(extra_km: int) -> str:
    thousands = max(1, round(extra_km / KM_PER_THOUSAND))
    return f"{to_persian_digits(thousands)} هزار کیلومتر بیشتر از سقف"


def farther(distance_km: float, city: str) -> str:
    return f"{to_persian_digits(round(distance_km))} کیلومتر دورتر · {city}"


def other_city(city: str) -> str:
    return f"شهر دیگر · {city}"


def other_trim(trim: str) -> str:
    return f"تیپ متفاوت · {trim}"


def other_model(model: str) -> str:
    return f"مدل متفاوت · {model}"


def gearbox_is(gearbox: Gearbox) -> str:
    return f"گیربکس {GEARBOX_NAMES[gearbox]}"


def fuel_is(fuel: Fuel) -> str:
    return f"سوخت {FUEL_NAMES[fuel]}"


def color_is(color: str) -> str:
    return f"رنگ {color}"
```

`backend/ranking/closeness.py`:

```python
"""One pure function per criterion: (query, candidate, weights) → CriterionScore, or
None when the user did not state that criterion. Closeness is 1.0 for a full match,
decays to 0.0, and is `unknown_closeness` when the listing lacks the value."""

import math
from collections.abc import Callable

from enums import Criterion, MentionLevel
from ranking import labels
from ranking.types import Candidate, CriterionScore, RankingQuery, VehicleTarget
from ranking.weights import RankingWeights

EARTH_RADIUS_KM = 6371.0
EXACT = 1.0
MISS = 0.0

type ClosenessFunction = Callable[
    [RankingQuery, Candidate, RankingWeights], CriterionScore | None
]


def haversine_km(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    lat_delta = math.radians(lat_b - lat_a)
    lng_delta = math.radians(lng_b - lng_a)
    chord = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(math.radians(lat_a))
        * math.cos(math.radians(lat_b))
        * math.sin(lng_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(chord))


def _linear_decay(excess: float, tolerance: float) -> float:
    if tolerance <= 0:
        return MISS
    return max(MISS, EXACT - excess / tolerance)


def _target_closeness(
    target: VehicleTarget, candidate: Candidate, weights: RankingWeights
) -> float:
    if candidate.brand != target.brand:
        return MISS
    if target.level is MentionLevel.BRAND:
        return EXACT
    if candidate.model != target.model:
        return weights.same_brand_other_model
    if target.level is MentionLevel.MODEL or candidate.trim == target.trim:
        return EXACT
    return weights.same_model_other_trim


def vehicle_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if not query.targets:
        return None
    closeness = max(
        _target_closeness(target, candidate, weights) for target in query.targets
    )
    label = None
    if closeness == weights.same_model_other_trim and candidate.trim:
        label = labels.other_trim(candidate.trim)
    elif closeness < weights.same_model_other_trim and candidate.model:
        label = labels.other_model(candidate.model)
    return CriterionScore(Criterion.VEHICLE, closeness, label)


def price_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if query.price_min is None and query.price_max is None:
        return None
    if candidate.price is None:
        return CriterionScore(
            Criterion.PRICE, weights.unknown_closeness, labels.PRICE_UNKNOWN
        )
    if query.price_max is not None and candidate.price > query.price_max:
        excess = candidate.price - query.price_max
        closeness = _linear_decay(excess, query.price_max * weights.price_tolerance)
        return CriterionScore(Criterion.PRICE, closeness, labels.over_budget(excess))
    if query.price_min is not None and candidate.price < query.price_min:
        shortfall = query.price_min - candidate.price
        closeness = _linear_decay(shortfall, query.price_min * weights.price_tolerance)
        return CriterionScore(
            Criterion.PRICE, closeness, labels.under_budget(shortfall)
        )
    return CriterionScore(Criterion.PRICE, EXACT)


def year_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if query.year_min is None and query.year_max is None:
        return None
    if candidate.year is None:
        return CriterionScore(Criterion.YEAR, weights.unknown_closeness)
    if query.year_min is not None and candidate.year < query.year_min:
        gap = query.year_min - candidate.year
        return CriterionScore(
            Criterion.YEAR,
            _linear_decay(gap, weights.year_tolerance),
            labels.year_gap(gap, older=True),
        )
    if query.year_max is not None and candidate.year > query.year_max:
        gap = candidate.year - query.year_max
        return CriterionScore(
            Criterion.YEAR,
            _linear_decay(gap, weights.year_tolerance),
            labels.year_gap(gap, older=False),
        )
    return CriterionScore(Criterion.YEAR, EXACT)


def km_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if query.km_max is None:
        return None
    if candidate.km is None:
        return CriterionScore(
            Criterion.KM, weights.unknown_closeness, labels.KM_UNKNOWN
        )
    if candidate.km <= query.km_max:
        return CriterionScore(Criterion.KM, EXACT)
    excess = candidate.km - query.km_max
    closeness = _linear_decay(excess, query.km_max * weights.km_tolerance)
    return CriterionScore(Criterion.KM, closeness, labels.over_km(excess))


def city_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if not query.cities:
        return None
    if any(city.name == candidate.city for city in query.cities):
        return CriterionScore(Criterion.CITY, EXACT)
    if candidate.lat is None or candidate.lng is None:
        return CriterionScore(
            Criterion.CITY, MISS, labels.other_city(candidate.city or "")
        )
    distances = [
        haversine_km(city.lat, city.lng, candidate.lat, candidate.lng)
        for city in query.cities
        if city.lat is not None and city.lng is not None
    ]
    if not distances:
        return CriterionScore(
            Criterion.CITY, MISS, labels.other_city(candidate.city or "")
        )
    nearest = min(distances)
    closeness = min(
        weights.other_city_ceiling, _linear_decay(nearest, weights.city_radius_km)
    )
    return CriterionScore(
        Criterion.CITY, closeness, labels.farther(nearest, candidate.city or "")
    )


def gearbox_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if query.gearbox is None:
        return None
    if candidate.gearbox is None:
        return CriterionScore(Criterion.GEARBOX, weights.unknown_closeness)
    if candidate.gearbox is query.gearbox:
        return CriterionScore(Criterion.GEARBOX, EXACT)
    return CriterionScore(Criterion.GEARBOX, MISS, labels.gearbox_is(candidate.gearbox))


def fuel_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if query.fuel is None:
        return None
    if candidate.fuel is None:
        return CriterionScore(Criterion.FUEL, weights.unknown_closeness)
    if candidate.fuel is query.fuel:
        return CriterionScore(Criterion.FUEL, EXACT)
    return CriterionScore(Criterion.FUEL, MISS, labels.fuel_is(candidate.fuel))


def color_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if not query.colors:
        return None
    if candidate.color is None:
        return CriterionScore(Criterion.COLOR, weights.unknown_closeness)
    if candidate.color in query.colors:
        return CriterionScore(Criterion.COLOR, EXACT)
    return CriterionScore(Criterion.COLOR, MISS, labels.color_is(candidate.color))


def text_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if not query.has_text:
        return None
    return CriterionScore(Criterion.TEXT, candidate.text_similarity or MISS)


CLOSENESS_FUNCTIONS: tuple[ClosenessFunction, ...] = (
    vehicle_closeness,
    price_closeness,
    year_closeness,
    city_closeness,
    km_closeness,
    gearbox_closeness,
    fuel_closeness,
    text_closeness,
    color_closeness,
)
```

`backend/ranking/ranker.py`:

```python
"""ListingRanker — the sorting algorithm (spec §7.4). Pure Python, no I/O.

match = Σ wᵢ·cᵢ / Σ wᵢ      over the criteria the user stated
rank  = 0.55·match + 0.30·deal + 0.15·fresh

`rank` orders listings INSIDE a tier; two tiers come first, whatever the rank:
1. exact matches (every stated criterion satisfied) precede near-misses;
2. the vehicle is identity, the other criteria are preferences — listings of the
   requested model precede listings that only share its brand. Without this a
   great-deal Peugeot 405 outranks real 206s for a "206" search.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from enums import Criterion, SortKey
from ranking.closeness import CLOSENESS_FUNCTIONS, EXACT
from ranking.types import Candidate, CriterionScore, RankedListing, RankingQuery
from ranking.weights import DEFAULT_WEIGHTS, RankingWeights

SECONDS_PER_DAY = 86_400
MAX_DEAL_SCORE = 100
RANK_PRECISION = 4
_MISSING_LAST = math.inf
_NO_DEAL_SCORE = -1


@dataclass(frozen=True, slots=True)
class _Scored:
    listing: RankedListing
    candidate: Candidate
    off_model: bool


class ListingRanker:
    def __init__(self, weights: RankingWeights = DEFAULT_WEIGHTS) -> None:
        self._weights = weights

    def rank(
        self, query: RankingQuery, candidates: Sequence[Candidate], now: datetime
    ) -> list[RankedListing]:
        scored = [self._score(query, candidate, now) for candidate in candidates]
        kept = [item for item in scored if self._passes_cutoff(item.listing)]
        kept.sort(key=lambda item: self._sort_key(query.sort, item))
        return [item.listing for item in kept]

    def _score(
        self, query: RankingQuery, candidate: Candidate, now: datetime
    ) -> _Scored:
        scores = [
            score
            for function in CLOSENESS_FUNCTIONS
            if (score := function(query, candidate, self._weights))
        ]
        match = self._match(scores)
        rank = self._combine(
            match, self._deal(candidate), self._freshness(candidate, now)
        )
        listing = RankedListing(
            id=candidate.id,
            rank=round(rank, RANK_PRECISION),
            match=None if match is None else round(match, RANK_PRECISION),
            is_exact=all(score.closeness == EXACT for score in scores),
            labels=self._labels(scores),
        )
        return _Scored(listing, candidate, self._is_off_model(scores))

    def _is_off_model(self, scores: Sequence[CriterionScore]) -> bool:
        return any(
            score.criterion is Criterion.VEHICLE
            and score.closeness < self._weights.same_model_other_trim
            for score in scores
        )

    def _match(self, scores: Sequence[CriterionScore]) -> float | None:
        if not scores:
            return None
        total_weight = sum(self._weights.criteria[score.criterion] for score in scores)
        weighted = sum(
            self._weights.criteria[score.criterion] * score.closeness
            for score in scores
        )
        return weighted / total_weight

    def _combine(self, match: float | None, deal: float, fresh: float) -> float:
        weights = self._weights
        if match is None:
            return weights.browse_deal_share * deal + weights.browse_fresh_share * fresh
        return (
            weights.match_share * match
            + weights.deal_share * deal
            + weights.fresh_share * fresh
        )

    def _deal(self, candidate: Candidate) -> float:
        if candidate.deal_score is None:
            return self._weights.neutral_deal
        return candidate.deal_score / MAX_DEAL_SCORE

    def _freshness(self, candidate: Candidate, now: datetime) -> float:
        if candidate.posted_at is None:
            return self._weights.neutral_fresh
        age_seconds = (now - candidate.posted_at).total_seconds()
        age_days = max(0.0, age_seconds / SECONDS_PER_DAY)
        return math.exp(-age_days / self._weights.freshness_decay_days)

    def _weighted_loss(self, score: CriterionScore) -> float:
        return self._weights.criteria[score.criterion] * (EXACT - score.closeness)

    def _labels(self, scores: Sequence[CriterionScore]) -> tuple[str, ...]:
        missed = [score for score in scores if score.closeness < EXACT]
        missed.sort(key=self._weighted_loss, reverse=True)
        found = [score.label for score in missed if score.label]
        return tuple(found[: self._weights.max_labels])

    def _passes_cutoff(self, listing: RankedListing) -> bool:
        return listing.match is None or listing.match >= self._weights.min_match_score

    @staticmethod
    def _explicit_value(sort: SortKey, candidate: Candidate, posted: float) -> float:
        if sort is SortKey.PRICE:
            return candidate.price if candidate.price is not None else _MISSING_LAST
        if sort is SortKey.KM:
            return candidate.km if candidate.km is not None else _MISSING_LAST
        if sort is SortKey.NEWEST:
            return -posted
        deal_score = candidate.deal_score
        return -(deal_score if deal_score is not None else _NO_DEAL_SCORE)

    @classmethod
    def _sort_key(cls, sort: SortKey, item: _Scored) -> tuple[object, ...]:
        listing, candidate = item.listing, item.candidate
        posted = candidate.posted_at.timestamp() if candidate.posted_at else 0.0
        tier = (not listing.is_exact, item.off_model)
        relevance = (-listing.rank, -posted, str(listing.id))
        if sort is SortKey.RELEVANCE:
            return (*tier, *relevance)
        explicit = cls._explicit_value(sort, candidate, posted)
        return (*tier, explicit, *relevance)
```

- [ ] **Step 4: Run the tests and the purity check**

Run: `uv run pytest -q && uv run ruff check . && uv run black --check .`
Expected: `107 passed`.

Run: `grep -rnE "sqlalchemy|redis|fastapi|pydantic_ai" ranking/ || echo "ranking/ is pure"`
Expected: `ranking/ is pure`.

- [ ] **Step 5: Commit**

```bash
cd .. && git add backend/ranking backend/tests/ranking
git commit -m "feat(ranking): add soft-match closeness functions and ListingRanker

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Cache, repositories, ingest pipeline and test fixture

**Files:**
- Create: `backend/core/cache.py`, `backend/repositories/__init__.py`, `backend/repositories/city_repository.py`, `backend/repositories/catalog_repository.py`, `backend/repositories/listing_repository.py`, `backend/ingest/report.py`, `backend/ingest/pipeline.py`
- Create: `backend/tests/support.py`, `backend/tests/fixtures/__init__.py`, `backend/tests/fixtures/make_fixture.py`, `backend/tests/fixtures/listings_sample.csv` (generated)
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/core/test_cache.py`, `backend/tests/repositories/__init__.py`, `backend/tests/repositories/test_repositories.py`

**Interfaces:**
- Consumes: models, `ranking.estimator`, `ranking.types.Candidate`, `ingest.row_mapper`.
- Produces: `core.cache.Cache(client)` with `get_json(key)`, `set_json(key, value, ttl_seconds)`, `get_data_version() -> int`, `bump_data_version() -> int`, `ping() -> bool`, `close()`; `CityRepository(session)` with `upsert_names`, `refresh_statistics`, `find_by_names(names) -> list[City]`, `list_names`, `list_top(limit)`; `CatalogRepository(session)` with `upsert_entries`, `refresh_counts`, `search(query, category, min_similarity, limit) -> list[CatalogMatch(brand, model, trim, score)]`, `list_top_models(category, limit) -> list[ModelCount]`; `ListingRepository(session)` with `upsert_many`, `load_estimator_inputs`, `apply_estimates`, `newest_fetched_at`, `count`, `count_by_category`, `get_by_id`, `get_by_ids` (order-preserving, joins city + catalog), `find_candidates(filters: CandidateFilter, limit) -> list[Candidate]`; `CandidateFilter(category, brands, text, only_below_market, price_floor, price_ceiling, km_ceiling, year_floor, year_ceiling, exclude_id)`; `IngestPipeline(cities, catalog, listings, cache).run(csv_path) -> IngestReport`; test double `tests.support.DictCache`; pytest fixtures `cache` and `seeded_session`.

- [ ] **Step 1: Build the committed test fixture**

Create empty `backend/repositories/__init__.py`, `backend/tests/fixtures/__init__.py`, `backend/tests/repositories/__init__.py`.

`backend/tests/fixtures/make_fixture.py`:

```python
"""Builds tests/fixtures/listings_sample.csv from the real (untracked) Divar CSV.

    uv run python -m tests.fixtures.make_fixture <path-to-the-real-csv>

Deterministic: rows are picked in token order. Free text that can carry phone numbers
(description, SEO text) is blanked and long digit runs in titles are masked, so the
coordinates are rounded to ~100 m, so the committed fixture holds no personal data."""

import csv
import re
import sys
from collections import Counter
from pathlib import Path

from core.text import to_ascii_digits

OUTPUT = Path(__file__).with_name("listings_sample.csv")
BLANKED_COLUMNS = ("description", "seo_description", "seo_title", "subtitle")
KEEP_FIRST_URL_COLUMNS = ("image_urls", "thumbnail_urls")
COORDINATE_COLUMNS = ("latitude", "longitude")
COORDINATE_DECIMALS = 3  # ~100 m: enough for city-distance tests, not an address
TRIM_COLUMN = "برند و مدل"
LONG_DIGIT_RUN = re.compile(r"\d{7,}")
LIGHT_TRIMS_KEPT = 14
QUOTAS = {"light": 420, "motorcycles": 120, "heavy": 60, "rental": 8, "classic": 9}


def _segment(row: dict[str, str]) -> str:
    return row["webengage_cat_3"] or row["webengage_cat_2"]


def _scrub(row: dict[str, str]) -> dict[str, str]:
    for column in BLANKED_COLUMNS:
        row[column] = ""
    for column in KEEP_FIRST_URL_COLUMNS:
        row[column] = row[column].split(" | ")[0]
    for column in COORDINATE_COLUMNS:
        if row[column]:
            row[column] = str(round(float(row[column]), COORDINATE_DECIMALS))
    row["title"] = (
        LONG_DIGIT_RUN.sub("", to_ascii_digits(row["title"])).strip() or "آگهی"
    )
    return row


def build(source: Path) -> Counter[str]:
    csv.field_size_limit(sys.maxsize)
    with source.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows = sorted(reader, key=lambda row: row["token"])
    trims = Counter(row[TRIM_COLUMN] for row in rows if _segment(row) == "light")
    popular = {trim for trim, _ in trims.most_common(LIGHT_TRIMS_KEPT)}
    taken: Counter[str] = Counter()
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            segment = _segment(row)
            if segment == "light" and row[TRIM_COLUMN] not in popular:
                continue
            if taken[segment] < QUOTAS.get(segment, 0):
                taken[segment] += 1
                writer.writerow(_scrub(row))
    return taken


if __name__ == "__main__":
    print(dict(build(Path(sys.argv[1]))), "→", OUTPUT)
```

Run: `uv run python -m tests.fixtures.make_fixture ../assets/divar-vehicles-sep-17-20_32.csv`
Expected: `{'motorcycles': 120, 'heavy': 60, 'light': 420, 'rental': 8, 'classic': 9}` and a ~0.5 MB `tests/fixtures/listings_sample.csv` with 617 rows.

If `assets/divar-vehicles-sep-17-20_32.csv` is missing (it is gitignored), **stop and ask
the user for it** — do not invent fixture data.

Verify nothing personal is left:

```bash
uv run python - <<'EOF'
import csv, re, sys
csv.field_size_limit(sys.maxsize)
rows = list(csv.DictReader(open("tests/fixtures/listings_sample.csv", encoding="utf-8")))
assert len(rows) == 617, len(rows)
assert all(not row["description"] and not row["seo_description"] for row in rows)
text_columns = [c for c in rows[0] if c not in ("latitude", "longitude", "fetched_at")]
assert not any(re.search(r"09\d{9}", row[c]) for row in rows for c in text_columns)
print("fixture ok")
EOF
```

Expected: `fixture ok`.

- [ ] **Step 2: Write the failing tests**

`backend/tests/support.py`:

```python
"""Test doubles shared across the suite."""

from typing import Any


class DictCache:
    """In-memory stand-in for core.cache.Cache (same public methods)."""

    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.data_version = 0
        self.reads = 0

    async def get_json(self, key: str) -> Any | None:
        self.reads += 1
        return self.values.get(key)

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        self.values[key] = value

    async def get_data_version(self) -> int:
        return self.data_version

    async def bump_data_version(self) -> int:
        self.data_version += 1
        return self.data_version

    async def ping(self) -> bool:
        return True
```

Add to `backend/tests/conftest.py` — these imports:

```python
from ingest.pipeline import IngestPipeline
from repositories.catalog_repository import CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import ListingRepository
from tests.support import DictCache
```

below `BACKEND_ROOT`:

```python
FIXTURE_CSV = BACKEND_ROOT / "tests" / "fixtures" / "listings_sample.csv"
```

and these fixtures:

```python
@pytest.fixture
def cache() -> DictCache:
    return DictCache()


@pytest.fixture
async def seeded_session(session: AsyncSession, cache: DictCache) -> AsyncSession:
    """The ~600-row fixture CSV loaded through the real ingest pipeline."""
    pipeline = IngestPipeline(
        CityRepository(session),
        CatalogRepository(session),
        ListingRepository(session),
        cache,
    )
    await pipeline.run(FIXTURE_CSV)
    return session
```

`backend/tests/core/test_cache.py`:

```python
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from core.cache import DATA_VERSION_KEY, Cache


class FakeRedis:
    def __init__(self, *, down: bool = False) -> None:
        self.store: dict[str, str] = {}
        self.down = down

    def _check(self) -> None:
        if self.down:
            raise RedisConnectionError("redis is down")

    async def get(self, key: str) -> str | None:
        self._check()
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int) -> None:
        self._check()
        self.store[key] = value

    async def incr(self, key: str) -> int:
        self._check()
        self.store[key] = str(int(self.store.get(key, "0")) + 1)
        return int(self.store[key])

    async def ping(self) -> bool:
        self._check()
        return True


async def test_json_round_trip_keeps_persian_text() -> None:
    cache = Cache(FakeRedis())
    await cache.set_json("key", {"chips": ["پژو ۲۰۶"]}, ttl_seconds=60)
    assert await cache.get_json("key") == {"chips": ["پژو ۲۰۶"]}
    assert await cache.get_json("missing") is None


async def test_data_version_starts_at_zero_and_increments() -> None:
    redis = FakeRedis()
    cache = Cache(redis)
    assert await cache.get_data_version() == 0
    assert await cache.bump_data_version() == 1
    assert redis.store[DATA_VERSION_KEY] == "1"


async def test_an_outage_reads_as_a_miss_and_never_raises() -> None:
    cache = Cache(FakeRedis(down=True))
    assert await cache.get_json("key") is None
    await cache.set_json("key", {"a": 1}, ttl_seconds=60)
    assert await cache.get_data_version() == 0
    assert await cache.ping() is False


async def test_bumping_the_version_during_an_outage_fails_loudly() -> None:
    with pytest.raises(RedisConnectionError):
        await Cache(FakeRedis(down=True)).bump_data_version()
```

`backend/tests/repositories/test_repositories.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from enums import Category
from repositories.catalog_repository import CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import CandidateFilter, ListingRepository

pytestmark = pytest.mark.db
MILLION = 1_000_000


async def test_ingest_is_idempotent_and_fills_every_table(
    seeded_session: AsyncSession,
) -> None:
    listings = ListingRepository(seeded_session)
    assert await listings.count() == 617
    counts = await listings.count_by_category()
    assert counts[Category.LIGHT] == 420 and counts[Category.MOTORCYCLE] == 120
    tehran = (await CityRepository(seeded_session).find_by_names(["تهران"]))[0]
    assert 35.4 < tehran.lat < 36.0 and 51.0 < tehran.lng < 51.8  # median centroid
    assert tehran.listing_count > 50


@pytest.mark.parametrize(
    ("query", "brand", "model"),
    [
        ("206", "پژو", "پژو 206"),
        ("پژو 206 تیپ 2", "پژو", "پژو 206"),
        ("پژو 206 تیب 2", "پژو", "پژو 206"),  # typo still resolves
        ("پراید", "پراید", "پراید صندوق دار"),  # «صندوق‌دار» stays one word
        ("سمند", "سمند", "سمند lx"),
    ],
)
async def test_catalog_search_finds_the_vehicle(
    seeded_session: AsyncSession, query: str, brand: str, model: str
) -> None:
    matches = await CatalogRepository(seeded_session).search(query, None, 0.6, 1)
    assert (matches[0].brand, matches[0].model) == (brand, model)


async def test_catalog_search_returns_nothing_for_an_unknown_vehicle(
    seeded_session: AsyncSession,
) -> None:
    assert await CatalogRepository(seeded_session).search("بوگاتی", None, 0.6, 1) == []


async def test_candidates_respect_brand_and_guard_rails(
    seeded_session: AsyncSession,
) -> None:
    filters = CandidateFilter(
        brands=("پژو",),
        price_ceiling=1_000 * MILLION,
        year_floor=1393,
        year_ceiling=1403,
    )
    candidates = await ListingRepository(seeded_session).find_candidates(filters, 5_000)
    assert candidates
    assert {candidate.brand for candidate in candidates} == {"پژو"}
    assert all(c.price is None or c.price <= 1_000 * MILLION for c in candidates)
    assert all(c.year is None or 1393 <= c.year <= 1403 for c in candidates)
    assert all(c.lat is not None for c in candidates)  # falls back to the centroid


async def test_text_candidates_carry_a_similarity_score(
    seeded_session: AsyncSession,
) -> None:
    filters = CandidateFilter(category=Category.HEAVY, text="کامیون")
    candidates = await ListingRepository(seeded_session).find_candidates(filters, 50)
    assert candidates and all(c.text_similarity >= 0.3 for c in candidates)


async def test_suspect_prices_are_hidden_from_candidates(
    seeded_session: AsyncSession,
) -> None:
    repository = ListingRepository(seeded_session)
    everything = await repository.find_candidates(CandidateFilter(), 5_000)
    hidden = sum(candidate.price is None for candidate in everything)
    cheap_only = CandidateFilter(price_ceiling=50 * MILLION, category=Category.LIGHT)
    cheap = await repository.find_candidates(cheap_only, 5_000)
    assert hidden > 0
    assert all(c.price is None or c.price <= 50 * MILLION for c in cheap)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/core/test_cache.py tests/repositories -q`
Expected: `ModuleNotFoundError: No module named 'ingest.pipeline'` (from `conftest.py`).

- [ ] **Step 4: Implement the cache and the repositories**

`backend/core/cache.py`:

```python
"""Thin async Redis wrapper. The cache is an optimisation, never a dependency:
when Redis is unreachable every method logs a WARNING and behaves like a miss, so
search keeps working uncached (spec §7.5). This is the one deliberate place where a
connection error is not re-raised."""

import json
import logging
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

DATA_VERSION_KEY = "search:data_version"


class Cache:
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def get_json(self, key: str) -> Any | None:
        try:
            raw = await self._client.get(key)
        except RedisError as error:
            logger.warning("cache read failed", extra={"fields": {"error": str(error)}})
            return None
        return None if raw is None else json.loads(raw)

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        try:
            await self._client.set(key, json.dumps(value), ex=ttl_seconds)
        except RedisError as error:
            logger.warning(
                "cache write failed", extra={"fields": {"error": str(error)}}
            )

    async def get_data_version(self) -> int:
        try:
            raw = await self._client.get(DATA_VERSION_KEY)
        except RedisError as error:
            logger.warning("cache read failed", extra={"fields": {"error": str(error)}})
            return 0
        return int(raw) if raw is not None else 0

    async def bump_data_version(self) -> int:
        """Invalidates every search and facet key at once. Raises on failure: a
        re-ingest that cannot invalidate the cache must not look successful."""
        return int(await self._client.incr(DATA_VERSION_KEY))

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except RedisError:
            return False

    async def close(self) -> None:
        await self._client.aclose()
```

`backend/repositories/city_repository.py`:

```python
import uuid
from collections.abc import Collection, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.text import normalize_persian
from models.city import City
from models.listing import Listing

MEDIAN = 0.5


class CityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_names(self, names: Collection[str]) -> dict[str, uuid.UUID]:
        if names:
            rows = [
                {"name": name, "name_normalized": normalize_persian(name)}
                for name in sorted(names)
            ]
            statement = insert(City).values(rows)
            await self._session.execute(
                statement.on_conflict_do_nothing(index_elements=[City.name])
            )
        found = await self._session.execute(select(City.name, City.id))
        return {name: city_id for name, city_id in found}

    async def refresh_statistics(self) -> None:
        """Centroid = median of the city's listing coordinates (no gazetteer)."""
        per_city = (
            select(
                Listing.city_id.label("city_id"),
                func.percentile_cont(MEDIAN).within_group(Listing.lat).label("lat"),
                func.percentile_cont(MEDIAN).within_group(Listing.lng).label("lng"),
                func.count().label("listing_count"),
            )
            .group_by(Listing.city_id)
            .subquery()
        )
        await self._session.execute(
            update(City)
            .where(City.id == per_city.c.city_id)
            .values(
                lat=per_city.c.lat,
                lng=per_city.c.lng,
                listing_count=per_city.c.listing_count,
            )
        )

    async def find_by_names(self, names: Sequence[str]) -> list[City]:
        normalized = [normalize_persian(name) for name in names]
        found = await self._session.scalars(
            select(City).where(City.name_normalized.in_(normalized))
        )
        return list(found)

    async def list_names(self) -> list[str]:
        found = await self._session.scalars(
            select(City.name).order_by(City.listing_count.desc())
        )
        return list(found)

    async def list_top(self, limit: int) -> list[City]:
        found = await self._session.scalars(
            select(City).order_by(City.listing_count.desc(), City.name).limit(limit)
        )
        return list(found)
```

`backend/repositories/catalog_repository.py`:

```python
import uuid
from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.text import normalize_persian
from enums import Category
from models.listing import Listing
from models.vehicle_catalog import VehicleCatalog

type CatalogKey = tuple[Category, str]


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    category: Category
    brand: str
    model: str
    trim: str


@dataclass(frozen=True, slots=True)
class CatalogMatch:
    brand: str
    model: str
    trim: str
    score: float


@dataclass(frozen=True, slots=True)
class ModelCount:
    brand: str
    model: str
    listing_count: int


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_entries(
        self, entries: Collection[CatalogEntry]
    ) -> dict[CatalogKey, uuid.UUID]:
        if entries:
            rows = [
                {
                    "category": entry.category,
                    "brand": entry.brand,
                    "model": entry.model,
                    "trim": entry.trim,
                    "trim_normalized": normalize_persian(entry.trim),
                }
                for entry in sorted(entries, key=lambda entry: entry.trim)
            ]
            statement = insert(VehicleCatalog).values(rows)
            await self._session.execute(
                statement.on_conflict_do_nothing(
                    constraint="uq_vehicle_catalog_category_trim"
                )
            )
        found = await self._session.execute(
            select(VehicleCatalog.category, VehicleCatalog.trim, VehicleCatalog.id)
        )
        return {(category, trim): catalog_id for category, trim, catalog_id in found}

    async def refresh_counts(self) -> None:
        per_entry = (
            select(
                Listing.catalog_id.label("catalog_id"),
                func.count().label("listing_count"),
            )
            .where(Listing.catalog_id.is_not(None))
            .group_by(Listing.catalog_id)
            .subquery()
        )
        await self._session.execute(
            update(VehicleCatalog)
            .where(VehicleCatalog.id == per_entry.c.catalog_id)
            .values(listing_count=per_entry.c.listing_count)
        )

    async def search(
        self, query: str, category: Category | None, min_similarity: float, limit: int
    ) -> list[CatalogMatch]:
        """Best catalog rows for a normalised free-text mention. `word_similarity`
        (not `similarity`) because «206» is a substring of «پژو 206 تیپ 2»."""
        score = func.word_similarity(query, VehicleCatalog.trim_normalized)
        statement = (
            select(
                VehicleCatalog.brand,
                VehicleCatalog.model,
                VehicleCatalog.trim,
                score.label("score"),
            )
            .where(score >= min_similarity)
            .order_by(score.desc(), VehicleCatalog.listing_count.desc())
            .limit(limit)
        )
        if category is not None:
            statement = statement.where(VehicleCatalog.category == category)
        found = await self._session.execute(statement)
        return [CatalogMatch(*row) for row in found]

    async def list_top_models(
        self, category: Category | None, limit: int
    ) -> list[ModelCount]:
        total = func.sum(VehicleCatalog.listing_count)
        statement = (
            select(VehicleCatalog.brand, VehicleCatalog.model, total.label("total"))
            .group_by(VehicleCatalog.brand, VehicleCatalog.model)
            .order_by(total.desc(), VehicleCatalog.model)
            .limit(limit)
        )
        if category is not None:
            statement = statement.where(VehicleCatalog.category == category)
        found = await self._session.execute(statement)
        return [ModelCount(brand, model, int(count)) for brand, model, count in found]
```

`backend/repositories/listing_repository.py`:

```python
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, case, func, literal, null, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from enums import Category
from models.city import City
from models.listing import Listing
from models.vehicle_catalog import VehicleCatalog
from ranking.estimator import Estimate, EstimatorInput
from ranking.types import Candidate

# asyncpg allows 32,767 bind parameters per statement; a listing row has ~35 columns.
UPSERT_BATCH_SIZE = 500
CHEAP_DIFF_PCT = -5.0
MIN_TEXT_SIMILARITY = 0.3
_IMMUTABLE_COLUMNS = frozenset({"id", "token"})


@dataclass(frozen=True, slots=True)
class CandidateFilter:
    """Absolute bounds, already widened by the ranking tolerances (spec §7.3). A
    bound of None means the user did not state that criterion. NULL column values
    always pass: the ranker scores them as unknown."""

    category: Category | None = None
    brands: tuple[str, ...] = ()
    text: str | None = None
    only_below_market: bool = False
    price_floor: int | None = None
    price_ceiling: int | None = None
    km_ceiling: int | None = None
    year_floor: int | None = None
    year_ceiling: int | None = None
    exclude_id: uuid.UUID | None = None


def _within(
    column: Any, floor: int | None, ceiling: int | None
) -> list[ColumnElement[bool]]:
    bounds: list[ColumnElement[bool]] = []
    if floor is not None:
        bounds.append(column.is_(None) | (column >= floor))
    if ceiling is not None:
        bounds.append(column.is_(None) | (column <= ceiling))
    return bounds


class ListingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: Sequence[Mapping[str, Any]]) -> None:
        for start in range(0, len(rows), UPSERT_BATCH_SIZE):
            statement = insert(Listing).values(
                list(rows[start : start + UPSERT_BATCH_SIZE])
            )
            updatable = {
                name: statement.excluded[name]
                for name in rows[start]
                if name not in _IMMUTABLE_COLUMNS
            }
            await self._session.execute(
                statement.on_conflict_do_update(
                    index_elements=[Listing.token], set_=updatable
                )
            )

    async def load_estimator_inputs(self) -> list[EstimatorInput]:
        found = await self._session.execute(
            select(
                Listing.id,
                Listing.category,
                VehicleCatalog.trim,
                VehicleCatalog.model,
                Listing.year,
                Listing.km,
                Listing.price,
                Listing.insurance_months,
                Listing.body_condition,
            ).outerjoin(VehicleCatalog, Listing.catalog_id == VehicleCatalog.id)
        )
        return [EstimatorInput(*row) for row in found]

    async def apply_estimates(self, estimates: Sequence[Estimate]) -> None:
        rows = [{"id": row.pop("listing_id"), **row} for row in map(asdict, estimates)]
        for start in range(0, len(rows), UPSERT_BATCH_SIZE):
            await self._session.execute(
                update(Listing), rows[start : start + UPSERT_BATCH_SIZE]
            )

    async def newest_fetched_at(self) -> datetime | None:
        return await self._session.scalar(select(func.max(Listing.fetched_at)))

    async def count(self) -> int:
        return (
            await self._session.scalar(select(func.count()).select_from(Listing)) or 0
        )

    async def count_by_category(self) -> dict[Category, int]:
        found = await self._session.execute(
            select(Listing.category, func.count()).group_by(Listing.category)
        )
        return {category: total for category, total in found}

    async def get_by_id(self, listing_id: uuid.UUID) -> Listing | None:
        found = await self.get_by_ids([listing_id])
        return found[0] if found else None

    async def get_by_ids(self, listing_ids: Sequence[uuid.UUID]) -> list[Listing]:
        found = await self._session.scalars(
            select(Listing)
            .options(joinedload(Listing.city), joinedload(Listing.catalog))
            .where(Listing.id.in_(listing_ids))
        )
        by_id = {listing.id: listing for listing in found}
        return [by_id[listing_id] for listing_id in listing_ids if listing_id in by_id]

    async def find_candidates(
        self, filters: CandidateFilter, limit: int
    ) -> list[Candidate]:
        statement = self._candidate_columns(filters.text)
        for condition in self._conditions(filters):
            statement = statement.where(condition)
        statement = statement.order_by(
            Listing.deal_score.desc().nulls_last(), Listing.id
        )
        found = await self._session.execute(statement.limit(limit))
        return [Candidate(*row) for row in found]

    @staticmethod
    def _candidate_columns(text: str | None) -> Select[Any]:
        similarity = (
            func.word_similarity(literal(text), Listing.title_normalized)
            if text
            else null()
        )
        # A suspect price is hidden from the ranker: a deposit never "fits the budget".
        trusted_price = case((Listing.price_suspect, null()), else_=Listing.price)
        return (
            select(
                Listing.id,
                VehicleCatalog.brand,
                VehicleCatalog.model,
                VehicleCatalog.trim,
                Listing.year,
                Listing.km,
                trusted_price.label("price"),
                City.name.label("city"),
                func.coalesce(Listing.lat, City.lat).label("lat"),
                func.coalesce(Listing.lng, City.lng).label("lng"),
                Listing.gearbox,
                Listing.fuel,
                Listing.color,
                similarity.label("text_similarity"),
                Listing.deal_score,
                Listing.posted_at,
            )
            .join(City, Listing.city_id == City.id)
            .outerjoin(VehicleCatalog, Listing.catalog_id == VehicleCatalog.id)
        )

    @staticmethod
    def _conditions(filters: CandidateFilter) -> list[ColumnElement[bool]]:
        trusted_price = case((Listing.price_suspect, null()), else_=Listing.price)
        conditions = [
            *_within(trusted_price, filters.price_floor, filters.price_ceiling),
            *_within(Listing.km, None, filters.km_ceiling),
            *_within(Listing.year, filters.year_floor, filters.year_ceiling),
        ]
        if filters.category is not None:
            conditions.append(Listing.category == filters.category)
        if filters.brands:
            conditions.append(VehicleCatalog.brand.in_(filters.brands))
        elif filters.text:
            similarity = func.word_similarity(
                literal(filters.text), Listing.title_normalized
            )
            conditions.append(similarity >= MIN_TEXT_SIMILARITY)
        if filters.only_below_market:
            conditions.append(Listing.diff_pct <= CHEAP_DIFF_PCT)
        if filters.exclude_id is not None:
            conditions.append(Listing.id != filters.exclude_id)
        return conditions
```

- [ ] **Step 5: Implement the report and the pipeline**

`backend/ingest/report.py`:

```python
from collections import Counter
from dataclasses import dataclass, field

MAX_REJECT_RATIO = 0.01


@dataclass(slots=True)
class IngestReport:
    rows_read: int = 0
    rows_upserted: int = 0
    rejected: Counter[str] = field(default_factory=Counter)
    nulled: Counter[str] = field(default_factory=Counter)
    estimate_basis: Counter[str] = field(default_factory=Counter)
    price_suspect: int = 0
    data_version: int = 0

    @property
    def rows_rejected(self) -> int:
        return sum(self.rejected.values())

    @property
    def too_many_rejects(self) -> bool:
        return (
            self.rows_read > 0
            and self.rows_rejected / self.rows_read > MAX_REJECT_RATIO
        )

    def render(self) -> str:
        lines = [
            f"rows read      {self.rows_read}",
            f"rows upserted  {self.rows_upserted}",
            f"rows rejected  {self.rows_rejected} {dict(self.rejected)}",
            f"fields nulled  {dict(self.nulled)}",
            f"estimate basis {dict(self.estimate_basis)}",
            f"price suspect  {self.price_suspect}",
            f"data version   {self.data_version}",
        ]
        return "\n".join(lines)
```

`backend/ingest/pipeline.py`:

```python
"""CSV → normalised rows → upsert → estimates → cache invalidation (spec §6.4).
Idempotent: re-running with the same file changes nothing."""

import csv
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from core.cache import Cache
from core.text import jalali_year
from errors import IngestError
from ingest.report import IngestReport
from ingest.row_mapper import MappedRow, NormalizedListing, RowRejectedError, map_row
from ranking.estimator import PriceEstimator
from repositories.catalog_repository import CatalogEntry, CatalogKey, CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import ListingRepository

CSV_ENCODING = "utf-8"
_CATALOG_FIELDS = {"trim", "brand", "model", "city"}


def _read_rows(csv_path: Path) -> Iterator[dict[str, str]]:
    csv.field_size_limit(sys.maxsize)  # descriptions exceed the 128 KB default
    with csv_path.open(encoding=CSV_ENCODING, newline="") as handle:
        yield from csv.DictReader(handle)


def _catalog_key(listing: NormalizedListing) -> CatalogKey | None:
    return (listing.category, listing.trim) if listing.trim else None


class IngestPipeline:
    def __init__(
        self,
        cities: CityRepository,
        catalog: CatalogRepository,
        listings: ListingRepository,
        cache: Cache,
    ) -> None:
        self._cities = cities
        self._catalog = catalog
        self._listings = listings
        self._cache = cache

    async def run(self, csv_path: Path) -> IngestReport:
        report = IngestReport()
        mapped = self._map_rows(csv_path, report)
        if report.too_many_rejects:
            raise IngestError(
                "Too many rejected rows", {"rejected": dict(report.rejected)}
            )
        await self._upsert(mapped, report)
        await self._cities.refresh_statistics()
        await self._catalog.refresh_counts()
        await self._estimate(report)
        report.data_version = await self._cache.bump_data_version()
        return report

    @staticmethod
    def _map_rows(csv_path: Path, report: IngestReport) -> list[MappedRow]:
        mapped: list[MappedRow] = []
        for row in _read_rows(csv_path):
            report.rows_read += 1
            try:
                mapped_row = map_row(row)
            except RowRejectedError as rejected:
                report.rejected[rejected.reason] += 1
                continue
            report.nulled.update(mapped_row.nulled)
            mapped.append(mapped_row)
        return mapped

    async def _upsert(self, mapped: list[MappedRow], report: IngestReport) -> None:
        listings = [row.listing for row in mapped]
        city_ids = await self._cities.upsert_names(
            {listing.city for listing in listings}
        )
        entries = {
            CatalogEntry(listing.category, listing.brand, listing.model, listing.trim)
            for listing in listings
            if listing.trim and listing.brand and listing.model
        }
        catalog_ids = await self._catalog.upsert_entries(entries)
        rows = [self._to_row(listing, city_ids, catalog_ids) for listing in listings]
        await self._listings.upsert_many(rows)
        report.rows_upserted = len(rows)

    @staticmethod
    def _to_row(
        listing: NormalizedListing,
        city_ids: dict[str, Any],
        catalog_ids: dict[CatalogKey, Any],
    ) -> dict[str, Any]:
        row = listing.model_dump(exclude=_CATALOG_FIELDS)
        row["city_id"] = city_ids[listing.city]
        key = _catalog_key(listing)
        row["catalog_id"] = catalog_ids.get(key) if key else None
        return row

    async def _estimate(self, report: IngestReport) -> None:
        newest = await self._listings.newest_fetched_at()
        if newest is None:
            return
        inputs = await self._listings.load_estimator_inputs()
        estimates = PriceEstimator(inputs, jalali_year(newest.date())).estimate_all()
        await self._listings.apply_estimates(estimates)
        report.estimate_basis.update(estimate.est_basis.value for estimate in estimates)
        report.price_suspect = sum(estimate.price_suspect for estimate in estimates)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run black --check .`
Expected: `121 passed`.

- [ ] **Step 7: Commit**

```bash
cd .. && git add backend/core/cache.py backend/repositories backend/ingest backend/tests
git commit -m "feat(ingest): add repositories, Redis cache wrapper and idempotent ingest pipeline

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Search schemas, chips and intent resolver

**Files:**
- Create: `backend/schemas/__init__.py`, `backend/schemas/listing.py`, `backend/schemas/search.py`, `backend/schemas/facets.py`, `backend/services/__init__.py`, `backend/services/intent_chips.py`, `backend/services/intent_resolver.py`
- Test: `backend/tests/services/__init__.py`, `backend/tests/services/test_intent_resolver.py`

**Interfaces:**
- Consumes: `CatalogRepository.search`, `CityRepository.find_by_names`, `CandidateFilter`, `ranking.types`, `ranking.weights`, `ranking.labels`.
- Produces: `schemas.search.VehicleMention(brand, model, trim)`, `SearchIntent` (validated), `SearchOverrides.apply_to(intent) -> SearchIntent`, `SearchParams(SearchOverrides)` with `q`, `page`, `page_size`, `IntentRead(SearchIntent)` with `chips`, `SearchResponse`; constants `MAX_QUERY_LENGTH = 300`, `MAX_PAGE_SIZE = 50`, `DEFAULT_PAGE_SIZE = 20`; `schemas.listing.ListingCard`, `PriceBreakdown`, `ListingDetail`; `schemas.facets.Facets`, `ModelFacet`, `FacetCount`; `services.intent_chips.build_chips(intent, targets, text) -> tuple[str, ...]`; `services.intent_resolver.IntentResolver(catalog, cities, weights=DEFAULT_WEIGHTS).resolve(intent) -> ResolvedIntent(query: RankingQuery, filters: CandidateFilter, chips)`; pure helpers `mention_queries(mention) -> list[str]` and `infer_level(query, match) -> MentionLevel`.

Why `mention_queries` retries without the brand: measured on Postgres 18,
`word_similarity('سایپا پراید', 'پراید 131 se')` is 0.5 — under the 0.6 threshold —
while `word_similarity('پراید', …)` is 1.0.

- [ ] **Step 1: Write the failing tests**

Create empty `backend/schemas/__init__.py`, `backend/services/__init__.py`, `backend/tests/services/__init__.py`.

`backend/tests/services/test_intent_resolver.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from enums import MentionLevel
from repositories.catalog_repository import CatalogMatch, CatalogRepository
from repositories.city_repository import CityRepository
from schemas.search import SearchIntent, VehicleMention
from services.intent_resolver import IntentResolver, infer_level, mention_queries

MATCH = CatalogMatch("پژو", "پژو 206", "پژو 206 تیپ ۲", 1.0)
MILLION = 1_000_000


@pytest.mark.parametrize(
    ("query", "level"),
    [
        ("پژو", MentionLevel.BRAND),
        ("206", MentionLevel.MODEL),
        ("پژو 206", MentionLevel.MODEL),
        ("206 تیپ 2", MentionLevel.TRIM),
        ("پژو 206 تیب 2", MentionLevel.TRIM),
    ],
)
def test_infer_level_follows_the_words_the_user_used(
    query: str, level: MentionLevel
) -> None:
    assert infer_level(query, MATCH) is level


def test_mention_queries_retry_without_the_brand() -> None:
    mention = VehicleMention(brand="سایپا", model="پراید")
    assert mention_queries(mention) == ["سایپا پراید", "پراید"]
    assert mention_queries(VehicleMention(brand="پژو", model="پژو ۲۰۶")) == ["پژو 206"]
    assert mention_queries(VehicleMention()) == []


@pytest.mark.db
async def test_resolve_builds_targets_cities_guard_rails_and_chips(
    seeded_session: AsyncSession,
) -> None:
    resolver = IntentResolver(
        CatalogRepository(seeded_session), CityRepository(seeded_session)
    )
    intent = SearchIntent(
        vehicles=[VehicleMention(brand="پژو", model="۲۰۶")],
        year_min=1398,
        year_max=1398,
        price_max=800 * MILLION,
        cities=["تهران"],
    )
    resolved = await resolver.resolve(intent)
    (target,) = resolved.query.targets
    assert (target.level, target.brand, target.model) == (
        MentionLevel.MODEL,
        "پژو",
        "پژو 206",
    )
    assert resolved.query.cities[0].name == "تهران"
    assert resolved.filters.brands == ("پژو",)
    assert resolved.filters.price_ceiling == 1_000 * MILLION
    assert (resolved.filters.year_floor, resolved.filters.year_ceiling) == (1393, 1403)
    assert resolved.chips == ("پژو 206", "مدل ۱۳۹۸", "زیر ۸۰۰ میلیون", "تهران")


@pytest.mark.db
async def test_unknown_vehicle_becomes_title_text(seeded_session: AsyncSession) -> None:
    resolver = IntentResolver(
        CatalogRepository(seeded_session), CityRepository(seeded_session)
    )
    intent = SearchIntent(vehicles=[VehicleMention(model="کامیون بنز")])
    resolved = await resolver.resolve(intent)
    assert resolved.query.targets == ()
    assert resolved.filters.text == "کامیون بنز" and resolved.query.has_text is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/services -q`
Expected: `ModuleNotFoundError: No module named 'schemas.search'`.

- [ ] **Step 3: Implement the schemas**

`backend/schemas/listing.py`:

```python
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from enums import Category, EstimateBasis, Fuel, Gearbox, Verdict


class ListingCard(BaseModel):
    id: uuid.UUID
    token: str
    title: str
    category: Category
    brand: str | None
    model: str | None
    trim: str | None
    year: int | None
    km: int | None
    price: int | None
    city: str
    district: str | None
    thumbnail_url: str | None
    posted_at: datetime | None
    est_price: int | None
    diff_pct: float | None
    deal_score: int | None
    verdict: Verdict
    match_score: float | None = None
    is_exact: bool = True
    near_miss_labels: list[str] = []


class PriceBreakdown(BaseModel):
    base: int | None
    km_adjustment: int | None
    insurance_adjustment: int | None
    est_basis: EstimateBasis
    est_sample_size: int


class ListingDetail(ListingCard):
    url: str
    description: str
    image_urls: list[str]
    lat: float | None
    lng: float | None
    gearbox: Gearbox | None
    fuel: Fuel | None
    color: str | None
    insurance_months: int | None
    is_dealer: bool
    attributes: dict[str, Any]
    price_breakdown: PriceBreakdown
```

`backend/schemas/search.py`:

```python
from datetime import date
from typing import Self

from pydantic import BaseModel, Field, PositiveInt, model_validator

from core.text import jalali_year
from enums import Category, Fuel, Gearbox, ParsedBy, SortKey
from schemas.listing import ListingCard

MIN_SEARCH_YEAR = 1340
MAX_QUERY_LENGTH = 300
MAX_PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 20


class VehicleMention(BaseModel):
    """A vehicle as the user wrote it — free text the resolver maps to the catalog."""

    brand: str | None = None
    model: str | None = None
    trim: str | None = None


class SearchIntent(BaseModel):
    """Everything a search can ask for. The LLM, the rules parser and the filter sheet
    all produce this one type, so there is exactly one ranking path."""

    category: Category | None = None
    vehicles: list[VehicleMention] = Field(default_factory=list)
    year_min: int | None = None
    year_max: int | None = None
    price_min: PositiveInt | None = Field(default=None, description="toman")
    price_max: PositiveInt | None = Field(default=None, description="toman")
    km_max: PositiveInt | None = None
    cities: list[str] = Field(default_factory=list)
    gearbox: Gearbox | None = None
    fuel: Fuel | None = None
    colors: list[str] = Field(default_factory=list)
    only_below_market: bool = False
    text: str | None = Field(default=None, description="anything not captured above")
    sort: SortKey = SortKey.RELEVANCE

    @model_validator(mode="after")
    def _check_ranges(self) -> Self:
        newest_year = jalali_year(date.today()) + 1
        for year in (self.year_min, self.year_max):
            if year is not None and not MIN_SEARCH_YEAR <= year <= newest_year:
                raise ValueError(f"year must be a Jalali year up to {newest_year}")
        if self.year_min and self.year_max and self.year_min > self.year_max:
            raise ValueError("year_min must not exceed year_max")
        if self.price_min and self.price_max and self.price_min > self.price_max:
            raise ValueError("price_min must not exceed price_max")
        return self


class SearchOverrides(BaseModel):
    """Explicit filter-sheet parameters. Whatever is set here wins over what was
    parsed from the free-text query."""

    category: Category | None = None
    models: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    year: int | None = None
    price_max: PositiveInt | None = None
    km_max: PositiveInt | None = None
    gearbox: Gearbox | None = None
    only_below: bool | None = None
    sort: SortKey | None = None

    def apply_to(self, intent: SearchIntent) -> SearchIntent:
        changes: dict[str, object] = {
            "category": self.category,
            "cities": self.cities or None,
            "year_min": self.year,
            "year_max": self.year,
            "price_max": self.price_max,
            "km_max": self.km_max,
            "gearbox": self.gearbox,
            "only_below_market": self.only_below,
            "sort": self.sort,
        }
        if self.models:
            changes["vehicles"] = [VehicleMention(model=name) for name in self.models]
        stated = {name: value for name, value in changes.items() if value is not None}
        return SearchIntent.model_validate({**intent.model_dump(), **stated})


class SearchParams(SearchOverrides):
    """Every query parameter of GET /search as ONE model. FastAPI cannot mix a
    query-parameter model with individual `Query()` parameters."""

    q: str | None = Field(default=None, max_length=MAX_QUERY_LENGTH)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class IntentRead(SearchIntent):
    chips: list[str]


class SearchResponse(BaseModel):
    intent: IntentRead
    parsed_by: ParsedBy
    total: int
    exact_count: int
    page: int
    page_size: int
    items: list[ListingCard]
```

`backend/schemas/facets.py`:

```python
from pydantic import BaseModel

from enums import Category


class FacetCount(BaseModel):
    value: str
    count: int


class ModelFacet(BaseModel):
    brand: str
    model: str
    count: int


class Facets(BaseModel):
    categories: dict[Category, int]
    models: list[ModelFacet]
    cities: list[FacetCount]
```

- [ ] **Step 4: Implement chips and the resolver**

`backend/services/intent_chips.py`:

```python
"""The parsed intent echoed back as short Persian chips, so the user sees what the
search understood."""

from core.text import to_persian_digits
from enums import MentionLevel
from ranking import labels
from ranking.types import VehicleTarget
from schemas.search import SearchIntent

KM_PER_THOUSAND = 1_000
ONLY_BELOW_MARKET = "فقط ارزان‌تر از بازار"


def _target_chip(target: VehicleTarget) -> str:
    if target.level is MentionLevel.TRIM and target.trim:
        return target.trim
    if target.level is MentionLevel.MODEL and target.model:
        return target.model
    return target.brand


def _year_chip(intent: SearchIntent) -> str | None:
    low, high = intent.year_min, intent.year_max
    if low and high:
        years = to_persian_digits(low)
        return (
            f"مدل {years}" if low == high else f"{years} تا {to_persian_digits(high)}"
        )
    if low:
        return f"از {to_persian_digits(low)}"
    return f"تا {to_persian_digits(high)}" if high else None


def build_chips(
    intent: SearchIntent, targets: tuple[VehicleTarget, ...], text: str | None
) -> tuple[str, ...]:
    chips: list[str | None] = [_target_chip(target) for target in targets]
    chips.append(_year_chip(intent))
    if intent.price_min:
        chips.append(f"از {labels.format_toman(intent.price_min)}")
    if intent.price_max:
        chips.append(f"زیر {labels.format_toman(intent.price_max)}")
    if intent.km_max:
        thousands = to_persian_digits(round(intent.km_max / KM_PER_THOUSAND))
        chips.append(f"کارکرد زیر {thousands} هزار")
    chips.extend(intent.cities)
    if intent.gearbox:
        chips.append(labels.GEARBOX_NAMES[intent.gearbox])
    if intent.fuel:
        chips.append(labels.FUEL_NAMES[intent.fuel])
    chips.extend(intent.colors)
    if intent.only_below_market:
        chips.append(ONLY_BELOW_MARKET)
    if text:
        chips.append(f"«{text}»")
    return tuple(chip for chip in chips if chip)
```

`backend/services/intent_resolver.py`:

```python
"""Stage 1 of search (spec §7.2): turn a SearchIntent's free-text mentions and city
names into catalog targets, city centroids and SQL guard rails."""

from dataclasses import dataclass

from core.text import normalize_persian
from enums import MentionLevel
from ranking.types import RankingQuery, ResolvedCity, VehicleTarget
from ranking.weights import DEFAULT_WEIGHTS, RankingWeights
from repositories.catalog_repository import CatalogMatch, CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import CandidateFilter
from schemas.search import SearchIntent, VehicleMention
from services.intent_chips import build_chips

MIN_CATALOG_SIMILARITY = 0.6
CATALOG_MATCH_LIMIT = 1


@dataclass(frozen=True, slots=True)
class ResolvedIntent:
    query: RankingQuery
    filters: CandidateFilter
    chips: tuple[str, ...]


def _unique_tokens(*parts: str | None) -> str:
    tokens = normalize_persian(" ".join(part for part in parts if part)).split()
    return " ".join(dict.fromkeys(tokens))


def mention_queries(mention: VehicleMention) -> list[str]:
    """Most specific first. The second form drops the brand because the LLM often
    supplies the manufacturer («سایپا پراید») while Divar's string starts at «پراید»."""
    full = _unique_tokens(mention.brand, mention.model, mention.trim)
    without_brand = _unique_tokens(mention.model, mention.trim)
    return [query for query in dict.fromkeys((full, without_brand)) if query]


def infer_level(query: str, match: CatalogMatch) -> MentionLevel:
    """How specific the user was, judged by which catalog words they used — not by
    which field the parser happened to put them in."""
    tokens = set(query.split())
    if tokens <= set(match.brand.split()):
        return MentionLevel.BRAND
    if tokens <= set(match.model.split()):
        return MentionLevel.MODEL
    return MentionLevel.TRIM


def _to_target(query: str, match: CatalogMatch) -> VehicleTarget:
    level = infer_level(query, match)
    model = match.model if level is not MentionLevel.BRAND else None
    trim = match.trim if level is MentionLevel.TRIM else None
    return VehicleTarget(level, match.brand, model, trim)


class IntentResolver:
    def __init__(
        self,
        catalog: CatalogRepository,
        cities: CityRepository,
        weights: RankingWeights = DEFAULT_WEIGHTS,
    ) -> None:
        self._catalog = catalog
        self._cities = cities
        self._weights = weights

    async def resolve(self, intent: SearchIntent) -> ResolvedIntent:
        targets, leftovers = await self._resolve_vehicles(intent)
        text = normalize_persian(" ".join([*leftovers, intent.text or ""])) or None
        cities = await self._resolve_cities(intent.cities)
        query = RankingQuery(
            targets=targets,
            year_min=intent.year_min,
            year_max=intent.year_max,
            price_min=intent.price_min,
            price_max=intent.price_max,
            km_max=intent.km_max,
            cities=cities,
            gearbox=intent.gearbox,
            fuel=intent.fuel,
            colors=tuple(intent.colors),
            has_text=text is not None,
            sort=intent.sort,
        )
        filters = self._guard_rails(intent, targets, text)
        return ResolvedIntent(query, filters, build_chips(intent, targets, text))

    async def _resolve_vehicles(
        self, intent: SearchIntent
    ) -> tuple[tuple[VehicleTarget, ...], list[str]]:
        targets: list[VehicleTarget] = []
        leftovers: list[str] = []
        for mention in intent.vehicles:
            target = await self._resolve_mention(mention, intent)
            if target is not None:
                targets.append(target)
            else:
                leftovers.extend(mention_queries(mention)[:1])
        return tuple(dict.fromkeys(targets)), leftovers

    async def _resolve_mention(
        self, mention: VehicleMention, intent: SearchIntent
    ) -> VehicleTarget | None:
        for query in mention_queries(mention):
            matches = await self._catalog.search(
                query, intent.category, MIN_CATALOG_SIMILARITY, CATALOG_MATCH_LIMIT
            )
            if matches:
                return _to_target(query, matches[0])
        return None

    async def _resolve_cities(self, names: list[str]) -> tuple[ResolvedCity, ...]:
        found = await self._cities.find_by_names(names) if names else []
        return tuple(ResolvedCity(city.name, city.lat, city.lng) for city in found)

    def _guard_rails(
        self, intent: SearchIntent, targets: tuple[VehicleTarget, ...], text: str | None
    ) -> CandidateFilter:
        weights = self._weights
        price_slack, km_slack = weights.price_tolerance, weights.km_tolerance
        return CandidateFilter(
            category=intent.category,
            brands=tuple(dict.fromkeys(target.brand for target in targets)),
            text=text,
            only_below_market=intent.only_below_market,
            price_floor=intent.price_min
            and round(intent.price_min * (1 - price_slack)),
            price_ceiling=intent.price_max
            and round(intent.price_max * (1 + price_slack)),
            km_ceiling=intent.km_max and round(intent.km_max * (1 + km_slack)),
            year_floor=intent.year_min and intent.year_min - weights.year_tolerance,
            year_ceiling=intent.year_max and intent.year_max + weights.year_tolerance,
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run black --check .`
Expected: `129 passed`.

- [ ] **Step 6: Commit**

```bash
cd .. && git add backend/schemas backend/services backend/tests/services
git commit -m "feat(search): add SearchIntent schemas and catalog/city intent resolver

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: LLM layer — rules parser, Pydantic AI agent, QueryParser

**Files:**
- Create: `backend/llm/__init__.py`, `backend/llm/rules_parser.py`, `backend/llm/eval_cases.py`, `backend/llm/model_factory.py`, `backend/llm/intent_agent.py`, `backend/llm/eval.py`, `backend/services/query_parser.py`
- Test: `backend/tests/llm/__init__.py`, `backend/tests/llm/test_rules_parser.py`, `backend/tests/llm/test_model_factory.py`, `backend/tests/llm/test_eval.py`, `backend/tests/services/test_query_parser.py`

**Interfaces:**
- Consumes: `schemas.search.SearchIntent`, `core.cache.Cache`, `CityRepository.list_names`, `core.config.Settings`.
- Produces: `llm.rules_parser.parse_with_rules(query: str, known_cities: Collection[str]) -> SearchIntent`; `llm.model_factory.build_model(settings) -> Model | None` (None when `LLM_API_KEY` is empty); `llm.intent_agent.build_intent_agent(model) -> Agent[None, SearchIntent]`, `build_instructions() -> str`; `llm.eval_cases.EVAL_CASES`; `services.query_parser.QueryParser(agent, cities, cache, timeout_seconds, cache_ttl_seconds).parse(text) -> ParsedQuery(intent, parsed_by)`; `PROMPT_VERSION` (bump it whenever the instructions change — it is part of the intent cache key).

- [ ] **Step 1: Write the failing tests**

Create empty `backend/llm/__init__.py`, `backend/tests/llm/__init__.py`.

`backend/llm/eval_cases.py`:

```python
"""Labelled queries shared by the rules-parser tests and the opt-in live LLM eval.
Each case lists only the fields that must match; vehicle text is checked loosely."""

from dataclasses import dataclass, field
from typing import Any

from enums import Gearbox

MILLION = 1_000_000
BILLION = 1_000_000_000


@dataclass(frozen=True, slots=True)
class EvalCase:
    query: str
    expected: dict[str, Any]
    vehicle_words: tuple[str, ...] = field(default=())


EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        "۲۰۶ مدل ۹۸ زیر ۸۰۰ میلیون تهران",
        {
            "year_min": 1398,
            "year_max": 1398,
            "price_max": 800 * MILLION,
            "cities": ["تهران"],
        },
        ("206",),
    ),
    EvalCase(
        "دنا پلاس اتومات زیر یک میلیارد کرج",
        {"price_max": BILLION, "cities": ["کرج"], "gearbox": Gearbox.AUTOMATIC},
        ("دنا", "پلاس"),
    ),
    EvalCase("پراید زیر 1.2", {"price_max": 1_200 * MILLION}, ("پراید",)),
    EvalCase(
        "پژو پارس کارکرد زیر ۵۰ هزار کیلومتر",
        {"km_max": 50_000, "price_max": None},
        ("پژو", "پارس"),
    ),
    EvalCase(
        "سمند کم کارکرد اصفهان", {"km_max": 90_000, "cities": ["اصفهان"]}, ("سمند",)
    ),
    EvalCase(
        "کوییک مدل 1402 دنده ای",
        {"year_min": 1402, "gearbox": Gearbox.MANUAL},
        ("کوییک",),
    ),
    EvalCase("تیبا مدل ۹۵ به بالا", {"year_min": 1395, "year_max": None}, ("تیبا",)),
    EvalCase(
        "ساینا ارزان مشهد", {"only_below_market": True, "cities": ["مشهد"]}, ("ساینا",)
    ),
    EvalCase("هوندا ۱۲۵ تا ۸۰ میلیون", {"price_max": 80 * MILLION}, ("هوندا",)),
    EvalCase("زیر ۵۰۰ میلیون شیراز", {"price_max": 500 * MILLION, "cities": ["شیراز"]}),
)
```

`backend/tests/llm/test_rules_parser.py`:

```python
import pytest

from llm.eval_cases import EVAL_CASES, EvalCase
from llm.rules_parser import parse_with_rules

KNOWN_CITIES = ("تهران", "کرج", "اصفهان", "مشهد", "شیراز", "اسلام‌شهر")


@pytest.mark.parametrize("case", EVAL_CASES, ids=[case.query for case in EVAL_CASES])
def test_rules_parser_extracts_the_labelled_fields(case: EvalCase) -> None:
    intent = parse_with_rules(case.query, KNOWN_CITIES)
    actual = {name: getattr(intent, name) for name in case.expected}
    assert actual == case.expected
    mention = " ".join(vehicle.model or "" for vehicle in intent.vehicles)
    assert all(word in mention for word in case.vehicle_words)


def test_recognised_clauses_never_leak_into_the_vehicle_mention() -> None:
    intent = parse_with_rules(
        "یه ۲۰۶ مدل ۹۸ زیر ۸۰۰ میلیون تو تهران میخوام", KNOWN_CITIES
    )
    assert [vehicle.model for vehicle in intent.vehicles] == ["206"]


def test_city_with_zwnj_is_matched_after_normalisation() -> None:
    assert parse_with_rules("پراید اسلام شهر", KNOWN_CITIES).cities == ["اسلام‌شهر"]


def test_empty_query_is_an_empty_intent() -> None:
    intent = parse_with_rules("   ", KNOWN_CITIES)
    assert intent.vehicles == [] and intent.price_max is None
```

`backend/tests/llm/test_model_factory.py`:

```python
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel

from core.config import Settings
from llm.model_factory import build_model


def settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_no_api_key_means_no_model() -> None:
    assert build_model(settings()) is None


def test_google_provider_builds_a_gemini_model() -> None:
    model = build_model(settings(llm_provider="google", llm_api_key="test-key"))
    assert isinstance(model, GoogleModel)
    assert model.model_name == "gemini-3.7-flash"


def test_openai_compatible_provider_uses_the_configured_base_url() -> None:
    model = build_model(
        settings(
            llm_provider="openai_compatible",
            llm_api_key="test-key",
            llm_model="openai/gpt-5-mini",
            llm_base_url="https://openrouter.ai/api/v1",
        )
    )
    assert isinstance(model, OpenAIChatModel)
    assert str(model.client.base_url).startswith("https://openrouter.ai/api/v1")
```

`backend/tests/llm/test_eval.py`:

```python
from llm.eval import score_case
from llm.eval_cases import EVAL_CASES
from schemas.search import SearchIntent, VehicleMention

CASE = EVAL_CASES[0]  # «۲۰۶ مدل ۹۸ زیر ۸۰۰ میلیون تهران»


def test_score_case_counts_correct_fields_and_names_the_wrong_ones() -> None:
    perfect = SearchIntent(
        vehicles=[VehicleMention(brand="پژو", model="۲۰۶")], **CASE.expected
    )
    assert score_case(CASE, perfect) == (5, 5, [])
    flawed = perfect.model_copy(update={"cities": [], "vehicles": []})
    assert score_case(CASE, flawed) == (3, 5, ["cities", "vehicles"])
```

`backend/tests/services/test_query_parser.py`:

```python
import asyncio

import pytest
from pydantic_ai import Agent, ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from enums import ParsedBy
from llm.intent_agent import build_instructions, build_intent_agent
from schemas.search import SearchIntent
from services.query_parser import QueryParser
from tests.support import DictCache

MILLION = 1_000_000
LLM_OUTPUT = {"cities": ["تهران"], "price_max": 800 * MILLION}


class StubCities:
    async def list_names(self) -> list[str]:
        return ["تهران", "کرج"]


def make_parser(
    agent: Agent | None, cache: DictCache, timeout: float = 1.0
) -> QueryParser:
    return QueryParser(agent, StubCities(), cache, timeout, cache_ttl_seconds=60)


def agent_returning(output: dict) -> Agent:
    return build_intent_agent(TestModel(custom_output_args=output))


async def test_llm_result_is_used_and_cached() -> None:
    cache = DictCache()
    parser = make_parser(agent_returning(LLM_OUTPUT), cache)
    first = await parser.parse("۲۰۶ زیر ۸۰۰ تهران")
    assert first.parsed_by is ParsedBy.LLM
    assert first.intent.price_max == 800 * MILLION
    offline = make_parser(None, cache)  # same cache, no LLM at all
    second = await offline.parse("  ۲۰۶ زیر ۸۰۰   تهران ")  # normalised → same key
    assert second.parsed_by is ParsedBy.LLM and second.intent == first.intent


async def test_without_an_agent_the_rules_parser_answers() -> None:
    parsed = await make_parser(None, DictCache()).parse("۲۰۶ زیر ۸۰۰ میلیون کرج")
    assert parsed.parsed_by is ParsedBy.RULES
    assert parsed.intent.cities == ["کرج"]


async def test_invalid_llm_output_falls_back_to_rules_and_is_not_cached() -> None:
    def always_invalid(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        bad = {"price_min": 900 * MILLION, "price_max": 100 * MILLION}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, bad)])

    cache = DictCache()
    parser = make_parser(build_intent_agent(FunctionModel(always_invalid)), cache)
    parsed = await parser.parse("۲۰۶ تهران")
    assert parsed.parsed_by is ParsedBy.RULES
    assert cache.values == {}


async def test_slow_llm_times_out_into_the_rules_parser() -> None:
    async def too_slow(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        await asyncio.sleep(5)
        raise AssertionError("unreachable")

    parser = make_parser(build_intent_agent(FunctionModel(too_slow)), DictCache(), 0.05)
    assert (await parser.parse("۲۰۶ تهران")).parsed_by is ParsedBy.RULES


async def test_empty_query_is_browse_mode_without_touching_the_llm() -> None:
    parsed = await make_parser(agent_returning(LLM_OUTPUT), DictCache()).parse("   ")
    assert parsed.intent == SearchIntent()


def test_instructions_state_the_current_jalali_year() -> None:
    assert "The current Jalali year is 14" in build_instructions()


@pytest.mark.parametrize("field", ["price_min", "year_min"])
def test_search_intent_rejects_inverted_ranges(field: str) -> None:
    other = field.replace("min", "max")
    values = {"price_min": 900, "price_max": 100, "year_min": 1400, "year_max": 1390}
    with pytest.raises(ValueError, match="must not exceed"):
        SearchIntent(**{field: values[field], other: values[other]})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/llm tests/services/test_query_parser.py -q`
Expected: `ModuleNotFoundError: No module named 'llm.rules_parser'`.

- [ ] **Step 3: Implement the rules parser**

`backend/llm/rules_parser.py`:

```python
"""Deterministic fallback parser, used whenever the LLM is unavailable (spec §8.3).
A Python port of frontend/src/lib/search.ts `parseQuery`, generalised: whatever it
cannot classify becomes one VehicleMention for the catalog resolver to try."""

import re
from collections.abc import Collection

from core.text import normalize_persian
from enums import Gearbox
from schemas.search import SearchIntent, VehicleMention

TOMAN_PER_MILLION = 1_000_000
TOMAN_PER_BILLION = 1_000_000_000
IMPLICIT_BILLION_BELOW = 5  # «زیر 1.2» means billions
KM_PER_THOUSAND = 1_000
LOW_MILEAGE_KM = 90_000
CENTURY_PIVOT = 50  # «مدل 98» → 1398, «مدل 02» → 1402
BILLION_WORD = "میلیارد"
MILEAGE_WORDS = ("کیلومتر", "کارکرد")

_LIMIT = r"(?:زیر|کمتر از|تا|حداکثر|سقف)"
_PRICE = re.compile(
    rf"{_LIMIT}\s*(\d+(?:[./]\d+)?)\s*(هزار)?\s*(میلیارد|میلیون|تومان|تومن|کیلومتر|کارکرد)?"
)
_ONE_BILLION = re.compile(r"(?:زیر|تا)?\s*یک میلیارد")
_KM = re.compile(rf"(?:کارکرد\s*)?{_LIMIT}\s*(\d+)\s*(?:هزار)?\s*(?:کیلومتر|کارکرد)")
_LOW_MILEAGE = re.compile(r"کم\s?کارکرد|کم کار")
_YEAR = re.compile(r"(?:مدل|سال)\s*(1[34]\d\d|\d\d)\b(\s*به بالا)?")
_AUTOMATIC = re.compile(r"اتومات\w*")
_MANUAL = re.compile(r"دنده\s?ای|دنده")
_BELOW_MARKET = re.compile(r"ارزان\w*|زیر قیمت|به صرفه")
_STOP_WORDS = frozenset(
    {"میخوام", "می", "خوام", "یه", "یک", "ماشین", "خودرو", "در", "تو", "توی"}
    | {"با", "و", "اطراف", "رنگ", "دنبال", "هستم"}
)


class _Text:
    """The query with every recognised clause blanked out as it is consumed."""

    def __init__(self, text: str) -> None:
        self.remaining = text

    def take(self, pattern: re.Pattern[str]) -> re.Match[str] | None:
        found = pattern.search(self.remaining)
        if found:
            start, end = found.span()
            self.remaining = f"{self.remaining[:start]} {self.remaining[end:]}"
        return found


def _is_mileage(thousand: str | None, unit: str | None) -> bool:
    return unit in MILEAGE_WORDS or (bool(thousand) and unit is None)


def _price_max(text: _Text) -> int | None:
    for found in _PRICE.finditer(text.remaining):
        value, thousand, unit = found.groups()
        if _is_mileage(thousand, unit):
            continue
        text.remaining = text.remaining.replace(found.group(), " ", 1)
        amount = float(value.replace("/", "."))
        in_billions = unit == BILLION_WORD or (
            unit is None and amount < IMPLICIT_BILLION_BELOW
        )
        return round(amount * (TOMAN_PER_BILLION if in_billions else TOMAN_PER_MILLION))
    return TOMAN_PER_BILLION if text.take(_ONE_BILLION) else None


def _km_max(text: _Text) -> int | None:
    found = text.take(_KM)
    if found:
        value = int(found.group(1))
        return value * KM_PER_THOUSAND if value < KM_PER_THOUSAND else value
    return LOW_MILEAGE_KM if text.take(_LOW_MILEAGE) else None


def _years(text: _Text) -> tuple[int | None, int | None]:
    found = text.take(_YEAR)
    if not found:
        return None, None
    year = int(found.group(1))
    if year < 100:
        year += 1300 if year >= CENTURY_PIVOT else 1400
    return year, (None if found.group(2) else year)


def _gearbox(text: _Text) -> Gearbox | None:
    if text.take(_AUTOMATIC):
        return Gearbox.AUTOMATIC
    return Gearbox.MANUAL if text.take(_MANUAL) else None


def _city(text: _Text, known_cities: Collection[str]) -> str | None:
    padded = f" {text.remaining} "
    for city in sorted(known_cities, key=len, reverse=True):
        normalized = normalize_persian(city)
        if normalized and f" {normalized} " in padded:
            text.remaining = padded.replace(f" {normalized} ", " ", 1)
            return city
    return None


def _remainder(text: _Text) -> str:
    words = [word for word in text.remaining.split() if word not in _STOP_WORDS]
    return " ".join(words)


def parse_with_rules(query: str, known_cities: Collection[str]) -> SearchIntent:
    text = _Text(normalize_persian(query))
    km_max = _km_max(text)  # before price: «زیر 50 هزار کیلومتر» is mileage
    price_max = _price_max(text)
    year_min, year_max = _years(text)
    gearbox = _gearbox(text)
    only_below_market = text.take(_BELOW_MARKET) is not None
    city = _city(text, known_cities)
    remainder = _remainder(text)
    return SearchIntent(
        vehicles=[VehicleMention(model=remainder)] if remainder else [],
        year_min=year_min,
        year_max=year_max,
        price_max=price_max,
        km_max=km_max,
        cities=[city] if city else [],
        gearbox=gearbox,
        only_below_market=only_below_market,
    )
```

- [ ] **Step 4: Implement the model factory, agent and QueryParser**

`backend/llm/model_factory.py`:

```python
"""The only module that knows which LLM provider is in use (spec §8.1)."""

from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider

from core.config import Settings
from enums import LlmProvider


def build_model(settings: Settings) -> Model | None:
    """None when no API key is configured: search then runs on the rules parser."""
    api_key = settings.llm_api_key.get_secret_value()
    if not api_key:
        return None
    match settings.llm_provider:
        case LlmProvider.GOOGLE:  # development — Gemini API
            return GoogleModel(
                settings.llm_model, provider=GoogleProvider(api_key=api_key)
            )
        case LlmProvider.OPENAI_COMPATIBLE:  # production — OpenRouter or OpenAI-like
            provider = OpenAIProvider(
                base_url=settings.llm_base_url or None, api_key=api_key
            )
            return OpenAIChatModel(settings.llm_model, provider=provider)
```

`backend/llm/intent_agent.py`:

```python
"""The Pydantic AI agent that turns a Persian search sentence into a SearchIntent.
It has no tools and one output type: the LLM never writes SQL (spec §8.2)."""

from datetime import date

from pydantic_ai import Agent
from pydantic_ai.models import Model

from core.text import jalali_year
from schemas.search import SearchIntent

OUTPUT_RETRIES = 2

_INSTRUCTIONS = """\
You convert one Persian used-vehicle search query (Divar marketplace, Iran) into a
SearchIntent. Extract only what the user stated; leave everything else unset.

Rules:
- The current Jalali year is {year}. Years are Jalali. «مدل ۹۸» means 1398, «مدل ۰۲»
  means 1402. «مدل ۹۸» sets year_min = year_max = 1398. «۹۵ به بالا» sets only
  year_min = 1395. «تا مدل ۹۰» sets only year_max.
- All money is in toman as a full integer. «۸۰۰ میلیون» = 800000000. «۱.۲ میلیارد»
  = 1200000000. A bare number under 5 after «زیر/تا» means billions («زیر ۱.۲» =
  1200000000); a bare number of 5 or more means millions («زیر ۸۰۰» = 800000000).
  «زیر/تا/حداکثر/سقف» set price_max; «از/حداقل/بالای» set price_min.
- km_max is in kilometres: «زیر ۵۰ هزار کیلومتر» = 50000. «کم‌کارکرد» = 90000.
- vehicles: copy the brand, model and trim words exactly as the user wrote them, in
  Persian. Do not translate, expand or guess. «۲۰۶ تیپ ۲» → brand «پژو», model «۲۰۶»,
  trim «تیپ ۲». Several vehicles → several entries.
- category: light = passenger cars and pickups, motorcycle, heavy = trucks, buses,
  agricultural and construction machinery, rental, classic. Set it only when clear.
- cities: Persian city names exactly as written.
- gearbox: «اتومات/اتوماتیک» → automatic, «دنده‌ای/دستی» → manual.
- only_below_market: true for «ارزان», «زیر قیمت», «به‌صرفه».
- sort: price for «ارزان‌ترین», km for «کم‌کارکردترین», newest for «جدیدترین»;
  otherwise relevance.
- text: any remaining descriptive words (e.g. «شاسی‌بلند», «خانوادگی»); else unset.

Examples:
«۲۰۶ مدل ۹۸ زیر ۸۰۰ میلیون تهران» → vehicles=[{{brand: پژو, model: ۲۰۶}}],
  year_min=1398, year_max=1398, price_max=800000000, cities=[تهران]
«دنا پلاس اتومات تا یک و نیم میلیارد کرج یا تهران» → vehicles=[{{model: دنا پلاس}}],
  gearbox=automatic, price_max=1500000000, cities=[کرج, تهران]
«موتور هوندا ۱۲۵ کم‌کارکرد» → category=motorcycle,
  vehicles=[{{brand: هوندا, model: ۱۲۵}}], km_max=90000
«یه شاسی‌بلند سفید زیر ۳ میلیارد» → price_max=3000000000, colors=[سفید],
  text=شاسی‌بلند
«کامیون بنز ده تن» → category=heavy, text=کامیون بنز ده تن
"""


def build_instructions() -> str:
    return _INSTRUCTIONS.format(year=jalali_year(date.today()))


def build_intent_agent(model: Model) -> Agent[None, SearchIntent]:
    return Agent(
        model,
        output_type=SearchIntent,
        instructions=build_instructions,
        retries=OUTPUT_RETRIES,
    )
```

`backend/services/query_parser.py`:

```python
"""Free text → SearchIntent: cache → LLM → rules fallback (spec §8.3)."""

import asyncio
import hashlib
import logging
from dataclasses import dataclass

import httpx
from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError, ModelAPIError

from core.cache import Cache
from core.text import normalize_persian
from enums import ParsedBy
from llm.rules_parser import parse_with_rules
from repositories.city_repository import CityRepository
from schemas.search import SearchIntent

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1"  # bump when llm/intent_agent.py instructions change
LLM_FAILURES = (AgentRunError, ModelAPIError, TimeoutError, httpx.HTTPError)


@dataclass(frozen=True, slots=True)
class ParsedQuery:
    intent: SearchIntent
    parsed_by: ParsedBy


def _cache_key(query: str) -> str:
    digest = hashlib.sha256(query.encode()).hexdigest()
    return f"intent:{PROMPT_VERSION}:{digest}"


class QueryParser:
    def __init__(
        self,
        agent: Agent[None, SearchIntent] | None,
        cities: CityRepository,
        cache: Cache,
        timeout_seconds: float,
        cache_ttl_seconds: int,
    ) -> None:
        self._agent = agent
        self._cities = cities
        self._cache = cache
        self._timeout_seconds = timeout_seconds
        self._cache_ttl_seconds = cache_ttl_seconds

    async def parse(self, text: str) -> ParsedQuery:
        query = normalize_persian(text)
        if not query:
            return ParsedQuery(SearchIntent(), ParsedBy.RULES)
        cached = await self._cache.get_json(_cache_key(query))
        if cached is not None:
            return ParsedQuery(SearchIntent.model_validate(cached), ParsedBy.LLM)
        intent = await self._ask_llm(query)
        if intent is None:
            # Fallback results are not cached, so the next request retries the LLM.
            known_cities = await self._cities.list_names()
            return ParsedQuery(parse_with_rules(query, known_cities), ParsedBy.RULES)
        payload = intent.model_dump(mode="json")
        await self._cache.set_json(_cache_key(query), payload, self._cache_ttl_seconds)
        return ParsedQuery(intent, ParsedBy.LLM)

    async def _ask_llm(self, query: str) -> SearchIntent | None:
        """None means "use the rules parser". An LLM outage must never fail a search,
        so provider errors are logged and absorbed here — deliberately."""
        if self._agent is None:
            return None
        try:
            result = await asyncio.wait_for(
                self._agent.run(query), self._timeout_seconds
            )
        except LLM_FAILURES as error:
            fields = {"error": type(error).__name__, "detail": str(error)}
            logger.warning("llm parse failed, using rules", extra={"fields": fields})
            return None
        return result.output
```

- [ ] **Step 5: Implement the opt-in live eval**

`backend/llm/eval.py`:

```python
"""Opt-in live accuracy check of the intent prompt. Calls the REAL provider, costs
tokens, and is never run in CI:

    uv run python -m llm.eval

Run it before and after editing llm/intent_agent.py, and bump PROMPT_VERSION in
services/query_parser.py when the instructions change."""

import asyncio

from core.config import get_settings
from core.text import normalize_persian
from llm.eval_cases import EVAL_CASES, EvalCase
from llm.intent_agent import build_intent_agent
from llm.model_factory import build_model
from schemas.search import SearchIntent


def score_case(case: EvalCase, intent: SearchIntent) -> tuple[int, int, list[str]]:
    """(fields correct, fields checked, names of the wrong fields)."""
    wrong = [
        name for name, value in case.expected.items() if getattr(intent, name) != value
    ]
    mention = normalize_persian(
        " ".join(
            " ".join(filter(None, (vehicle.brand, vehicle.model, vehicle.trim)))
            for vehicle in intent.vehicles
        )
    )
    if not all(word in mention for word in case.vehicle_words):
        wrong.append("vehicles")
    checked = len(case.expected) + bool(case.vehicle_words)
    return checked - len(wrong), checked, wrong


async def main() -> None:
    model = build_model(get_settings())
    if model is None:
        raise SystemExit("LLM_API_KEY is not set")
    agent = build_intent_agent(model)
    correct = checked = 0
    for case in EVAL_CASES:
        result = await agent.run(normalize_persian(case.query))
        case_correct, case_checked, wrong = score_case(case, result.output)
        correct += case_correct
        checked += case_checked
        print(f"{'ok ' if not wrong else 'BAD'} {case.query}  {wrong or ''}")
    print(f"\nfield accuracy: {correct}/{checked} = {correct / checked:.0%}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run black --check .`
Expected: `154 passed`. No test reaches a provider: `conftest.py` sets `ALLOW_MODEL_REQUESTS = False`.

- [ ] **Step 7: (Optional, needs the user's Gemini key) live prompt check**

With `LLM_API_KEY` set in the repo-root `.env`: `uv run python -m llm.eval`
Expected: a line per query and `field accuracy: N/M`. Below ~90% means the prompt in
`llm/intent_agent.py` needs work — report the BAD lines to the user; do not tune
silently. Skip this step when no key is available.

- [ ] **Step 8: Commit**

```bash
cd .. && git add backend/llm backend/services/query_parser.py backend/tests
git commit -m "feat(llm): add Pydantic AI intent agent with deterministic rules fallback

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: Search, listing and facet services + REST API

**Files:**
- Create: `backend/services/listing_views.py`, `backend/services/search_service.py`, `backend/services/listing_service.py`, `backend/services/facet_service.py`, `backend/dependencies/__init__.py`, `backend/dependencies/providers.py`, `backend/api/v1/endpoints/search.py`, `backend/api/v1/endpoints/listings.py`, `backend/api/v1/endpoints/facets.py`, `backend/ingest/__main__.py`
- Replace: `backend/api/v1/router.py`, `backend/api/health.py`, `backend/main.py`, `backend/tests/conftest.py`
- Test: `backend/tests/services/test_search_service.py`, `backend/tests/api/test_search_api.py`

**Interfaces:**
- Consumes: everything from Tasks 7–10.
- Produces: `SearchService(parser, resolver, listings, ranker, cache, cache_ttl_seconds)` with `search(query, overrides, page, page_size) -> SearchResponse`, `rank(intent, exclude_id=None) -> tuple[RankedSearch, bool]`, `page_of(results, page, page_size) -> list[ListingCard]`; `ListingService(listings, search)` with `get_detail`, `get_many`, `get_similar`; `FacetService.get_facets(category)`; `services.listing_views.to_card`, `to_detail`, `verdict_of`; providers `get_cache`, `get_intent_agent`, `get_query_parser`, `get_search_service`, `get_listing_service`, `get_facet_service`, type aliases `SessionDep`, `CacheDep`; endpoints `GET /api/v1/search`, `GET /api/v1/listings`, `GET /api/v1/listings/{id}`, `GET /api/v1/listings/{id}/similar`, `GET /api/v1/facets`, `GET /health/ready`; CLI `python -m ingest <csv>`; pytest fixture `api`.

- [ ] **Step 1: Write the failing tests**

Create empty `backend/dependencies/__init__.py`.

Replace `backend/tests/conftest.py` with its final version:

`backend/tests/conftest.py`:

```python
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic_ai import models
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import get_settings
from db.session import get_session
from dependencies.providers import get_cache, get_intent_agent
from ingest.pipeline import IngestPipeline
from main import create_app
from repositories.catalog_repository import CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import ListingRepository
from tests.support import DictCache

models.ALLOW_MODEL_REQUESTS = False  # tests must never reach a real LLM

BACKEND_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_CSV = BACKEND_ROOT / "tests" / "fixtures" / "listings_sample.csv"


@pytest.fixture(scope="session")
def migrated_database_url() -> str:
    """Runs the real Alembic migrations once against the throwaway test database
    (start it with `docker compose -f .docker/compose.test.yml up -d`)."""
    url = get_settings().test_database_url
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "db" / "migrations"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    return url


@pytest.fixture
async def session(migrated_database_url: str) -> AsyncIterator[AsyncSession]:
    """A session inside one outer transaction that is always rolled back."""
    engine = create_async_engine(migrated_database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        ) as db_session:
            yield db_session
        await transaction.rollback()
    await engine.dispose()


@pytest.fixture
def cache() -> DictCache:
    return DictCache()


@pytest.fixture
async def seeded_session(session: AsyncSession, cache: DictCache) -> AsyncSession:
    """The ~600-row fixture CSV loaded through the real ingest pipeline."""
    pipeline = IngestPipeline(
        CityRepository(session),
        CatalogRepository(session),
        ListingRepository(session),
        cache,
    )
    await pipeline.run(FIXTURE_CSV)
    return session


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.fixture
async def api(
    app: FastAPI, seeded_session: AsyncSession, cache: DictCache
) -> AsyncIterator[AsyncClient]:
    """HTTP client wired to the seeded test database, an in-memory cache and no LLM
    (so every query goes through the rules parser)."""

    async def use_seeded_session() -> AsyncIterator[AsyncSession]:
        yield seeded_session

    app.dependency_overrides[get_session] = use_seeded_session
    app.dependency_overrides[get_cache] = lambda: cache
    app.dependency_overrides[get_intent_agent] = lambda: None
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
```

`backend/tests/services/test_search_service.py`:

```python
"""SearchService in isolation: every collaborator is a stub (CLAUDE.md §8)."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from enums import Category, EstimateBasis, ParsedBy
from errors import InvalidSearchError, ListingNotFoundError
from ranking.ranker import ListingRanker
from ranking.types import Candidate, RankingQuery
from repositories.listing_repository import CandidateFilter
from schemas.search import SearchIntent, SearchOverrides
from services.intent_resolver import ResolvedIntent
from services.listing_service import MAX_BATCH_IDS, ListingService
from services.query_parser import ParsedQuery
from services.search_service import SearchService
from tests.support import DictCache

NOW = datetime(2026, 9, 17, 20, 0, tzinfo=UTC)
IDS = [uuid.UUID(int=number) for number in range(1, 4)]


def make_listing(listing_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=listing_id,
        token=f"tok{listing_id.int}",
        title="پژو ۲۰۶",
        category=Category.LIGHT,
        catalog=None,
        city=SimpleNamespace(name="تهران"),
        year=1398,
        km=60_000,
        price=800_000_000,
        district=None,
        thumbnail_urls=[],
        image_urls=[],
        posted_at=NOW,
        est_price=None,
        diff_pct=None,
        deal_score=None,
        est_basis=EstimateBasis.NONE,
    )


class StubParser:
    async def parse(self, text: str) -> ParsedQuery:
        return ParsedQuery(SearchIntent(), ParsedBy.RULES)


class StubResolver:
    async def resolve(self, intent: SearchIntent) -> ResolvedIntent:
        return ResolvedIntent(RankingQuery(), CandidateFilter(), ("چیپ",))


class StubListings:
    def __init__(self) -> None:
        self.candidate_queries = 0
        self.last_filters: CandidateFilter | None = None

    async def find_candidates(
        self, filters: CandidateFilter, limit: int
    ) -> list[Candidate]:
        self.candidate_queries += 1
        self.last_filters = filters
        scores = (90, 50, 70)
        return [
            Candidate(id=listing_id, deal_score=score, posted_at=NOW)
            for listing_id, score in zip(IDS, scores, strict=True)
        ]

    async def newest_fetched_at(self) -> datetime:
        return NOW

    async def get_by_ids(self, listing_ids: list[uuid.UUID]) -> list[SimpleNamespace]:
        return [make_listing(listing_id) for listing_id in listing_ids]

    async def get_by_id(self, listing_id: uuid.UUID) -> None:
        return None


def make_service(listings: StubListings, cache: DictCache) -> SearchService:
    return SearchService(
        StubParser(), StubResolver(), listings, ListingRanker(), cache, 60
    )


async def test_search_ranks_pages_and_reports_totals() -> None:
    service = make_service(StubListings(), DictCache())
    response = await service.search(None, SearchOverrides(), page=1, page_size=2)
    assert (response.total, response.exact_count) == (3, 3)
    assert [item.id for item in response.items] == [IDS[0], IDS[2]]  # deal 90, 70
    assert response.intent.chips == ["چیپ"]


async def test_second_page_reuses_the_cached_ranking() -> None:
    listings, cache = StubListings(), DictCache()
    service = make_service(listings, cache)
    await service.search(None, SearchOverrides(), page=1, page_size=2)
    second = await service.search(None, SearchOverrides(), page=2, page_size=2)
    assert listings.candidate_queries == 1
    assert [item.id for item in second.items] == [IDS[1]]


async def test_a_new_data_version_invalidates_the_cached_ranking() -> None:
    listings, cache = StubListings(), DictCache()
    service = make_service(listings, cache)
    await service.search(None, SearchOverrides(), page=1, page_size=2)
    await cache.bump_data_version()
    await service.search(None, SearchOverrides(), page=1, page_size=2)
    assert listings.candidate_queries == 2


async def test_paging_past_the_result_cap_is_rejected() -> None:
    service = make_service(StubListings(), DictCache())
    with pytest.raises(InvalidSearchError):
        await service.search(None, SearchOverrides(), page=11, page_size=50)


async def test_similar_search_excludes_the_listing_itself() -> None:
    listings = StubListings()
    service = make_service(listings, DictCache())
    await service.rank(SearchIntent(), exclude_id=IDS[0])
    assert listings.last_filters.exclude_id == IDS[0]


async def test_listing_service_guards_missing_listings_and_batch_size() -> None:
    listings = StubListings()
    service = ListingService(listings, make_service(listings, DictCache()))
    with pytest.raises(ListingNotFoundError):
        await service.get_detail(IDS[0])
    with pytest.raises(InvalidSearchError):
        await service.get_many([uuid.uuid4() for _ in range(MAX_BATCH_IDS + 1)])
```

`backend/tests/api/test_search_api.py`:

```python
"""End-to-end golden queries (spec §11): real migrations, real ingest of the fixture
CSV, real SQL and ranking — only Redis and the LLM are replaced. Assertions are about
PROPERTIES of the ranking, never about specific listing ids."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.db
MILLION = 1_000_000


async def search(api: AsyncClient, **params: object) -> dict:
    response = await api.get("/api/v1/search", params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def test_model_query_returns_only_that_model_first(api: AsyncClient) -> None:
    body = await search(api, q="۲۰۶ تهران", page_size=10)
    assert body["parsed_by"] == "rules"
    assert body["intent"]["chips"] == ["پژو 206", "تهران"]
    assert [item["model"] for item in body["items"]] == ["پژو 206"] * 10


async def test_exact_matches_precede_near_misses(api: AsyncClient) -> None:
    body = await search(api, q="۲۰۶ تیپ ۲ تهران", page_size=50)
    exactness = [item["is_exact"] for item in body["items"]]
    assert exactness == sorted(exactness, reverse=True)
    assert body["exact_count"] == sum(exactness) > 0
    near_misses = [item for item in body["items"] if not item["is_exact"]]
    assert near_misses and all(item["near_miss_labels"] for item in near_misses)


async def test_budget_is_soft_but_bounded(api: AsyncClient) -> None:
    budget = 900 * MILLION
    body = await search(api, q="۲۰۶ زیر ۹۰۰ میلیون", page_size=50)
    prices = [item["price"] for item in body["items"] if item["price"]]
    assert prices and max(prices) <= budget * 1.25
    over = [item for item in body["items"] if item["price"] and item["price"] > budget]
    assert all("بالاتر از بودجه" in " ".join(i["near_miss_labels"]) for i in over)


async def test_nearer_city_beats_a_far_one(api: AsyncClient) -> None:
    body = await search(api, q="۲۰۶ تیپ ۲ تهران", page_size=50)
    cities = [item["city"] for item in body["items"]]
    assert cities[0] == "تهران"
    if "کرج" in cities and "مشهد" in cities:
        assert cities.index("کرج") < cities.index("مشهد")


async def test_other_models_never_precede_the_requested_model(api: AsyncClient) -> None:
    body = await search(api, q="۲۰۶", page_size=50)
    models = [item["model"] for item in body["items"]]
    last_206 = max(index for index, model in enumerate(models) if model == "پژو 206")
    assert all(model == "پژو 206" for model in models[: last_206 + 1])


async def test_explicit_filters_override_the_text(api: AsyncClient) -> None:
    body = await search(api, q="۲۰۶ تهران", cities=["مشهد"], sort="price")
    assert body["intent"]["cities"] == ["مشهد"]
    exact_prices = [i["price"] for i in body["items"] if i["is_exact"] and i["price"]]
    assert exact_prices == sorted(exact_prices)


async def test_heavy_vehicles_are_found_by_title_text(api: AsyncClient) -> None:
    body = await search(api, q="کامیون", category="heavy")
    assert body["total"] > 0
    assert {item["category"] for item in body["items"]} == {"heavy"}


async def test_browse_mode_and_stable_pagination(api: AsyncClient) -> None:
    first = await search(api, page=1, page_size=5)
    second = await search(api, page=2, page_size=5)
    assert first["total"] == 500  # capped at MAX_RESULTS
    ids = [item["id"] for item in first["items"] + second["items"]]
    assert len(set(ids)) == 10


async def test_paging_past_the_cap_is_a_clean_422(api: AsyncClient) -> None:
    response = await api.get("/api/v1/search", params={"page": 11, "page_size": 50})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_search"


async def test_overlong_query_is_rejected(api: AsyncClient) -> None:
    response = await api.get("/api/v1/search", params={"q": "پ" * 301})
    assert response.status_code == 422


async def test_detail_similar_batch_and_facets(api: AsyncClient) -> None:
    listing = (await search(api, q="۲۰۶ تیپ ۲ تهران"))["items"][0]
    detail = (await api.get(f"/api/v1/listings/{listing['id']}")).json()
    assert detail["token"] == listing["token"]
    assert set(detail["price_breakdown"]) >= {"base", "km_adjustment", "est_basis"}
    similar = (await api.get(f"/api/v1/listings/{listing['id']}/similar")).json()
    assert similar and listing["id"] not in [item["id"] for item in similar]
    assert similar[0]["model"] == "پژو 206"
    batch = await api.get("/api/v1/listings", params={"ids": [listing["id"]]})
    assert [item["id"] for item in batch.json()] == [listing["id"]]
    facets = (await api.get("/api/v1/facets")).json()
    assert facets["categories"]["light"] == 420
    assert facets["models"][0]["count"] >= facets["models"][-1]["count"]


async def test_unknown_listing_is_a_404_envelope(api: AsyncClient) -> None:
    missing = "00000000-0000-8000-8000-000000000000"
    response = await api.get(f"/api/v1/listings/{missing}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "listing_not_found"


async def test_readiness(api: AsyncClient) -> None:
    assert (await api.get("/health/ready")).json() == {"status": "ready"}


async def test_second_identical_search_is_served_from_the_cache(
    api: AsyncClient, cache
) -> None:
    await search(api, q="۲۰۶ تهران")
    keys_after_first = set(cache.values)
    body = await search(api, q="۲۰۶ تهران", page=2)
    assert set(cache.values) == keys_after_first  # nothing new was computed
    assert body["page"] == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/services/test_search_service.py tests/api -q`
Expected: `ModuleNotFoundError: No module named 'dependencies.providers'` (from `conftest.py`).

- [ ] **Step 3: Implement the services**

`backend/services/listing_views.py`:

```python
"""ORM Listing → API schemas. ORM objects never leave the service layer untranslated."""

from enums import Verdict
from models.listing import Listing
from ranking.types import RankedListing
from schemas.listing import ListingCard, ListingDetail, PriceBreakdown

CHEAP_DIFF_PCT = -5.0
EXPENSIVE_DIFF_PCT = 6.0


def verdict_of(diff_pct: float | None) -> Verdict:
    if diff_pct is None:
        return Verdict.UNKNOWN
    if diff_pct <= CHEAP_DIFF_PCT:
        return Verdict.CHEAP
    if diff_pct >= EXPENSIVE_DIFF_PCT:
        return Verdict.EXPENSIVE
    return Verdict.FAIR


def _card_fields(listing: Listing) -> dict[str, object]:
    catalog = listing.catalog
    thumbnails = listing.thumbnail_urls or listing.image_urls
    return {
        "id": listing.id,
        "token": listing.token,
        "title": listing.title,
        "category": listing.category,
        "brand": catalog.brand if catalog else None,
        "model": catalog.model if catalog else None,
        "trim": catalog.trim if catalog else None,
        "year": listing.year,
        "km": listing.km,
        "price": listing.price,
        "city": listing.city.name,
        "district": listing.district,
        "thumbnail_url": thumbnails[0] if thumbnails else None,
        "posted_at": listing.posted_at,
        "est_price": listing.est_price,
        "diff_pct": listing.diff_pct,
        "deal_score": listing.deal_score,
        "verdict": verdict_of(listing.diff_pct),
    }


def to_card(listing: Listing, ranked: RankedListing | None = None) -> ListingCard:
    fields = _card_fields(listing)
    if ranked is not None:
        fields |= {
            "match_score": ranked.match,
            "is_exact": ranked.is_exact,
            "near_miss_labels": list(ranked.labels),
        }
    return ListingCard(**fields)


def _price_breakdown(listing: Listing) -> PriceBreakdown:
    base = None
    km_adjustment = None
    insurance_adjustment = None
    if listing.est_price is not None:
        base = round(listing.est_price / (listing.km_factor * listing.insurance_factor))
        km_adjustment = round(base * (listing.km_factor - 1))
        insurance_adjustment = round(base * (listing.insurance_factor - 1))
    return PriceBreakdown(
        base=base,
        km_adjustment=km_adjustment,
        insurance_adjustment=insurance_adjustment,
        est_basis=listing.est_basis,
        est_sample_size=listing.est_sample_size,
    )


def to_detail(listing: Listing) -> ListingDetail:
    return ListingDetail(
        **_card_fields(listing),
        url=listing.url,
        description=listing.description,
        image_urls=listing.image_urls,
        lat=listing.lat,
        lng=listing.lng,
        gearbox=listing.gearbox,
        fuel=listing.fuel,
        color=listing.color,
        insurance_months=listing.insurance_months,
        is_dealer=listing.is_dealer,
        attributes=listing.attributes,
        price_breakdown=_price_breakdown(listing),
    )
```

`backend/services/search_service.py`:

```python
"""Search orchestration (spec §7): parse → resolve → candidates → rank → cache."""

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from core.cache import Cache
from enums import ParsedBy
from errors import InvalidSearchError
from ranking.ranker import ListingRanker
from ranking.types import RankedListing
from repositories.listing_repository import ListingRepository
from schemas.listing import ListingCard
from schemas.search import IntentRead, SearchIntent, SearchOverrides, SearchResponse
from services.intent_resolver import IntentResolver
from services.listing_views import to_card
from services.query_parser import QueryParser

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 5_000
# ponytail: only the top 500 are cached and pageable; re-rank on demand if anyone
# ever pages deeper.
MAX_RESULTS = 500
MILLISECONDS = 1_000


@dataclass(frozen=True, slots=True)
class RankedSearch:
    chips: tuple[str, ...]
    results: tuple[RankedListing, ...]


def _to_payload(search: RankedSearch) -> dict[str, object]:
    rows = [
        [str(item.id), item.rank, item.match, item.is_exact, list(item.labels)]
        for item in search.results
    ]
    return {"chips": list(search.chips), "results": rows}


def _from_payload(payload: dict) -> RankedSearch:
    results = tuple(
        RankedListing(uuid.UUID(listing_id), rank, match, is_exact, tuple(labels))
        for listing_id, rank, match, is_exact, labels in payload["results"]
    )
    return RankedSearch(tuple(payload["chips"]), results)


class SearchService:
    def __init__(
        self,
        parser: QueryParser,
        resolver: IntentResolver,
        listings: ListingRepository,
        ranker: ListingRanker,
        cache: Cache,
        cache_ttl_seconds: int,
    ) -> None:
        self._parser = parser
        self._resolver = resolver
        self._listings = listings
        self._ranker = ranker
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    async def search(
        self, query: str | None, overrides: SearchOverrides, page: int, page_size: int
    ) -> SearchResponse:
        started = time.perf_counter()
        parsed = await self._parser.parse(query or "")
        intent = overrides.apply_to(parsed.intent)
        ranked, cache_hit = await self.rank(intent)
        items = await self.page_of(ranked.results, page, page_size)
        self._log(parsed.parsed_by, cache_hit, len(ranked.results), started)
        return SearchResponse(
            intent=IntentRead(**intent.model_dump(), chips=list(ranked.chips)),
            parsed_by=parsed.parsed_by,
            total=len(ranked.results),
            exact_count=sum(item.is_exact for item in ranked.results),
            page=page,
            page_size=page_size,
            items=items,
        )

    async def rank(
        self, intent: SearchIntent, exclude_id: uuid.UUID | None = None
    ) -> tuple[RankedSearch, bool]:
        key = await self._cache_key(intent, exclude_id)
        cached = await self._cache.get_json(key)
        if cached is not None:
            return _from_payload(cached), True
        resolved = await self._resolver.resolve(intent)
        filters = replace(resolved.filters, exclude_id=exclude_id)
        candidates = await self._listings.find_candidates(filters, MAX_CANDIDATES)
        now = await self._listings.newest_fetched_at() or datetime.now(UTC)
        results = self._ranker.rank(resolved.query, candidates, now)[:MAX_RESULTS]
        search = RankedSearch(resolved.chips, tuple(results))
        await self._cache.set_json(key, _to_payload(search), self._cache_ttl_seconds)
        return search, False

    async def page_of(
        self, results: tuple[RankedListing, ...], page: int, page_size: int
    ) -> list[ListingCard]:
        start = (page - 1) * page_size
        if start >= MAX_RESULTS:
            raise InvalidSearchError(
                f"Only the first {MAX_RESULTS} results can be paged",
                {"page": page, "page_size": page_size},
            )
        window = results[start : start + page_size]
        listings = await self._listings.get_by_ids([item.id for item in window])
        ranked_by_id = {item.id: item for item in window}
        return [to_card(listing, ranked_by_id[listing.id]) for listing in listings]

    async def _cache_key(
        self, intent: SearchIntent, exclude_id: uuid.UUID | None
    ) -> str:
        version = await self._cache.get_data_version()
        canonical = json.dumps(
            {"intent": intent.model_dump(mode="json"), "exclude": str(exclude_id)},
            sort_keys=True,
            ensure_ascii=False,
        )
        return f"search:{version}:{hashlib.sha256(canonical.encode()).hexdigest()}"

    @staticmethod
    def _log(parsed_by: ParsedBy, cache_hit: bool, total: int, started: float) -> None:
        fields = {
            "parsed_by": parsed_by.value,
            "cache_hit": cache_hit,
            "total": total,
            "duration_ms": round((time.perf_counter() - started) * MILLISECONDS),
        }
        logger.info("search", extra={"fields": fields})
```

`backend/services/listing_service.py`:

```python
import uuid
from collections.abc import Sequence

from errors import InvalidSearchError, ListingNotFoundError
from models.listing import Listing
from repositories.listing_repository import ListingRepository
from schemas.listing import ListingCard, ListingDetail
from schemas.search import SearchIntent, VehicleMention
from services.listing_views import to_card, to_detail
from services.search_service import SearchService

MAX_BATCH_IDS = 4
SIMILAR_PRICE_SPREAD = 0.15
FIRST_PAGE = 1


def _similar_intent(listing: Listing) -> SearchIntent:
    """ "Similar" is not a second algorithm: it is a search for this listing's own
    trim, year, price band and city (spec §7.6)."""
    price = None if listing.price_suspect else listing.price
    catalog = listing.catalog
    return SearchIntent(
        category=listing.category,
        vehicles=[VehicleMention(trim=catalog.trim)] if catalog else [],
        year_min=listing.year,
        year_max=listing.year,
        price_min=round(price * (1 - SIMILAR_PRICE_SPREAD)) if price else None,
        price_max=round(price * (1 + SIMILAR_PRICE_SPREAD)) if price else None,
        cities=[listing.city.name],
        text=None if catalog else listing.title,
    )


class ListingService:
    def __init__(self, listings: ListingRepository, search: SearchService) -> None:
        self._listings = listings
        self._search = search

    async def _require(self, listing_id: uuid.UUID) -> Listing:
        listing = await self._listings.get_by_id(listing_id)
        if listing is None:
            raise ListingNotFoundError(listing_id)
        return listing

    async def get_detail(self, listing_id: uuid.UUID) -> ListingDetail:
        return to_detail(await self._require(listing_id))

    async def get_many(self, listing_ids: Sequence[uuid.UUID]) -> list[ListingCard]:
        if len(listing_ids) > MAX_BATCH_IDS:
            raise InvalidSearchError(
                f"At most {MAX_BATCH_IDS} listings can be fetched at once",
                {"requested": len(listing_ids)},
            )
        listings = await self._listings.get_by_ids(list(listing_ids))
        return [to_card(listing) for listing in listings]

    async def get_similar(self, listing_id: uuid.UUID, limit: int) -> list[ListingCard]:
        listing = await self._require(listing_id)
        ranked, _ = await self._search.rank(_similar_intent(listing), listing.id)
        return await self._search.page_of(ranked.results, FIRST_PAGE, limit)
```

`backend/services/facet_service.py`:

```python
from core.cache import Cache
from enums import Category
from repositories.catalog_repository import CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import ListingRepository
from schemas.facets import FacetCount, Facets, ModelFacet

TOP_MODELS = 60
TOP_CITIES = 60


class FacetService:
    def __init__(
        self,
        listings: ListingRepository,
        catalog: CatalogRepository,
        cities: CityRepository,
        cache: Cache,
        cache_ttl_seconds: int,
    ) -> None:
        self._listings = listings
        self._catalog = catalog
        self._cities = cities
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    async def get_facets(self, category: Category | None) -> Facets:
        version = await self._cache.get_data_version()
        key = f"facets:{version}:{category.value if category else 'all'}"
        cached = await self._cache.get_json(key)
        if cached is not None:
            return Facets.model_validate(cached)
        facets = await self._build(category)
        payload = facets.model_dump(mode="json")
        await self._cache.set_json(key, payload, self._cache_ttl_seconds)
        return facets

    async def _build(self, category: Category | None) -> Facets:
        models = await self._catalog.list_top_models(category, TOP_MODELS)
        cities = await self._cities.list_top(TOP_CITIES)
        return Facets(
            categories=await self._listings.count_by_category(),
            models=[
                ModelFacet(brand=item.brand, model=item.model, count=item.listing_count)
                for item in models
            ],
            cities=[
                FacetCount(value=city.name, count=city.listing_count) for city in cities
            ],
        )
```

- [ ] **Step 4: Implement the providers and endpoints**

`backend/dependencies/providers.py`:

```python
"""Every FastAPI `Depends` provider — the single place where objects are wired."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from pydantic_ai import Agent
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import Cache
from core.config import Settings, get_settings
from db.session import get_session
from llm.intent_agent import build_intent_agent
from llm.model_factory import build_model
from ranking.ranker import ListingRanker
from repositories.catalog_repository import CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import ListingRepository
from schemas.search import SearchIntent
from services.facet_service import FacetService
from services.intent_resolver import IntentResolver
from services.listing_service import ListingService
from services.query_parser import QueryParser
from services.search_service import SearchService

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache
def get_cache() -> Cache:
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return Cache(client)


@lru_cache
def get_intent_agent() -> Agent[None, SearchIntent] | None:
    model = build_model(get_settings())
    return build_intent_agent(model) if model is not None else None


CacheDep = Annotated[Cache, Depends(get_cache)]
AgentDep = Annotated[Agent[None, SearchIntent] | None, Depends(get_intent_agent)]


def get_query_parser(
    session: SessionDep, cache: CacheDep, agent: AgentDep, settings: SettingsDep
) -> QueryParser:
    return QueryParser(
        agent,
        CityRepository(session),
        cache,
        settings.llm_timeout_seconds,
        settings.intent_cache_ttl_seconds,
    )


def get_search_service(
    session: SessionDep,
    cache: CacheDep,
    settings: SettingsDep,
    parser: Annotated[QueryParser, Depends(get_query_parser)],
) -> SearchService:
    resolver = IntentResolver(CatalogRepository(session), CityRepository(session))
    return SearchService(
        parser,
        resolver,
        ListingRepository(session),
        ListingRanker(),
        cache,
        settings.search_cache_ttl_seconds,
    )


def get_listing_service(
    session: SessionDep,
    search: Annotated[SearchService, Depends(get_search_service)],
) -> ListingService:
    return ListingService(ListingRepository(session), search)


def get_facet_service(
    session: SessionDep, cache: CacheDep, settings: SettingsDep
) -> FacetService:
    return FacetService(
        ListingRepository(session),
        CatalogRepository(session),
        CityRepository(session),
        cache,
        settings.search_cache_ttl_seconds,
    )
```

`backend/api/v1/endpoints/search.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from dependencies.providers import get_search_service
from schemas.search import SearchParams, SearchResponse
from services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search_listings(
    service: Annotated[SearchService, Depends(get_search_service)],
    params: Annotated[SearchParams, Query()],
) -> SearchResponse:
    return await service.search(params.q, params, params.page, params.page_size)
```

`backend/api/v1/endpoints/listings.py`:

```python
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from dependencies.providers import get_listing_service
from schemas.listing import ListingCard, ListingDetail
from services.listing_service import ListingService

DEFAULT_SIMILAR_LIMIT = 6
MAX_SIMILAR_LIMIT = 20

router = APIRouter(prefix="/listings", tags=["listings"])
ServiceDep = Annotated[ListingService, Depends(get_listing_service)]


@router.get("", response_model=list[ListingCard])
async def read_listings(
    service: ServiceDep, ids: Annotated[list[uuid.UUID], Query(min_length=1)]
) -> list[ListingCard]:
    return await service.get_many(ids)


@router.get("/{listing_id}", response_model=ListingDetail)
async def read_listing(service: ServiceDep, listing_id: uuid.UUID) -> ListingDetail:
    return await service.get_detail(listing_id)


@router.get("/{listing_id}/similar", response_model=list[ListingCard])
async def read_similar_listings(
    service: ServiceDep,
    listing_id: uuid.UUID,
    limit: Annotated[int, Query(ge=1, le=MAX_SIMILAR_LIMIT)] = DEFAULT_SIMILAR_LIMIT,
) -> list[ListingCard]:
    return await service.get_similar(listing_id, limit)
```

`backend/api/v1/endpoints/facets.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.providers import get_facet_service
from enums import Category
from schemas.facets import Facets
from services.facet_service import FacetService

router = APIRouter(prefix="/facets", tags=["facets"])


@router.get("", response_model=Facets)
async def read_facets(
    service: Annotated[FacetService, Depends(get_facet_service)],
    category: Category | None = None,
) -> Facets:
    return await service.get_facets(category)
```

Replace these three files with their final versions:

`backend/api/v1/router.py`:

```python
"""Aggregates every v1 endpoint router."""

from fastapi import APIRouter

from api.v1.endpoints import facets, listings, search

router = APIRouter()
router.include_router(search.router)
router.include_router(listings.router)
router.include_router(facets.router)
```

`backend/api/health.py`:

```python
from fastapi import APIRouter
from sqlalchemy import text

from dependencies.providers import CacheDep, SessionDep
from errors import ServiceUnavailableError

router = APIRouter(tags=["health"])


@router.get("/health")
async def read_liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def read_readiness(session: SessionDep, cache: CacheDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))  # OperationalError → 503 via errors.py
    if not await cache.ping():
        raise ServiceUnavailableError("Redis unavailable")
    return {"status": "ready"}
```

`backend/main.py`:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.health import router as health_router
from api.v1.router import router as v1_router
from core.config import get_settings
from core.logging import configure_logging, request_id_middleware
from db.session import get_engine
from dependencies.providers import get_cache
from errors import register_exception_handlers

API_V1_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await get_cache().close()
    await get_engine().dispose()


def create_app() -> FastAPI:
    configure_logging(get_settings().log_level)
    app = FastAPI(title="Torobcar API", lifespan=lifespan)
    app.middleware("http")(request_id_middleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(v1_router, prefix=API_V1_PREFIX)
    return app


app = create_app()
```

- [ ] **Step 5: Implement the ingest CLI**

`backend/ingest/__main__.py`:

```python
"""CLI: `python -m ingest <csv-path>`. Run it inside the backend container
(`./.scripts/ingest.sh <csv-path>`), where `db` and `redis` are reachable."""

import asyncio
import sys
from pathlib import Path

from core.config import get_settings
from core.logging import configure_logging
from db.session import get_engine, get_session_factory
from dependencies.providers import get_cache
from ingest.pipeline import IngestPipeline
from ingest.report import IngestReport
from repositories.catalog_repository import CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import ListingRepository

USAGE = "usage: python -m ingest <csv-path>"


async def run_ingest(csv_path: Path) -> IngestReport:
    cache = get_cache()
    try:
        async with get_session_factory()() as session:
            pipeline = IngestPipeline(
                CityRepository(session),
                CatalogRepository(session),
                ListingRepository(session),
                cache,
            )
            report = await pipeline.run(csv_path)
            await session.commit()  # one transaction: a failed ingest changes nothing
    finally:
        await cache.close()
        await get_engine().dispose()
    return report


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(USAGE)
    csv_path = Path(sys.argv[1])
    if not csv_path.is_file():
        raise SystemExit(f"not a file: {csv_path}")
    configure_logging(get_settings().log_level)
    print(asyncio.run(run_ingest(csv_path)).render())


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run the whole suite with coverage**

Run: `uv run pytest -q --cov=. --cov-report=term-missing && uv run ruff check . && uv run black --check .`
Expected: `174 passed`, total coverage ≈ 90%. `ingest/__main__.py` is the only file at
0% (it is exercised in Task 12's smoke test).

- [ ] **Step 7: Commit**

```bash
cd .. && git add backend/services backend/dependencies backend/api backend/main.py backend/ingest/__main__.py backend/tests
git commit -m "feat(api): add search, listings, similar and facets endpoints

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 12: Docker, Traefik and scripts

> **Unverified while planning.** Nothing in this task was run. Follow the smoke test in
> Step 6 exactly and fix what it finds. Starting this stack mounts the Docker socket
> into Traefik — get the user's go-ahead before `docker compose up`.

**Files:**
- Create: `.dockerignore`, `.docker/backend.Dockerfile`, `.docker/frontend.Dockerfile`, `.docker/compose.yml`, `.docker/compose.dev.yml`, `.scripts/setup.sh`, `.scripts/dev.sh`, `.scripts/lint.sh`, `.scripts/ingest.sh`

**Interfaces:**
- Consumes: `backend/` (Tasks 1–11), the existing `frontend/` (already `output: "standalone"`, lockfile `bun.lock`), `example.env`.
- Produces: the app at `http://localhost` through Traefik; `./.scripts/ingest.sh <csv>`.

- [ ] **Step 1: `.dockerignore`** (repo root)

```gitignore
**/node_modules
**/.venv
**/.next
**/__pycache__
**/.pytest_cache
**/.ruff_cache
**/coverage
.git
.env
assets
prototype
brag-output
graphify-out
docs
```

- [ ] **Step 2: Dockerfiles**

`.docker/backend.Dockerfile`:

```dockerfile
FROM python:3.14-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 PYDANTIC_AI_NO_BANNER=1

FROM base AS builder
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM base AS runtime
RUN useradd --system --no-create-home app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && fastapi run main.py --host 0.0.0.0 --port 8000"]
```

If the tag `ghcr.io/astral-sh/uv:0.11` does not exist, use the newest `0.x` tag listed
at `https://github.com/astral-sh/uv/pkgs/container/uv` — never `latest`.

`.docker/frontend.Dockerfile`:

```dockerfile
FROM oven/bun:1 AS deps
WORKDIR /app
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile

FROM oven/bun:1 AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./
ENV NEXT_PUBLIC_API_URL=/api
RUN bun run build

FROM oven/bun:1 AS runtime
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
COPY --from=builder --chown=bun:bun /app/.next/standalone ./
COPY --from=builder --chown=bun:bun /app/.next/static ./.next/static
COPY --from=builder --chown=bun:bun /app/public ./public
USER bun
EXPOSE 3000
CMD ["bun", "server.js"]
```

If the standalone server fails under Bun, switch the runtime stage to `node:22-slim`
with `CMD ["node", "server.js"]` (`CLAUDE.md` §11.2).

- [ ] **Step 3: `.docker/compose.yml`**

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
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:8-alpine
    command: ["redis-server", "--save", "", "--maxmemory", "256mb", "--maxmemory-policy", "allkeys-lru"]
    expose: ["6379"] # internal only — cache, no persistence
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  pgdata:
```

- [ ] **Step 4: `.docker/compose.dev.yml`**

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
    # the anonymous volume keeps the image's Linux .venv from being hidden by the mount
    volumes: ["../backend:/app", "/app/.venv"]
  frontend:
    command: bun run dev
    volumes: ["../frontend:/app", "/app/node_modules"]
```

- [ ] **Step 5: Scripts** (then `chmod +x .scripts/*.sh`)

`.scripts/setup.sh`:

```bash
#!/usr/bin/env bash
# Bootstrap a fresh clone.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env ]] || cp example.env .env
(cd backend && uv sync)
(cd frontend && bun install)
if command -v pre-commit >/dev/null; then pre-commit install; fi
```

`.scripts/dev.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose -f .docker/compose.yml -f .docker/compose.dev.yml up --build
```

`.scripts/lint.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
(cd backend && uv run ruff check . --fix && uv run black .)
(cd frontend && bun run lint)
```

`.scripts/ingest.sh`:

```bash
#!/usr/bin/env bash
# Load a Divar CSV. Runs INSIDE the backend container: db and redis publish no host port.
set -euo pipefail
csv="${1:?usage: .scripts/ingest.sh <csv-path>}"
csv_dir="$(cd "$(dirname "$csv")" && pwd)"
cd "$(dirname "$0")/.."
docker compose -f .docker/compose.yml run --rm --no-deps \
  -v "$csv_dir:/data:ro" backend python -m ingest "/data/$(basename "$csv")"
```

- [ ] **Step 6: Smoke test** (ask the user before starting the stack)

```bash
cp -n example.env .env
docker compose -f .docker/compose.yml config --quiet && echo "compose ok"
docker compose -f .docker/compose.yml up -d --build --wait
curl -fsS http://localhost/health            # {"status":"ok"}
curl -fsS http://localhost/health/ready      # {"status":"ready"}
./.scripts/ingest.sh assets/divar-vehicles-sep-17-20_32.csv
```

Expected ingest report: `rows read 14652`, `rows upserted 14652`, `rows rejected 0 {}`,
`fields nulled {'km_implausible': 221, 'price_placeholder': 1685}`, `price suspect 611`.
Run it a second time: identical numbers, `data version 2`.

```bash
curl -fsS --get http://localhost/api/v1/search \
  --data-urlencode "q=۲۰۶ مدل ۹۸ زیر ۹۰۰ میلیون تهران" --data-urlencode "page_size=5" \
  | python3 -m json.tool --no-ensure-ascii | head -40
```

Expected: `"parsed_by": "rules"` (no key set) or `"llm"`, chips
`["پژو 206", "مدل ۱۳۹۸", "زیر ۹۰۰ میلیون", "تهران"]`, every item `"model": "پژو 206"`,
exact items before items with `near_miss_labels`.

Routing and port policy:

```bash
curl -fsS -o /dev/null -w "%{http_code}\n" http://localhost/          # 200 — frontend
for i in $(seq 1 40); do curl -s -o /dev/null -w "%{http_code} " "http://localhost/api/v1/search?page_size=1"; done; echo
docker compose -f .docker/compose.yml ps --format '{{.Service}} {{.Ports}}'
```

Expected: a run of `200`s that turns into `429` (rate limit active); only `traefik`
shows a host mapping (`0.0.0.0:80->80/tcp`).

- [ ] **Step 7: Commit**

```bash
git add .dockerignore .docker/backend.Dockerfile .docker/frontend.Dockerfile .docker/compose.yml .docker/compose.dev.yml .scripts
git commit -m "feat(infra): serve the stack behind Traefik with Postgres and Redis

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 13: CI, pre-commit and SonarQube

**Files:**
- Create: `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `.github/workflows/security.yml`, `.github/workflows/docker-publish.yml`, `.docker/compose.sonar.yml`, `sonar-project.properties`, `.scripts/sonar.sh`

- [ ] **Step 1: `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: [--maxkb=1024]
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.16.8
    hooks:
      - id: ruff # lint only (Black handles formatting)
        args: [--fix]
        files: ^backend/
  - repo: https://github.com/psf/black
    rev: 26.5.1
    hooks:
      - id: black
        files: ^backend/
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.21.0
    hooks:
      - id: gitleaks
```

Run: `pre-commit autoupdate && pre-commit install && pre-commit run --all-files`
Expected: every hook passes (whitespace fixers may rewrite files once; re-run, then
stage what they changed).

- [ ] **Step 2: `.github/workflows/ci.yml`**

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  backend:
    runs-on: ubuntu-latest
    defaults:
      run: { working-directory: backend }
    services:
      postgres:
        image: pgvector/pgvector:pg18
        env: { POSTGRES_USER: app, POSTGRES_PASSWORD: app, POSTGRES_DB: app_test }
        ports: ["54329:5432"]
        options: >-
          --health-cmd "pg_isready -U app -d app_test"
          --health-interval 5s --health-timeout 3s --health-retries 20
    env:
      TEST_DATABASE_URL: postgresql+asyncpg://app:app@127.0.0.1:54329/app_test
      PYDANTIC_AI_NO_BANNER: "1"
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run black --check .
      - run: uv run pytest --cov=. --cov-report=xml
  frontend:
    runs-on: ubuntu-latest
    defaults:
      run: { working-directory: frontend }
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
      - run: bun install --frozen-lockfile
      - run: bun run lint
      - run: bunx tsc --noEmit
      - run: bun test
```

- [ ] **Step 3: `.github/workflows/security.yml`**

```yaml
name: security
on:
  pull_request:
  push:
    branches: [main]
  schedule:
    - cron: "0 6 * * 1" # weekly, Monday 06:00 UTC
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

- [ ] **Step 4: `.github/workflows/docker-publish.yml`**

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
          - { service: backend, image: pejmans21/torobcar-backend, dockerfile: .docker/backend.Dockerfile }
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

- [ ] **Step 5: SonarQube server** — `.docker/compose.sonar.yml`

```yaml
# Developer tool, NOT part of the application stack. Start it only to scan; it needs
# ~3 GB of RAM. Loopback-only port — a documented exception to the port policy.
name: torobcar-sonar
services:
  sonarqube:
    image: sonarqube:community
    depends_on:
      sonar-db: { condition: service_healthy }
    environment:
      SONAR_JDBC_URL: jdbc:postgresql://sonar-db:5432/sonar
      SONAR_JDBC_USERNAME: sonar
      SONAR_JDBC_PASSWORD: sonar
    ports: ["127.0.0.1:9000:9000"]
    volumes:
      - sonarqube_data:/opt/sonarqube/data
      - sonarqube_extensions:/opt/sonarqube/extensions
      - sonarqube_logs:/opt/sonarqube/logs
  sonar-db:
    image: postgres:17-alpine
    environment:
      POSTGRES_USER: sonar
      POSTGRES_PASSWORD: sonar
      POSTGRES_DB: sonar
    volumes: ["sonar_db:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sonar -d sonar"]
      interval: 5s
      timeout: 3s
      retries: 20
volumes:
  sonarqube_data:
  sonarqube_extensions:
  sonarqube_logs:
  sonar_db:
```

After the first `docker pull`, replace `sonarqube:community` with the exact version tag
printed by `docker image inspect sonarqube:community --format '{{index .Config.Labels "org.opencontainers.image.version"}}'`
(e.g. `sonarqube:25.x.y.z-community`), and confirm at
`https://docs.sonarsource.com/sonarqube-community-build/` that Postgres 17 is in the
supported range — if not, use the newest supported major.

- [ ] **Step 6: `sonar-project.properties`** (repo root)

```properties
sonar.projectKey=torobcar
sonar.projectName=Torobcar
sonar.sources=backend,frontend/src
sonar.tests=backend/tests,frontend/src
sonar.test.inclusions=backend/tests/**,frontend/src/**/*.test.ts,frontend/src/**/*.test.tsx
sonar.exclusions=backend/tests/**,backend/db/migrations/versions/**,**/.next/**,**/node_modules/**,**/.venv/**
sonar.cpd.exclusions=backend/tests/**,frontend/src/**/*.test.ts,frontend/src/**/*.test.tsx
sonar.python.version=3.14
sonar.python.coverage.reportPaths=backend/coverage.xml
sonar.javascript.lcov.reportPaths=frontend/coverage/lcov.info
sonar.qualitygate.wait=true
```

- [ ] **Step 7: `.scripts/sonar.sh`** (then `chmod +x .scripts/sonar.sh`)

```bash
#!/usr/bin/env bash
# Coverage for both apps, then a SonarQube scan. Exits non-zero when the quality gate
# fails (sonar.qualitygate.wait=true). Needs SONAR_TOKEN in .env and the server from
# .docker/compose.sonar.yml running.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
: "${SONAR_TOKEN:?set SONAR_TOKEN in .env (SonarQube → My Account → Security)}"

./.scripts/test-db.sh
(cd backend && uv run pytest -q --cov=. --cov-report=xml)
(cd frontend && bun test --coverage --coverage-reporter=lcov --coverage-dir=coverage)

# The scanner sees the repo at /usr/src: make both reports resolve from there.
perl -pi -e 's|<source>.*?</source>|<source>/usr/src/backend</source>|' backend/coverage.xml
perl -pi -e 's|^SF:(?!frontend/)|SF:frontend/|' frontend/coverage/lcov.info

docker run --rm --network torobcar-sonar_default \
  -e SONAR_HOST_URL=http://sonarqube:9000 -e SONAR_TOKEN="$SONAR_TOKEN" \
  -v "$PWD:/usr/src" sonarsource/sonar-scanner-cli
```

- [ ] **Step 8: First scan** (needs the user)

```bash
docker compose -f .docker/compose.sonar.yml up -d
```

Ask the user to: open `http://localhost:9000`, log in with `admin` / `admin`, set a new
password, create a **User Token** (My Account → Security) and put it in `.env` as
`SONAR_TOKEN=`. Never write the token anywhere else. Then:

Run: `./.scripts/sonar.sh`
Expected: `QUALITY GATE STATUS: PASSED` and the project at
`http://localhost:9000/dashboard?id=torobcar`. The first analysis has no "new code"
baseline, so it passes by construction; from the second scan on, the built-in
"Sonar way" gate applies to new code (no new issues, hotspots reviewed, coverage ≥ 80%,
duplication ≤ 3%). Report the overall-code findings (backend **and** the existing
frontend) to the user; fix the backend ones, leave frontend triage to the user.

Stop the server when done: `docker compose -f .docker/compose.sonar.yml stop`.

- [ ] **Step 9: Commit**

```bash
git add .pre-commit-config.yaml .github sonar-project.properties .docker/compose.sonar.yml .scripts/sonar.sh
git commit -m "ci: add lint/test, security and publish workflows plus local SonarQube gate

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 14: Documentation and final verification

**Files:**
- Modify: `CLAUDE.md` (currently untracked — it gets committed here), `README.md`

- [ ] **Step 1: Update `CLAUDE.md`**

Apply each change; keep everything else as is.

- §1 *Project Overview*: replace the **Edge** bullet with "**Edge** — **Traefik v3 reverse proxy** is the single entry point, configured entirely by container labels. It is the *only* service that publishes a host port; backend, frontend, database and Redis are reachable only on the internal network." Add a bullet: "**Cache / LLM** — Redis caches parsed intents and ranked result lists; Pydantic AI turns free text into a typed `SearchIntent` (Gemini in development, any OpenAI-compatible API in production). The LLM never writes SQL." Replace "NGINX routes" with "Traefik routes".
- §2 *Repository Structure*: remove `nginx.Dockerfile` and `nginx/`; add `compose.test.yml`, `compose.sonar.yml`; add `.scripts/test-db.sh`, `ingest.sh`, `sonar.sh`; rename `.pre-commit.config.yml` → `.pre-commit-config.yaml`; add `sonar-project.properties`; under `backend/` add `ranking/` ("pure-Python ranking + price estimator — NO I/O imports"), `ingest/` ("CSV → DB pipeline + CLI"), `llm/` ("Pydantic AI agent, rules fallback, eval"); change `bun.lockb` → `bun.lock`.
- §3 *Tech Stack*: Database row → "PostgreSQL 18 (`pgvector/pgvector:pg18`, `pg_trgm`); UUIDv8 primary keys"; Reverse proxy row → "**Traefik v3** — single entry point, only exposed port"; add rows "Cache | Redis 8 (no persistence)", "LLM | Pydantic AI (`pydantic-ai-slim[google,openai]`)", "Code quality | SonarQube Community Build (local) + Semgrep + Gitleaks".
- §4 *Environment Variables*: add `REDIS_URL`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`, `TEST_DATABASE_URL`, `SONAR_TOKEN`; "through NGINX" → "through Traefik".
- §5 *Common Commands*: add `./.scripts/test-db.sh` ("start the throwaway Postgres that `uv run pytest` needs"), `./.scripts/ingest.sh <csv>`, `./.scripts/sonar.sh`, `uv run python -m llm.eval`; "NGINX, port 80" → "Traefik, port 80".
- §8 *Testing*: add "Repository and API tests need `./.scripts/test-db.sh`. Tests never call a real LLM (`ALLOW_MODEL_REQUESTS = False`). Ranking changes must keep the golden queries in `tests/api/test_search_api.py` green."
- §10 *Pre-commit*: delete the naming caveat; the file is `.pre-commit-config.yaml`.
- §11 *Docker*: replace §11.3 with a Traefik section — the label block from `.docker/compose.yml`, the note about explicit router priorities, and "for TLS add a `websecure` entrypoint and publish 443 on `traefik` only"; replace the §11.4 Compose reference with the real `compose.yml`; state the two loopback-only developer-tool exceptions (`compose.test.yml`, `compose.sonar.yml`).
- §12 *CI/CD*: two images (backend, frontend); backend job uses a `pgvector/pgvector:pg18` service container.
- §13 *Security*: add SonarQube as the third scanner (local, quality gate via `./.scripts/sonar.sh`).
- §14 *Definition of Done*: "All traffic is routed through Traefik; only the `traefik` service publishes a host port"; add "`./.scripts/sonar.sh` passes the quality gate"; add "Ranking changes keep the golden-query suite green".

- [ ] **Step 2: Update `README.md`**

Replace the "there is no backend" note and add a **Backend** section: what it is (one
paragraph), `./.scripts/setup.sh`, `./.scripts/dev.sh`, `./.scripts/ingest.sh assets/<csv>`,
the endpoint table from spec §9, how to run tests (`./.scripts/test-db.sh` then
`cd backend && uv run pytest`), and the LLM note (works without a key via the rules
parser; set `LLM_API_KEY` for Gemini).

- [ ] **Step 3: Refresh the code graph**

The repo has `graphify-out/`, so update the graph now that the codebase changed: run the
`graphify` skill / CLI in update mode for the repo root. `graphify-out/` stays untracked.

- [ ] **Step 4: Definition of Done — run everything**

```bash
./.scripts/test-db.sh
(cd backend && uv run pytest -q && uv run ruff check . && uv run black --check .)
(cd backend && grep -rnE "sqlalchemy|redis|fastapi|pydantic_ai" ranking/ || echo "ranking/ is pure")
(cd backend && grep -rn "os.environ" --include=*.py . | grep -v "^./tests" || echo "no os.environ outside config")
(cd frontend && bun run lint && bun test)
pre-commit run --all-files
gitleaks detect --source . --no-banner
docker compose -f .docker/compose.yml build
```

Expected: `174 passed`; both greps print their "ok" line; no lint, secret or build
failures. If `semgrep` is installed: `semgrep scan --config p/python --config p/security-audit backend` → 0 findings.

Tick the spec's §16 "Done means" list against what you ran; report anything you could
not run (for example the live LLM eval without a key) instead of claiming it.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: document Traefik, Redis, Pydantic AI and the search backend

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
