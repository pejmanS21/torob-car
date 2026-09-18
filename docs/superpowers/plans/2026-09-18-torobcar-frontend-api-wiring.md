# Torobcar Frontend on the Real API (Spec 3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every piece of synthetic data in the Next.js frontend with the real crawled Divar data served by the search-core backend, and add the four backend endpoints the remaining screens need (model stats, catalog suggest, estimates, assistant).

**Architecture:** Backend additions follow the existing layers (endpoint → service → repository; `ranking/` stays pure Python) and reuse `SearchService.rank` for "similar" and for the assistant's search tool. The frontend gets one typed client (`src/lib/api/`), Server Components fetch `API_INTERNAL_URL` on the Compose network, interactive islands call same-origin `/api/v1` through Traefik, and the URL is the single source of truth for search state. Every screen has loading, error and empty states; the UI never invents data.

**Tech Stack:** Python 3.14 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 async · Pydantic AI 2.45 (tool-calling agent) · Next.js 16.3.5 (App Router, Turbopack) · React 19.2 · TypeScript strict · Bun 1.3 · CSS Modules · Leaflet · Traefik v3 · agent-browser (smoke test).

**Spec:** `docs/superpowers/specs/2026-09-18-torobcar-frontend-api-wiring-design.md` — read it before starting. Section numbers below (§) refer to it; "Spec 1" is the search-core spec/plan this builds on.

## Global Constraints

- **Backend:** Python 3.14, **uv** only (`uv run …` from `backend/`); never `pip`/`poetry`. Layered architecture: endpoints hold no business logic, **no SQLAlchemy query outside `repositories/`**, DI only in `dependencies/providers.py`, services receive collaborators through `__init__`, `ranking/` imports no `sqlalchemy`/`redis`/`fastapi`/`pydantic_ai`.
- **User input is validated at the boundary and surfaces as a 422 envelope, never a 500:** request bodies are Pydantic models with explicit bounds; a `ValidationError` raised from user input goes through `errors.invalid_search_error` (Spec 1's final review found one leaking as 500).
- **Named construction for dataclasses built from SQL rows** in every new repository method (positional construction silently corrupts when a column moves).
- Fail loudly: raise from `errors.py`; never return `None` to signal an error. The two deliberate absorptions (LLM outage in `QueryParser`/`AssistantService`, Redis outage in `Cache`) log at WARNING and say so in a comment.
- Money is integer **toman** end to end. The frontend formats with `formatToman` (millions/billions wording identical to the backend's labels).
- Tests never call a real LLM (`ALLOW_MODEL_REQUESTS = False` in `tests/conftest.py`); LLM paths are tested with `FunctionModel`/`TestModel`.
- **Frontend:** **bun** only; TypeScript strict, no `any`; CSS Modules; RTL Persian copy; **no new dependencies** (the spec adds none). Every backend call goes through `src/lib/api/` (`apiGet`/`apiPost`/`useApi`), every fetch is `cache: "no-store"`, screens branch on `ApiError.code`/`status`, never on message text, and never fall back to made-up data.
- **Next.js 16.3.5 is not the Next.js you know** (see `frontend/AGENTS.md`): `params`/`searchParams` are Promises; `error.tsx` receives `retry` (not `reset`); a Server Component that must run per request calls `await connection()` from `next/server` first, otherwise `next build` prerenders it and calls the API at build time. Read `frontend/node_modules/next/dist/docs/01-app/` before touching a route.
- **Frontend Tasks 7–11 leave `bunx tsc --noEmit` red** in the screens that are not yet migrated (each task lists the exact files still allowed to fail). `bun test` must pass at every task; Task 12 must bring `tsc` and `bun run lint` to zero findings.
- Traefik is the only service that publishes a host port. New rate-limited routers carry an **explicit priority above the general `api` router (50)** — Traefik otherwise ranks by rule length.
- `git add` explicit paths only — never `git add -A`/`git add .` — the repo has untracked `prototype/`, `brag-output/`, `graphify-out/`, `assets/`, `frontend/AGENTS.md`, `frontend/CLAUDE.md` that must stay untracked. Never create or commit a real `.env`.
- Conventional commits; every commit message ends with exactly `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>` and the implementer verifies it with `git log -1 --format='%(trailers)'`. Pre-commit hooks run on commit — let them pass, never `--no-verify`.
- Every task states its **exact cumulative test count**. Backend starts at **178**; frontend starts at **38**.
- A backend task is done only when `uv run pytest`, `uv run ruff check .` and `uv run black --check .` pass (the throwaway Postgres from `./.scripts/test-db.sh` must be up). A frontend task is done only when `bun test` passes (plus `tsc`/`lint` where the task says so).

## Facts verified while writing this plan (2026-09-18)

Every code block in this plan was executed in a throwaway worktree of `feat/frontend-api-wiring`: the backend suite went from 178 to **225** tests, the frontend from 38 to **27** (after deleting the synthetic-data tests), and each task's count below was measured at that task's commit.

- **Pydantic AI 2.45** tool agents: `Agent(model, deps_type=…, output_type=…, instructions=…, retries=…)`; tools are `@agent.tool async def name(context: RunContext[Deps], …)`; in a `FunctionModel` script the second call sees the tool result as a `ToolReturnPart` in `messages`; provider failures are `pydantic_ai.exceptions.ModelAPIError(model_name, message)` (a plain `RuntimeError` from the model is *not* absorbed — by design).
- **Next.js 16.3.5**: `next build` **prerenders `app/page.tsx` at build time** and fails the Docker build because the API is unreachable there — fixed with `await connection()` (Deviation 5). The final build reports `ƒ /`, `ƒ /listing/[id]`, `ƒ /model/[model]` as dynamic and `/results`, `/compare`, `/estimate` as static shells. `error.tsx` receives `retry`. React 19.2.8 exports `useEffectEvent`, which is what lets `useApi` keep the latest fetcher without tripping `react-hooks/refs`.
- **`bun run build` is not used** — `.docker/frontend.Dockerfile` already runs `node node_modules/.bin/next build` (Bun segfaults under Next 16); run the same locally when you need a production build.
- **End-to-end smoke:** `.scripts/smoke.sh` passed all nine steps (home stats → NL search → near-miss divider → listing (no phone numbers) → similar → compare two → estimate → chat → 422 message) against the new backend serving the seeded fixture DB and `next dev` on a local port. Both Docker images build from the final tree. `docker compose config` accepts the new Traefik labels.
- **Real data** (running stack, 14,652 ads): the home example queries return results — «پژو ۲۰۶ تیپ ۲ تهران» 500 (44 exact), «پراید زیر ۳۰۰ میلیون» 224, «دنا پلاس اتومات» 146, «سمند مدل ۹۵ به بالا مشهد» 290. Light-car listings mostly have empty `attributes`; motorcycles carry `حجم موتور`, `نوع کلاچ`, `نوع استارت`, `وضعیت فنی موتور`, `وضعیت سند و مدارک`.
- **Phone masking** regex verified on Persian/ASCII/Arabic-Indic digits, spaces/dashes, `+98` and landlines, and leaves prices, km, years and 17-digit VINs untouched.
- **Suggest threshold 0.3** (`word_similarity`) resolves the typo «پژو 206 تیب» to «پژو 206» on the fixture DB; the resolver's 0.6 is too strict for half-typed input.
- The fixture CSV (`backend/tests/fixtures/listings_sample.csv`) already blanks descriptions and rounds coordinates, so the JSON fixtures captured from it hold no personal data.

## Deliberate deviations from the spec

Each was found by running the code. Items marked **A#** are recorded in the spec's §8 "Amendments found while planning".

1. **A1** — `Facets` also gains `model_count` (§3.5 lists only `data_as_of`): the home page shows «N مدل», and `facets.models` is capped at 60.
2. **A2** — `/catalog/suggest` rows are catalog entries (trims), so an empty `q` returns the 10 largest **trims** of the category, not models: the estimate form needs a trim to post.
3. **A3** — The card meta line is year · km · city/district · gearbox; engine cc for motorcycles appears on the listing page specs grid only (`attributes` are detail-only; §4.3 asked for it on cards).
4. **A4** — `POST /estimates` answers 422 `invalid_search` for an unknown trim (§3.3 names only `no_comparables`), and validates `year` to 1301…current Jalali year so the "similar" intent (year ± 1) can never fail `SearchIntent`'s own bounds.
5. **A5** — Server pages that fetch per request call `await connection()` first (Next 16 prerenders otherwise, and the Docker build fails).
6. **A6** — New setting `ASSISTANT_TIMEOUT_SECONDS=20`: a tool-calling run needs two provider round trips, so the 4 s intent timeout would always fall back to rules.
7. **A7** — The rules-path assistant ranks exact matches before near-misses when picking its top 3 (on the fixture DB a Peugeot 405 with a higher deal score topped a «۲۰۶» reply).
8. **A8** — The filter sheet uses preset caps (`<select>`) for price and km instead of sliders: real prices span 10 M to 10 B toman.
9. `EstimateRequest.body_condition` is accepted and ignored by the estimate — the ingest estimator prices body condition only into the deal score, which `/estimates` does not return.
10. Facet scoping uses a new `ListingRepository.count_by_city(category, limit)` (GROUP BY, cached under `data_version`); `CityRepository.list_top` is deleted.
11. Card `lat`/`lng` fall back to the city centroid so map pins never disappear for listings without coordinates.
12. `PriceAlert.threshold` is `price_max` when set, otherwise the median of the loaded exact matches rounded to 10 M toman.
13. Frontend `SortKey` is the API enum (`relevance/deal/price/km/newest`); the old `score/new` values are gone.
14. `frontend/src/lib/labels.ts` (Persian names of the API enums) is a new module not named in §4.3.
15. `.docker/frontend.Dockerfile` drops `ENV NEXT_PUBLIC_API_URL`; `example.env` replaces it with `API_INTERNAL_URL`.

**Not verified while planning:** Traefik actually routing `/api/v1/assistant` and `/api/v1/estimates` through the new rate-limited router on the live stack (the running stack was not restarted; the labels parse and mirror `api-search`), the LLM assistant path against a real provider (no key; covered by `FunctionModel`), and the smoke script through Traefik at `http://localhost` (it ran against a local `next dev` with a scratch rewrite). Task 13 carries the explicit checks.

## File map

````
backend/
  core/phone.py                       mask_phone_numbers (Task 1)
  schemas/listing.py (+lat, lng, gearbox, fuel, body_condition, insurance_months on ListingCard)
  schemas/facets.py (+model_count, data_as_of) · schemas/model_stats.py · schemas/catalog.py · schemas/estimate.py · schemas/assistant.py
  ranking/model_stats.py              summarize_model (pure)         (Task 2)
  ranking/estimator.py                +EstimateQuery, SingleEstimate, estimate_for (Task 4)
  repositories/listing_repository.py  +count_by_city, count_by_category(category), load_model_rows, load_estimator_inputs(category)
  repositories/catalog_repository.py  +count_models, find_model, suggest, find_trim, _trim_similarity
  repositories/city_repository.py     −list_top
  services/listing_views.py (+fields, masking) · facet_service.py · model_stats_service.py · catalog_service.py · estimate_service.py · assistant_service.py
  llm/assistant_agent.py              AssistantDeps, AssistantReply, build_prompt, build_assistant_agent (Task 5)
  api/v1/endpoints/models.py · catalog.py · estimates.py · assistant.py · router.py
  dependencies/providers.py           +get_model_stats_service, get_catalog_service, get_estimate_service, get_assistant_agent, get_assistant_service
  errors.py                           +ModelNotFoundError, NoComparablesError
  enums.py (+ChatRole) · core/config.py (+assistant_timeout_seconds)
  tests/core/test_phone.py · tests/ranking/test_model_stats.py · tests/api/test_models_api.py · test_catalog_api.py · test_estimates_api.py · test_assistant_api.py · tests/services/test_assistant_service.py
  tests/fixtures/capture_api_fixtures.py   writes frontend/src/lib/api/__fixtures__/*.json (Task 6)
frontend/src/
  lib/api/types.ts · base.ts · client.ts · useApi.ts · client.test.ts · __fixtures__/*.json   (Task 6)
  lib/theme.ts · labels.ts · types.ts · format.ts · pricing.ts · view.ts · compare.ts · specs.ts · search.ts (+ *.test.ts)   (Task 7)
  state/AppState.tsx (v2) · components/ChatPanel · AlertsDropdown · ListingCard · ListingRow · MiniListing · VerdictBadge · BreakdownCard · ErrorBanner · Skeleton · Footer   (Task 8)
  app/page.tsx · app/error.tsx · app/loading.tsx · app/results/page.tsx · components/ResultsScreen · FiltersPanel · ResultsToolbar · ModelCard · ParsedChips · MapCard · ListingsMap · HomeSearch   (Task 9)
  app/listing/[id]/{page,loading}.tsx · components/ListingScreen · PriceCard · SummaryCard   (Task 10)
  app/model/[model]/{page,loading}.tsx · components/ModelScreen · PriceHistogram · TrimBars   (Task 11)
  app/compare/page.tsx · app/estimate/page.tsx · components/CompareTable · EstimateForm · EstimateResultCard   (Task 12)
  DELETED: lib/listings.ts, catalog.ts, estimate.ts, modelStats.ts, assistant.ts (+ their tests), components/SellerAssessmentCard, IssueBars
.docker/compose.yml (+api-assistant router) · .docker/frontend.Dockerfile · example.env · .scripts/smoke.sh · README.md · CLAUDE.md   (Task 13)
````

**How to read the tasks:** code blocks are final and already formatted (Black for Python); copy them verbatim. **New files are given whole; modified files are given as unified diffs** against the previous task's state — apply the hunks by hand, or paste the block into a file and run `git apply <file>` from the repo root. `uv run …` runs from `backend/`, `bun …`/`bunx …` from `frontend/`, `git` from the repo root. Start the test database once: `./.scripts/test-db.sh`.

---

### Task 1: Card fields, phone masking and category-scoped facets

**Files:**
- Create: `backend/core/phone.py`
- Modify: `backend/dependencies/providers.py`
- Modify: `backend/repositories/catalog_repository.py`
- Modify: `backend/repositories/city_repository.py`
- Modify: `backend/repositories/listing_repository.py`
- Modify: `backend/schemas/facets.py`
- Modify: `backend/schemas/listing.py`
- Modify: `backend/services/facet_service.py`
- Modify: `backend/services/listing_views.py`
- Modify: `backend/tests/api/test_search_api.py`
- Create: `backend/tests/core/test_phone.py`
- Modify: `backend/tests/services/test_search_service.py`

**Interfaces:**
- Consumes: `models.Listing` (incl. `city.lat/lng`), `ranking.weights.CHEAP_DIFF_PCT`, the `api` fixture (seeded test DB, no LLM).
- Produces: `core.phone.mask_phone_numbers(text: str) -> str` and `PHONE_PLACEHOLDER`; `ListingCard` fields `lat`, `lng`, `gearbox`, `fuel`, `body_condition`, `insurance_months` (so `ListingDetail` no longer redeclares them); `Facets.model_count: int`, `Facets.data_as_of: datetime | None`; `ListingRepository.count_by_category(category: Category | None = None)`, `ListingRepository.count_by_city(category: Category | None, limit: int) -> list[CityCount]` (`CityCount(name, listing_count)`); `CatalogRepository.count_models(category: Category | None) -> int`; `FacetService(listings, catalog, cache, cache_ttl_seconds)` (no `CityRepository`).

Spec §3.5. `ListingDetail.description` is masked in `services/listing_views.to_detail` — stored data is unchanged. Card coordinates fall back to the city centroid (Deviation 11). `CityRepository.list_top` is deleted; its only caller was `FacetService` (Deviation 10). The stub listing in `tests/services/test_search_service.py` gains the new attributes so `to_card` keeps working with `SimpleNamespace` doubles.

- [ ] **Step 1: Write the failing tests**

Modify `backend/tests/api/test_search_api.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/tests/api/test_search_api.py b/backend/tests/api/test_search_api.py
index 275fa62..1a7355f 100644
--- a/backend/tests/api/test_search_api.py
+++ b/backend/tests/api/test_search_api.py
@@ -127,3 +127,23 @@ async def test_second_identical_search_is_served_from_the_cache(
     body = await search(api, q="۲۰۶ تهران", page=2)
     assert set(cache.values) == keys_after_first  # nothing new was computed
     assert body["page"] == 2
+
+
+async def test_cards_carry_map_and_spec_fields(api: AsyncClient) -> None:
+    item = (await search(api, q="۲۰۶ تیپ ۲ تهران"))["items"][0]
+    assert {"lat", "lng", "gearbox", "fuel", "body_condition"} <= set(item)
+    assert "insurance_months" in item
+    assert item["lat"] is not None and item["gearbox"] == "manual"
+
+
+async def test_facets_are_scoped_by_category_and_dated(api: AsyncClient) -> None:
+    everything = (await api.get("/api/v1/facets")).json()
+    scoped = await api.get("/api/v1/facets", params={"category": "motorcycle"})
+    motorcycles = scoped.json()
+    assert everything["data_as_of"] and motorcycles["data_as_of"]
+    assert everything["model_count"] > motorcycles["model_count"] > 0
+    assert set(motorcycles["categories"]) == {"motorcycle"}
+    assert len(everything["categories"]) == 5
+    assert motorcycles["cities"][0]["count"] <= everything["cities"][0]["count"]
+    assert all(m["count"] <= 120 for m in motorcycles["models"])
+    assert sum(c["count"] for c in motorcycles["cities"]) == 120
````

Create `backend/tests/core/test_phone.py`:

````python
import pytest

from core.phone import PHONE_PLACEHOLDER, mask_phone_numbers


@pytest.mark.parametrize(
    "raw",
    [
        "تماس ۰۹۱۲۳۴۵۶۷۸۹ فقط",
        "تماس 09123456789 فقط",
        "تماس 0912 345 67 89 فقط",
        "تماس 0912-345-6789 فقط",
        "تماس ٠٩١٢٣٤٥٦٧٨٩ فقط",
        "تماس +989123456789 فقط",
        "تماس 02122334455 فقط",  # landline
    ],
)
def test_phone_numbers_are_replaced(raw: str) -> None:
    assert mask_phone_numbers(raw) == f"تماس {PHONE_PLACEHOLDER} فقط"


@pytest.mark.parametrize(
    "raw",
    [
        "قیمت ۹۷۰,۰۰۰,۰۰۰ تومان",
        "قیمت 1,200,000,000 تومان",
        "کارکرد ۲۷۰۰۰ کیلومتر",
        "مدل ۱۳۹۷ تیپ ۲",
        "شاسی 12345678901234567",  # 17 digits: not a phone
    ],
)
def test_ordinary_numbers_are_untouched(raw: str) -> None:
    assert mask_phone_numbers(raw) == raw


def test_every_number_in_a_description_is_masked() -> None:
    masked = mask_phone_numbers("۰۹۱۲۱۱۱۱۱۱۱ یا ۰۹۳۵۲۲۲۲۲۲۲")
    assert masked == f"{PHONE_PLACEHOLDER} یا {PHONE_PLACEHOLDER}"
````

Modify `backend/tests/services/test_search_service.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/tests/services/test_search_service.py b/backend/tests/services/test_search_service.py
index 0d82c02..ae2dacc 100644
--- a/backend/tests/services/test_search_service.py
+++ b/backend/tests/services/test_search_service.py
@@ -29,11 +29,17 @@ def make_listing(listing_id: uuid.UUID) -> SimpleNamespace:
         title="پژو ۲۰۶",
         category=Category.LIGHT,
         catalog=None,
-        city=SimpleNamespace(name="تهران"),
+        city=SimpleNamespace(name="تهران", lat=35.7, lng=51.4),
         year=1398,
         km=60_000,
         price=800_000_000,
         district=None,
+        lat=None,
+        lng=None,
+        gearbox=None,
+        fuel=None,
+        body_condition=None,
+        insurance_months=None,
         thumbnail_urls=[],
         image_urls=[],
         posted_at=NOW,
````

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q`
Expected: collection error `ModuleNotFoundError: No module named 'core.phone'`.

- [ ] **Step 3: Implement**

Create `backend/core/phone.py`:

````python
"""Masks sellers' phone numbers in free text (spec 3 §3.5). Stored data is never
changed; only what leaves the API through `ListingDetail.description`."""

import re

PHONE_PLACEHOLDER = "شماره در آگهی دیوار"

_DIGIT = r"[0-9۰-۹٠-٩]"
_SEPARATOR = r"[\s\-.]{0,2}"
_PREFIX = r"(?:\+?(?:98|۹۸|٩٨)|[0۰٠])"
# An Iranian number is the prefix (0 or +98) followed by ten more digits, in any digit
# script, with optional spaces/dashes/dots between them: mobiles (09xx…) and landlines
# (0xx…) alike. Digit boundaries on both sides keep prices, km and years untouched.
_PHONE = re.compile(
    rf"(?<!{_DIGIT}){_PREFIX}{_SEPARATOR}(?:{_DIGIT}{_SEPARATOR}){{9}}{_DIGIT}(?!{_DIGIT})"
)


def mask_phone_numbers(text: str) -> str:
    return _PHONE.sub(PHONE_PLACEHOLDER, text)
````

Modify `backend/dependencies/providers.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/dependencies/providers.py b/backend/dependencies/providers.py
index 3cb9cb5..40cffc0 100644
--- a/backend/dependencies/providers.py
+++ b/backend/dependencies/providers.py
@@ -87,7 +87,6 @@ def get_facet_service(
     return FacetService(
         ListingRepository(session),
         CatalogRepository(session),
-        CityRepository(session),
         cache,
         settings.search_cache_ttl_seconds,
     )
````

Modify `backend/repositories/catalog_repository.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/repositories/catalog_repository.py b/backend/repositories/catalog_repository.py
index a10fbcb..4319159 100644
--- a/backend/repositories/catalog_repository.py
+++ b/backend/repositories/catalog_repository.py
@@ -104,6 +104,13 @@ class CatalogRepository:
         found = await self._session.execute(statement)
         return [CatalogMatch(*row) for row in found]

+    async def count_models(self, category: Category | None) -> int:
+        distinct = select(VehicleCatalog.model).distinct()
+        if category is not None:
+            distinct = distinct.where(VehicleCatalog.category == category)
+        statement = select(func.count()).select_from(distinct.subquery())
+        return await self._session.scalar(statement) or 0
+
     async def list_top_models(
         self, category: Category | None, limit: int
     ) -> list[ModelCount]:
````

Modify `backend/repositories/city_repository.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/repositories/city_repository.py b/backend/repositories/city_repository.py
index 840d971..98bc225 100644
--- a/backend/repositories/city_repository.py
+++ b/backend/repositories/city_repository.py
@@ -63,9 +63,3 @@ class CityRepository:
             select(City.name).order_by(City.listing_count.desc())
         )
         return list(found)
-
-    async def list_top(self, limit: int) -> list[City]:
-        found = await self._session.scalars(
-            select(City).order_by(City.listing_count.desc(), City.name).limit(limit)
-        )
-        return list(found)
````

Modify `backend/repositories/listing_repository.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/repositories/listing_repository.py b/backend/repositories/listing_repository.py
index a5453bc..604b91f 100644
--- a/backend/repositories/listing_repository.py
+++ b/backend/repositories/listing_repository.py
@@ -23,6 +23,12 @@ MIN_TEXT_SIMILARITY = 0.3
 _IMMUTABLE_COLUMNS = frozenset({"id", "token"})


+@dataclass(frozen=True, slots=True)
+class CityCount:
+    name: str
+    listing_count: int
+
+
 @dataclass(frozen=True, slots=True)
 class CandidateFilter:
     """Absolute bounds, already widened by the ranking tolerances (spec §7.3). A
@@ -103,12 +109,31 @@ class ListingRepository:
             await self._session.scalar(select(func.count()).select_from(Listing)) or 0
         )

-    async def count_by_category(self) -> dict[Category, int]:
-        found = await self._session.execute(
-            select(Listing.category, func.count()).group_by(Listing.category)
-        )
+    async def count_by_category(
+        self, category: Category | None = None
+    ) -> dict[Category, int]:
+        statement = select(Listing.category, func.count()).group_by(Listing.category)
+        if category is not None:
+            statement = statement.where(Listing.category == category)
+        found = await self._session.execute(statement)
         return {category: total for category, total in found}

+    async def count_by_city(
+        self, category: Category | None, limit: int
+    ) -> list[CityCount]:
+        total = func.count().label("total")
+        statement = (
+            select(City.name, total)
+            .join(Listing, Listing.city_id == City.id)
+            .group_by(City.name)
+            .order_by(total.desc(), City.name)
+            .limit(limit)
+        )
+        if category is not None:
+            statement = statement.where(Listing.category == category)
+        found = await self._session.execute(statement)
+        return [CityCount(name=name, listing_count=count) for name, count in found]
+
     async def get_by_id(self, listing_id: uuid.UUID) -> Listing | None:
         found = await self.get_by_ids([listing_id])
         return found[0] if found else None
````

Modify `backend/schemas/facets.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/schemas/facets.py b/backend/schemas/facets.py
index f25515f..d5c20ba 100644
--- a/backend/schemas/facets.py
+++ b/backend/schemas/facets.py
@@ -1,3 +1,5 @@
+from datetime import datetime
+
 from pydantic import BaseModel

 from enums import Category
@@ -18,3 +20,5 @@ class Facets(BaseModel):
     categories: dict[Category, int]
     models: list[ModelFacet]
     cities: list[FacetCount]
+    model_count: int
+    data_as_of: datetime | None
````

Modify `backend/schemas/listing.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/schemas/listing.py b/backend/schemas/listing.py
index 4be0569..5dbd715 100644
--- a/backend/schemas/listing.py
+++ b/backend/schemas/listing.py
@@ -4,7 +4,7 @@ from typing import Any

 from pydantic import BaseModel

-from enums import Category, EstimateBasis, Fuel, Gearbox, Verdict
+from enums import BodyCondition, Category, EstimateBasis, Fuel, Gearbox, Verdict


 class ListingCard(BaseModel):
@@ -20,6 +20,12 @@ class ListingCard(BaseModel):
     price: int | None
     city: str
     district: str | None
+    lat: float | None
+    lng: float | None
+    gearbox: Gearbox | None
+    fuel: Fuel | None
+    body_condition: BodyCondition | None
+    insurance_months: int | None
     thumbnail_url: str | None
     posted_at: datetime | None
     est_price: int | None
@@ -43,12 +49,7 @@ class ListingDetail(ListingCard):
     url: str
     description: str
     image_urls: list[str]
-    lat: float | None
-    lng: float | None
-    gearbox: Gearbox | None
-    fuel: Fuel | None
     color: str | None
-    insurance_months: int | None
     is_dealer: bool
     attributes: dict[str, Any]
     price_breakdown: PriceBreakdown
````

Modify `backend/services/facet_service.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/services/facet_service.py b/backend/services/facet_service.py
index 4021f46..6866ac9 100644
--- a/backend/services/facet_service.py
+++ b/backend/services/facet_service.py
@@ -1,7 +1,6 @@
 from core.cache import Cache
 from enums import Category
 from repositories.catalog_repository import CatalogRepository
-from repositories.city_repository import CityRepository
 from repositories.listing_repository import ListingRepository
 from schemas.facets import FacetCount, Facets, ModelFacet

@@ -14,13 +13,11 @@ class FacetService:
         self,
         listings: ListingRepository,
         catalog: CatalogRepository,
-        cities: CityRepository,
         cache: Cache,
         cache_ttl_seconds: int,
     ) -> None:
         self._listings = listings
         self._catalog = catalog
-        self._cities = cities
         self._cache = cache
         self._cache_ttl_seconds = cache_ttl_seconds

@@ -37,9 +34,9 @@ class FacetService:

     async def _build(self, category: Category | None) -> Facets:
         models = await self._catalog.list_top_models(category, TOP_MODELS)
-        cities = await self._cities.list_top(TOP_CITIES)
+        cities = await self._listings.count_by_city(category, TOP_CITIES)
         return Facets(
-            categories=await self._listings.count_by_category(),
+            categories=await self._listings.count_by_category(category),
             models=[
                 ModelFacet(brand=item.brand, model=item.model, count=item.listing_count)
                 for item in models
@@ -47,4 +44,6 @@ class FacetService:
             cities=[
                 FacetCount(value=city.name, count=city.listing_count) for city in cities
             ],
+            model_count=await self._catalog.count_models(category),
+            data_as_of=await self._listings.newest_fetched_at(),
         )
````

Modify `backend/services/listing_views.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/services/listing_views.py b/backend/services/listing_views.py
index 6f6043f..b784bd0 100644
--- a/backend/services/listing_views.py
+++ b/backend/services/listing_views.py
@@ -1,5 +1,6 @@
 """ORM Listing → API schemas. ORM objects never leave the service layer untranslated."""

+from core.phone import mask_phone_numbers
 from enums import Verdict
 from models.listing import Listing
 from ranking.types import RankedListing
@@ -33,6 +34,13 @@ def _card_fields(listing: Listing) -> dict[str, object]:
         "price": listing.price,
         "city": listing.city.name,
         "district": listing.district,
+        # Map pins: a listing without coordinates sits on its city's centroid.
+        "lat": listing.lat if listing.lat is not None else listing.city.lat,
+        "lng": listing.lng if listing.lng is not None else listing.city.lng,
+        "gearbox": listing.gearbox,
+        "fuel": listing.fuel,
+        "body_condition": listing.body_condition,
+        "insurance_months": listing.insurance_months,
         "thumbnail_url": thumbnails[0] if thumbnails else None,
         "posted_at": listing.posted_at,
         "est_price": listing.est_price,
@@ -74,14 +82,9 @@ def to_detail(listing: Listing) -> ListingDetail:
     return ListingDetail(
         **_card_fields(listing),
         url=listing.url,
-        description=listing.description,
+        description=mask_phone_numbers(listing.description),
         image_urls=listing.image_urls,
-        lat=listing.lat,
-        lng=listing.lng,
-        gearbox=listing.gearbox,
-        fuel=listing.fuel,
         color=listing.color,
-        insurance_months=listing.insurance_months,
         is_dealer=listing.is_dealer,
         attributes=listing.attributes,
         price_breakdown=_price_breakdown(listing),
````

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run black --check .`
Expected: `193 passed` (178 + 13 phone + 2 API), no lint or format findings.

- [ ] **Step 5: Commit**

From the repo root (`cd ..`), stage explicit paths only (never `git add -A`):

````bash
git add backend/core/phone.py backend/dependencies/providers.py backend/repositories/catalog_repository.py backend/repositories/city_repository.py backend/repositories/listing_repository.py backend/schemas/facets.py backend/schemas/listing.py backend/services/facet_service.py backend/services/listing_views.py backend/tests/api/test_search_api.py backend/tests/core/test_phone.py backend/tests/services/test_search_service.py
git commit -m "feat(api): add card map/spec fields, phone masking and scoped facets

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git log -1 --format='%(trailers)'   # must print exactly: Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
````

---

### Task 2: Model stats endpoint

**Files:**
- Create: `backend/api/v1/endpoints/models.py`
- Modify: `backend/api/v1/router.py`
- Modify: `backend/dependencies/providers.py`
- Modify: `backend/errors.py`
- Create: `backend/ranking/model_stats.py`
- Modify: `backend/repositories/catalog_repository.py`
- Modify: `backend/repositories/listing_repository.py`
- Create: `backend/schemas/model_stats.py`
- Create: `backend/services/model_stats_service.py`
- Create: `backend/tests/api/test_models_api.py`
- Create: `backend/tests/ranking/test_model_stats.py`

**Interfaces:**
- Consumes: `services.listing_views.to_card`, `core.text.normalize_persian`, `ListingRepository.get_by_ids`.
- Produces: `ranking.model_stats.ModelRow(listing_id, trim, year, price, deal_score)`, `HistogramBucket(low, high, count)`, `TrimStat(trim, count, price_median)`, `ModelSummary`, `summarize_model(rows, top_deals) -> ModelSummary`; `schemas.model_stats.ModelStats` (+`HistogramBucketRead`, `TrimStatRead`); `errors.ModelNotFoundError(model)` → 404 `model_not_found`; `CatalogRepository.find_model(model) -> CatalogModel | None` (`CatalogModel(brand, model, category)`); `ListingRepository.load_model_rows(model) -> list[ModelRow]` (suspect prices → `None`); `ModelStatsService(catalog, listings).get_stats(model) -> ModelStats`; `GET /api/v1/models/{model}/stats`; provider `get_model_stats_service`.

Spec §3.1. `ranking/model_stats.py` is pure Python: the histogram is 8 equal-width buckets between the 5th and 95th percentile (`statistics.quantiles(n=20)`), out-of-range prices land in the edge buckets so counts always sum to the priced count; suspect/NULL prices are excluded (`price=None`). Trims are sorted by count desc, then name; top deals by `deal_score` desc. The path parameter is normalised (`پژو ۲۰۶` resolves like `پژو 206`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/api/test_models_api.py`:

````python
"""GET /models/{model}/stats on the seeded fixture DB."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.db


async def test_model_stats_summarise_the_market(api: AsyncClient) -> None:
    response = await api.get("/api/v1/models/پژو ۲۰۶/stats")  # Persian digits resolve
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["model"] == "پژو 206" and body["brand"] == "پژو"
    assert body["category"] == "light" and body["count"] > 20
    assert body["year_min"] <= body["year_max"]
    assert body["price_min"] <= body["price_median"] <= body["price_max"]
    assert len(body["histogram"]) == 8
    priced = sum(bucket["count"] for bucket in body["histogram"])
    assert 0 < priced <= body["count"]
    counts = [trim["count"] for trim in body["trims"]]
    assert counts == sorted(counts, reverse=True) and sum(counts) == body["count"]
    scores = [card["deal_score"] for card in body["top_deals"]]
    assert 0 < len(scores) <= 6 and scores == sorted(scores, reverse=True)
    assert all(card["model"] == "پژو 206" for card in body["top_deals"])


async def test_unknown_model_is_a_404_envelope(api: AsyncClient) -> None:
    response = await api.get("/api/v1/models/بوگاتی/stats")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"
````

Create `backend/tests/ranking/test_model_stats.py`:

````python
import uuid

from ranking.model_stats import HISTOGRAM_BUCKETS, ModelRow, summarize_model


def make_row(price: int | None, **overrides: object) -> ModelRow:
    fields: dict[str, object] = {
        "listing_id": uuid.uuid4(),
        "trim": "پژو 206 تیپ ۲",
        "year": 1398,
        "price": price,
        "deal_score": 70,
    }
    return ModelRow(**{**fields, **overrides})


def test_histogram_counts_sum_to_the_priced_count_and_ignore_unpriced() -> None:
    rows = [make_row(price) for price in range(500, 1500, 10)]  # 100 priced rows
    rows += [make_row(None), make_row(None)]  # missing or suspect prices
    summary = summarize_model(rows, top_deals=6)
    assert summary.count == 102
    assert len(summary.histogram) == HISTOGRAM_BUCKETS
    assert sum(bucket.count for bucket in summary.histogram) == 100
    assert summary.price_min == 500 and summary.price_max == 1490
    assert summary.price_median == 995


def test_outliers_fall_into_the_edge_buckets() -> None:
    rows = [make_row(price) for price in range(1000, 1100)] + [
        make_row(1),
        make_row(10_000_000),
    ]
    histogram = summarize_model(rows, top_deals=6).histogram
    assert histogram[0].count >= 1 and histogram[-1].count >= 1
    assert sum(bucket.count for bucket in histogram) == 102
    assert all(
        b.high - b.low == histogram[0].high - histogram[0].low for b in histogram
    )


def test_trims_are_sorted_by_count_with_their_own_median() -> None:
    rows = [make_row(800, trim="تیپ ۵")] * 3 + [make_row(600, trim="تیپ ۲")]
    trims = summarize_model(rows, top_deals=6).trims
    assert [(trim.trim, trim.count) for trim in trims] == [("تیپ ۵", 3), ("تیپ ۲", 1)]
    assert trims[0].price_median == 800


def test_top_deals_are_the_highest_deal_scores() -> None:
    best = make_row(700, deal_score=95)
    rows = [make_row(800, deal_score=40), best, make_row(900, deal_score=None)]
    summary = summarize_model(rows, top_deals=1)
    assert summary.top_deal_ids == (best.listing_id,)


def test_a_single_priced_row_still_produces_eight_buckets() -> None:
    summary = summarize_model([make_row(800)], top_deals=6)
    assert len(summary.histogram) == HISTOGRAM_BUCKETS
    assert summary.histogram[0].count == 1


def test_no_rows_means_no_numbers() -> None:
    summary = summarize_model([], top_deals=6)
    assert summary.count == 0 and summary.price_median is None
    assert summary.histogram == () and summary.trims == ()
````

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q`
Expected: collection error `ModuleNotFoundError: No module named 'ranking.model_stats'`.

- [ ] **Step 3: Implement**

Create `backend/api/v1/endpoints/models.py`:

````python
from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.providers import get_model_stats_service
from schemas.model_stats import ModelStats
from services.model_stats_service import ModelStatsService

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/{model}/stats", response_model=ModelStats)
async def read_model_stats(
    service: Annotated[ModelStatsService, Depends(get_model_stats_service)],
    model: str,
) -> ModelStats:
    return await service.get_stats(model)
````

Modify `backend/api/v1/router.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/api/v1/router.py b/backend/api/v1/router.py
index ab28eab..99a0536 100644
--- a/backend/api/v1/router.py
+++ b/backend/api/v1/router.py
@@ -2,9 +2,10 @@

 from fastapi import APIRouter

-from api.v1.endpoints import facets, listings, search
+from api.v1.endpoints import facets, listings, models, search

 router = APIRouter()
 router.include_router(search.router)
 router.include_router(listings.router)
 router.include_router(facets.router)
+router.include_router(models.router)
````

Modify `backend/dependencies/providers.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/dependencies/providers.py b/backend/dependencies/providers.py
index 40cffc0..b55a12e 100644
--- a/backend/dependencies/providers.py
+++ b/backend/dependencies/providers.py
@@ -22,6 +22,7 @@ from schemas.search import SearchIntent
 from services.facet_service import FacetService
 from services.intent_resolver import IntentResolver
 from services.listing_service import ListingService
+from services.model_stats_service import ModelStatsService
 from services.query_parser import QueryParser
 from services.search_service import SearchService

@@ -92,5 +93,9 @@ def get_facet_service(
     )


+def get_model_stats_service(session: SessionDep) -> ModelStatsService:
+    return ModelStatsService(CatalogRepository(session), ListingRepository(session))
+
+
 def get_health_repository(session: SessionDep) -> HealthRepository:
     return HealthRepository(session)
````

Modify `backend/errors.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/errors.py b/backend/errors.py
index 5594b21..8613c12 100644
--- a/backend/errors.py
+++ b/backend/errors.py
@@ -34,6 +34,14 @@ class ListingNotFoundError(AppError):
         super().__init__("Listing not found", {"listing_id": str(listing_id)})


+class ModelNotFoundError(AppError):
+    status_code = 404
+    code = "model_not_found"
+
+    def __init__(self, model: str) -> None:
+        super().__init__("Model not found", {"model": model})
+
+
 class InvalidSearchError(AppError):
     status_code = 422
     code = "invalid_search"
````

Create `backend/ranking/model_stats.py`:

````python
"""Per-model market summary for GET /models/{model}/stats. Pure Python, no I/O."""

import math
import statistics
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

HISTOGRAM_BUCKETS = 8
PERCENTILE_STEPS = 20  # quantiles(n=20) → cut points at every 5 %
LOW_PERCENTILE_INDEX = 0  # 5th percentile
HIGH_PERCENTILE_INDEX = 18  # 95th percentile
MIN_ROWS_FOR_PERCENTILES = 2


@dataclass(frozen=True, slots=True)
class ModelRow:
    listing_id: uuid.UUID
    trim: str
    year: int | None
    price: int | None  # None when missing OR flagged price_suspect
    deal_score: int | None


@dataclass(frozen=True, slots=True)
class HistogramBucket:
    low: int
    high: int
    count: int


@dataclass(frozen=True, slots=True)
class TrimStat:
    trim: str
    count: int
    price_median: int | None


@dataclass(frozen=True, slots=True)
class ModelSummary:
    count: int
    year_min: int | None
    year_max: int | None
    price_median: int | None
    price_min: int | None
    price_max: int | None
    histogram: tuple[HistogramBucket, ...]
    trims: tuple[TrimStat, ...]
    top_deal_ids: tuple[uuid.UUID, ...]


def _percentile_bounds(prices: Sequence[int]) -> tuple[int, int]:
    if len(prices) < MIN_ROWS_FOR_PERCENTILES:
        return prices[0], prices[0]
    cuts = statistics.quantiles(prices, n=PERCENTILE_STEPS)
    return round(cuts[LOW_PERCENTILE_INDEX]), round(cuts[HIGH_PERCENTILE_INDEX])


def _histogram(prices: Sequence[int]) -> tuple[HistogramBucket, ...]:
    """8 equal-width buckets between the 5th and 95th percentile; prices outside
    that range land in the edge buckets, so counts always sum to len(prices)."""
    if not prices:
        return ()
    low, high = _percentile_bounds(prices)
    width = max(1, math.ceil((high - low) / HISTOGRAM_BUCKETS))
    counts = [0] * HISTOGRAM_BUCKETS
    for price in prices:
        index = math.floor((price - low) / width)
        counts[min(HISTOGRAM_BUCKETS - 1, max(0, index))] += 1
    return tuple(
        HistogramBucket(
            low=low + index * width, high=low + (index + 1) * width, count=n
        )
        for index, n in enumerate(counts)
    )


def _trim_stats(rows: Sequence[ModelRow]) -> tuple[TrimStat, ...]:
    counts: dict[str, int] = defaultdict(int)
    prices: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        counts[row.trim] += 1
        if row.price is not None:
            prices[row.trim].append(row.price)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return tuple(
        TrimStat(
            trim=trim,
            count=count,
            price_median=(
                round(statistics.median(prices[trim])) if prices[trim] else None
            ),
        )
        for trim, count in ordered
    )


def _top_deal_ids(rows: Sequence[ModelRow], limit: int) -> tuple[uuid.UUID, ...]:
    scored = [row for row in rows if row.deal_score is not None]
    scored.sort(key=lambda row: (-row.deal_score, row.listing_id))
    return tuple(row.listing_id for row in scored[:limit])


def summarize_model(rows: Sequence[ModelRow], top_deals: int) -> ModelSummary:
    prices = sorted(row.price for row in rows if row.price is not None)
    years = [row.year for row in rows if row.year is not None]
    return ModelSummary(
        count=len(rows),
        year_min=min(years) if years else None,
        year_max=max(years) if years else None,
        price_median=round(statistics.median(prices)) if prices else None,
        price_min=prices[0] if prices else None,
        price_max=prices[-1] if prices else None,
        histogram=_histogram(prices),
        trims=_trim_stats(rows),
        top_deal_ids=_top_deal_ids(rows, top_deals),
    )
````

Modify `backend/repositories/catalog_repository.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/repositories/catalog_repository.py b/backend/repositories/catalog_repository.py
index 4319159..eca736f 100644
--- a/backend/repositories/catalog_repository.py
+++ b/backend/repositories/catalog_repository.py
@@ -1,6 +1,7 @@
 import uuid
 from collections.abc import Collection
 from dataclasses import dataclass
+from typing import Any

 from sqlalchemy import func, select, update
 from sqlalchemy.dialects.postgresql import insert
@@ -30,6 +31,13 @@ class CatalogMatch:
     score: float


+@dataclass(frozen=True, slots=True)
+class CatalogModel:
+    brand: str
+    model: str
+    category: Category
+
+
 @dataclass(frozen=True, slots=True)
 class ModelCount:
     brand: str
@@ -82,12 +90,17 @@ class CatalogRepository:
             .values(listing_count=per_entry.c.listing_count)
         )

+    @staticmethod
+    def _trim_similarity(query: str) -> Any:
+        """`word_similarity` (not `similarity`) because «206» is a substring of
+        «پژو 206 تیپ 2»."""
+        return func.word_similarity(query, VehicleCatalog.trim_normalized)
+
     async def search(
         self, query: str, category: Category | None, min_similarity: float, limit: int
     ) -> list[CatalogMatch]:
-        """Best catalog rows for a normalised free-text mention. `word_similarity`
-        (not `similarity`) because «206» is a substring of «پژو 206 تیپ 2»."""
-        score = func.word_similarity(query, VehicleCatalog.trim_normalized)
+        """Best catalog rows for a normalised free-text mention."""
+        score = self._trim_similarity(query)
         statement = (
             select(
                 VehicleCatalog.brand,
@@ -104,6 +117,19 @@ class CatalogRepository:
         found = await self._session.execute(statement)
         return [CatalogMatch(*row) for row in found]

+    async def find_model(self, model: str) -> CatalogModel | None:
+        statement = (
+            select(VehicleCatalog.brand, VehicleCatalog.model, VehicleCatalog.category)
+            .where(VehicleCatalog.model == model)
+            .order_by(VehicleCatalog.listing_count.desc())
+            .limit(1)
+        )
+        row = (await self._session.execute(statement)).first()
+        if row is None:
+            return None
+        brand, name, category = row
+        return CatalogModel(brand=brand, model=name, category=category)
+
     async def count_models(self, category: Category | None) -> int:
         distinct = select(VehicleCatalog.model).distinct()
         if category is not None:
````

Modify `backend/repositories/listing_repository.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/repositories/listing_repository.py b/backend/repositories/listing_repository.py
index 604b91f..90441df 100644
--- a/backend/repositories/listing_repository.py
+++ b/backend/repositories/listing_repository.py
@@ -14,6 +14,7 @@ from models.city import City
 from models.listing import Listing
 from models.vehicle_catalog import VehicleCatalog
 from ranking.estimator import Estimate, EstimatorInput
+from ranking.model_stats import ModelRow
 from ranking.types import Candidate
 from ranking.weights import CHEAP_DIFF_PCT

@@ -101,6 +102,30 @@ class ListingRepository:
                 update(Listing), rows[start : start + UPSERT_BATCH_SIZE]
             )

+    async def load_model_rows(self, model: str) -> list[ModelRow]:
+        trusted_price = case((Listing.price_suspect, null()), else_=Listing.price)
+        found = await self._session.execute(
+            select(
+                Listing.id,
+                VehicleCatalog.trim,
+                Listing.year,
+                trusted_price,
+                Listing.deal_score,
+            )
+            .join(VehicleCatalog, Listing.catalog_id == VehicleCatalog.id)
+            .where(VehicleCatalog.model == model)
+        )
+        return [
+            ModelRow(
+                listing_id=listing_id,
+                trim=trim,
+                year=year,
+                price=price,
+                deal_score=deal_score,
+            )
+            for listing_id, trim, year, price, deal_score in found
+        ]
+
     async def newest_fetched_at(self) -> datetime | None:
         return await self._session.scalar(select(func.max(Listing.fetched_at)))

````

Create `backend/schemas/model_stats.py`:

````python
from pydantic import BaseModel

from enums import Category
from schemas.listing import ListingCard


class HistogramBucketRead(BaseModel):
    low: int
    high: int
    count: int


class TrimStatRead(BaseModel):
    trim: str
    count: int
    price_median: int | None


class ModelStats(BaseModel):
    model: str
    brand: str
    category: Category
    count: int
    year_min: int | None
    year_max: int | None
    price_median: int | None
    price_min: int | None
    price_max: int | None
    histogram: list[HistogramBucketRead]
    trims: list[TrimStatRead]
    top_deals: list[ListingCard]
````

Create `backend/services/model_stats_service.py`:

````python
from core.text import normalize_persian
from errors import ModelNotFoundError
from ranking.model_stats import summarize_model
from repositories.catalog_repository import CatalogRepository
from repositories.listing_repository import ListingRepository
from schemas.model_stats import HistogramBucketRead, ModelStats, TrimStatRead
from services.listing_views import to_card

TOP_DEALS = 6


class ModelStatsService:
    def __init__(self, catalog: CatalogRepository, listings: ListingRepository) -> None:
        self._catalog = catalog
        self._listings = listings

    async def get_stats(self, model: str) -> ModelStats:
        name = normalize_persian(model)
        info = await self._catalog.find_model(name)
        if info is None:
            raise ModelNotFoundError(model)
        rows = await self._listings.load_model_rows(name)
        summary = summarize_model(rows, TOP_DEALS)
        top = await self._listings.get_by_ids(list(summary.top_deal_ids))
        return ModelStats(
            model=info.model,
            brand=info.brand,
            category=info.category,
            count=summary.count,
            year_min=summary.year_min,
            year_max=summary.year_max,
            price_median=summary.price_median,
            price_min=summary.price_min,
            price_max=summary.price_max,
            histogram=[
                HistogramBucketRead(low=b.low, high=b.high, count=b.count)
                for b in summary.histogram
            ],
            trims=[
                TrimStatRead(trim=t.trim, count=t.count, price_median=t.price_median)
                for t in summary.trims
            ],
            top_deals=[to_card(listing) for listing in top],
        )
````

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run black --check .`
Expected: `201 passed` (+6 pure, +2 API).

- [ ] **Step 5: Commit**

From the repo root (`cd ..`), stage explicit paths only (never `git add -A`):

````bash
git add backend/api/v1/endpoints/models.py backend/api/v1/router.py backend/dependencies/providers.py backend/errors.py backend/ranking/model_stats.py backend/repositories/catalog_repository.py backend/repositories/listing_repository.py backend/schemas/model_stats.py backend/services/model_stats_service.py backend/tests/api/test_models_api.py backend/tests/ranking/test_model_stats.py
git commit -m "feat(api): add GET /models/{model}/stats

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git log -1 --format='%(trailers)'   # must print exactly: Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
````

---

### Task 3: Catalog suggest endpoint

**Files:**
- Create: `backend/api/v1/endpoints/catalog.py`
- Modify: `backend/api/v1/router.py`
- Modify: `backend/dependencies/providers.py`
- Modify: `backend/repositories/catalog_repository.py`
- Create: `backend/schemas/catalog.py`
- Create: `backend/services/catalog_service.py`
- Create: `backend/tests/api/test_catalog_api.py`

**Interfaces:**
- Consumes: `VehicleCatalog.trim_normalized` + `pg_trgm word_similarity` (already indexed), `core.text.normalize_persian`.
- Produces: `CatalogRepository.suggest(query, category, min_similarity, limit) -> list[CatalogSuggestionRow]` (`CatalogSuggestionRow(brand, model, trim, category, listing_count)`), `CatalogRepository._trim_similarity(query)` shared with `search`; `schemas.catalog.CatalogSuggestion(brand, model, trim, category, count)`; `CatalogService(catalog).suggest(query, category)`; `GET /api/v1/catalog/suggest?q=&category=` (`q` ≤ 100 chars → 422 `validation_error` beyond); provider `get_catalog_service`.

Spec §3.2 with Deviation 2 (rows are trims; empty `q` = the category's largest trims by `listing_count`). Threshold `MIN_SUGGEST_SIMILARITY = 0.3` (type-ahead sees half-typed words); the cap is `SUGGEST_LIMIT = 10`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/api/test_catalog_api.py`:

````python
"""GET /catalog/suggest on the seeded fixture DB."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.db


async def test_suggest_is_typo_tolerant_and_capped(api: AsyncClient) -> None:
    response = await api.get("/api/v1/catalog/suggest", params={"q": "پژو 206 تیب"})
    rows = response.json()
    assert response.status_code == 200 and rows
    assert rows[0]["model"] == "پژو 206"
    assert {"brand", "model", "trim", "category", "count"} <= set(rows[0])
    everything = (await api.get("/api/v1/catalog/suggest", params={"q": "پ"})).json()
    assert len(everything) <= 10


async def test_suggest_respects_the_category_and_lists_the_largest_by_default(
    api: AsyncClient,
) -> None:
    motorcycles = (
        await api.get("/api/v1/catalog/suggest", params={"category": "motorcycle"})
    ).json()
    assert 0 < len(motorcycles) <= 10
    assert {row["category"] for row in motorcycles} == {"motorcycle"}
    counts = [row["count"] for row in motorcycles]
    assert counts == sorted(counts, reverse=True)


async def test_overlong_suggest_query_is_a_422(api: AsyncClient) -> None:
    response = await api.get("/api/v1/catalog/suggest", params={"q": "پ" * 101})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
````

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/api/test_catalog_api.py`
Expected: `FAILED … test_suggest_is_typo_tolerant_and_capped - assert (404 == 200)` (the route does not exist yet).

- [ ] **Step 3: Implement**

Create `backend/api/v1/endpoints/catalog.py`:

````python
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from dependencies.providers import get_catalog_service
from enums import Category
from schemas.catalog import CatalogSuggestion
from services.catalog_service import CatalogService

MAX_SUGGEST_QUERY_LENGTH = 100

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/suggest", response_model=list[CatalogSuggestion])
async def suggest_vehicles(
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    q: Annotated[str | None, Query(max_length=MAX_SUGGEST_QUERY_LENGTH)] = None,
    category: Category | None = None,
) -> list[CatalogSuggestion]:
    return await service.suggest(q, category)
````

Modify `backend/api/v1/router.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/api/v1/router.py b/backend/api/v1/router.py
index 99a0536..584bdc9 100644
--- a/backend/api/v1/router.py
+++ b/backend/api/v1/router.py
@@ -2,10 +2,11 @@

 from fastapi import APIRouter

-from api.v1.endpoints import facets, listings, models, search
+from api.v1.endpoints import catalog, facets, listings, models, search

 router = APIRouter()
 router.include_router(search.router)
 router.include_router(listings.router)
 router.include_router(facets.router)
 router.include_router(models.router)
+router.include_router(catalog.router)
````

Modify `backend/dependencies/providers.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/dependencies/providers.py b/backend/dependencies/providers.py
index b55a12e..7ecec30 100644
--- a/backend/dependencies/providers.py
+++ b/backend/dependencies/providers.py
@@ -19,6 +19,7 @@ from repositories.city_repository import CityRepository
 from repositories.health_repository import HealthRepository
 from repositories.listing_repository import ListingRepository
 from schemas.search import SearchIntent
+from services.catalog_service import CatalogService
 from services.facet_service import FacetService
 from services.intent_resolver import IntentResolver
 from services.listing_service import ListingService
@@ -97,5 +98,9 @@ def get_model_stats_service(session: SessionDep) -> ModelStatsService:
     return ModelStatsService(CatalogRepository(session), ListingRepository(session))


+def get_catalog_service(session: SessionDep) -> CatalogService:
+    return CatalogService(CatalogRepository(session))
+
+
 def get_health_repository(session: SessionDep) -> HealthRepository:
     return HealthRepository(session)
````

Modify `backend/repositories/catalog_repository.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/repositories/catalog_repository.py b/backend/repositories/catalog_repository.py
index eca736f..f60e8f7 100644
--- a/backend/repositories/catalog_repository.py
+++ b/backend/repositories/catalog_repository.py
@@ -38,6 +38,15 @@ class CatalogModel:
     category: Category


+@dataclass(frozen=True, slots=True)
+class CatalogSuggestionRow:
+    brand: str
+    model: str
+    trim: str
+    category: Category
+    listing_count: int
+
+
 @dataclass(frozen=True, slots=True)
 class ModelCount:
     brand: str
@@ -117,6 +126,43 @@ class CatalogRepository:
         found = await self._session.execute(statement)
         return [CatalogMatch(*row) for row in found]

+    async def suggest(
+        self, query: str, category: Category | None, min_similarity: float, limit: int
+    ) -> list[CatalogSuggestionRow]:
+        """Type-ahead rows: by similarity when there is a query, else the largest
+        catalog entries of the category."""
+        columns = (
+            VehicleCatalog.brand,
+            VehicleCatalog.model,
+            VehicleCatalog.trim,
+            VehicleCatalog.category,
+            VehicleCatalog.listing_count,
+        )
+        if query:
+            score = self._trim_similarity(query)
+            statement = (
+                select(*columns)
+                .where(score >= min_similarity)
+                .order_by(score.desc(), VehicleCatalog.listing_count.desc())
+            )
+        else:
+            statement = select(*columns).order_by(
+                VehicleCatalog.listing_count.desc(), VehicleCatalog.trim
+            )
+        if category is not None:
+            statement = statement.where(VehicleCatalog.category == category)
+        found = await self._session.execute(statement.limit(limit))
+        return [
+            CatalogSuggestionRow(
+                brand=brand,
+                model=model,
+                trim=trim,
+                category=category_value,
+                listing_count=count,
+            )
+            for brand, model, trim, category_value, count in found
+        ]
+
     async def find_model(self, model: str) -> CatalogModel | None:
         statement = (
             select(VehicleCatalog.brand, VehicleCatalog.model, VehicleCatalog.category)
````

Create `backend/schemas/catalog.py`:

````python
from pydantic import BaseModel

from enums import Category


class CatalogSuggestion(BaseModel):
    brand: str
    model: str
    trim: str
    category: Category
    count: int
````

Create `backend/services/catalog_service.py`:

````python
from core.text import normalize_persian
from enums import Category
from repositories.catalog_repository import CatalogRepository
from schemas.catalog import CatalogSuggestion

SUGGEST_LIMIT = 10
# Looser than the resolver's 0.6: a type-ahead sees half-typed words.
MIN_SUGGEST_SIMILARITY = 0.3


class CatalogService:
    def __init__(self, catalog: CatalogRepository) -> None:
        self._catalog = catalog

    async def suggest(
        self, query: str | None, category: Category | None
    ) -> list[CatalogSuggestion]:
        rows = await self._catalog.suggest(
            normalize_persian(query or ""),
            category,
            MIN_SUGGEST_SIMILARITY,
            SUGGEST_LIMIT,
        )
        return [
            CatalogSuggestion(
                brand=row.brand,
                model=row.model,
                trim=row.trim,
                category=row.category,
                count=row.listing_count,
            )
            for row in rows
        ]
````

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run black --check .`
Expected: `204 passed` (+3 API).

- [ ] **Step 5: Commit**

From the repo root (`cd ..`), stage explicit paths only (never `git add -A`):

````bash
git add backend/api/v1/endpoints/catalog.py backend/api/v1/router.py backend/dependencies/providers.py backend/repositories/catalog_repository.py backend/schemas/catalog.py backend/services/catalog_service.py backend/tests/api/test_catalog_api.py
git commit -m "feat(api): add GET /catalog/suggest

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git log -1 --format='%(trailers)'   # must print exactly: Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
````

---

### Task 4: Estimator extraction and POST /estimates

**Files:**
- Create: `backend/api/v1/endpoints/estimates.py`
- Modify: `backend/api/v1/router.py`
- Modify: `backend/dependencies/providers.py`
- Modify: `backend/errors.py`
- Modify: `backend/ranking/estimator.py`
- Modify: `backend/repositories/catalog_repository.py`
- Modify: `backend/repositories/listing_repository.py`
- Create: `backend/schemas/estimate.py`
- Create: `backend/services/estimate_service.py`
- Create: `backend/tests/api/test_estimates_api.py`
- Modify: `backend/tests/ranking/test_estimator.py`

**Interfaces:**
- Consumes: `PriceEstimator` (bulk pass, unchanged results), `SearchService.rank`/`page_of`, `services.listing_views.verdict_of`, `core.text.jalali_year`.
- Produces: `ranking.estimator.EstimateQuery(category, trim, model, year, km, insurance_months)`, `SingleEstimate(base, est_price, low, high, est_basis, est_sample_size, km_factor, insurance_factor, tried)`, `PriceEstimator.estimate_for(query) -> SingleEstimate`, module functions `insurance_factor_of(months)`, `km_factor_of(km, expected_km)`; `schemas.estimate.EstimateRequest` (validated: `year` 1301…current, `km` 0…2 000 000, `insurance_months` 0…24, `asking_price` > 0), `EstimateBreakdown(base, km_adjustment, insurance_adjustment)`, `EstimateResponse`; `errors.NoComparablesError(tried: list[str])` → 422 `no_comparables` with `details.tried`; `CatalogRepository.find_trim(category, trim_normalized) -> CatalogEntry | None`; `ListingRepository.load_estimator_inputs(category=None)`; `EstimateService(catalog, listings, search).estimate(request)`; `POST /api/v1/estimates`; provider `get_estimate_service`.

Spec §3.3. The refactor keeps `estimate_all()` byte-for-byte equivalent (all 10 existing estimator tests stay green): the basis chain moves to `_attempts`, comparables collection to `_collect` (leave-one-out now happens in `_base_price` only), and km/insurance factors become module functions shared by both paths. `estimate_for` never removes a price (the queried vehicle is not in the data). `low`/`high` are the 25th/75th percentiles of the comparables scaled by the same factors. `similar` runs the search pipeline with the trim, year ± 1 and the category. The estimator is rebuilt from the category's rows on every request (≈5 k rows, a `ponytail:` comment names the cache upgrade path). Body validation failures are 422 `validation_error` envelopes (Global Constraints).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/api/test_estimates_api.py`:

````python
"""POST /estimates on the seeded fixture DB."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.db
MILLION = 1_000_000


async def _a_priced_206(api: AsyncClient) -> dict:
    body = (await api.get("/api/v1/search", params={"q": "۲۰۶ تیپ ۲"})).json()
    return next(item for item in body["items"] if item["est_price"] and item["km"])


async def test_estimate_matches_the_listing_it_is_modelled_on(api: AsyncClient) -> None:
    listing = await _a_priced_206(api)
    request = {
        "category": "light",
        "trim": listing["trim"],
        "year": listing["year"],
        "km": listing["km"],
        "insurance_months": listing["insurance_months"],
        "asking_price": listing["price"],
    }
    response = await api.post("/api/v1/estimates", json=request)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["low"] <= body["est_price"] <= body["high"]
    assert body["est_sample_size"] >= 5
    breakdown = body["breakdown"]
    assert set(breakdown) == {"base", "km_adjustment", "insurance_adjustment"}
    assert body["asking_verdict"] in {"cheap", "fair", "expensive"}
    assert body["asking_diff_pct"] is not None
    assert 0 < len(body["similar"]) <= 4
    assert all(card["model"] == "پژو 206" for card in body["similar"])
    # The same formulas as ingest: the listing's own estimate differs only by its
    # leave-one-out comparables, so the two agree to within a few percent.
    assert abs(body["est_price"] - listing["est_price"]) / listing["est_price"] < 0.1


async def test_no_asking_price_means_no_verdict(api: AsyncClient) -> None:
    listing = await _a_priced_206(api)
    request = {"category": "light", "trim": listing["trim"], "year": listing["year"]}
    body = (await api.post("/api/v1/estimates", json=request)).json()
    assert body["asking_verdict"] is None and body["asking_diff_pct"] is None


async def test_unknown_trim_is_a_422_invalid_search(api: AsyncClient) -> None:
    request = {"category": "light", "trim": "بوگاتی شیرون", "year": 1400}
    response = await api.post("/api/v1/estimates", json=request)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_search"


async def test_without_comparables_the_basis_chain_is_reported(
    api: AsyncClient,
) -> None:
    listing = await _a_priced_206(api)
    # A real trim, but a year nobody sells: every basis in the chain comes up empty.
    request = {"category": "light", "trim": listing["trim"], "year": 1320}
    response = await api.post("/api/v1/estimates", json=request)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "no_comparables"
    assert error["details"]["tried"] == [
        "trim_year",
        "trim_near_year",
        "model_year",
        "model_near_year",
    ]


@pytest.mark.parametrize(
    "bad",
    [
        {"year": 1200},
        {"year": 1398, "km": -1},
        {"year": 1398, "asking_price": 0},
        {"year": 1398, "category": "spaceship"},
    ],
)
async def test_invalid_bodies_are_422_envelopes_not_500s(
    api: AsyncClient, bad: dict
) -> None:
    request = {"category": "light", "trim": "پژو 206 تیپ ۲", **bad}
    response = await api.post("/api/v1/estimates", json=request)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
````

Modify `backend/tests/ranking/test_estimator.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/tests/ranking/test_estimator.py b/backend/tests/ranking/test_estimator.py
index 4c2a6d4..01de45c 100644
--- a/backend/tests/ranking/test_estimator.py
+++ b/backend/tests/ranking/test_estimator.py
@@ -3,7 +3,7 @@ import uuid
 import pytest

 from enums import BodyCondition, Category, EstimateBasis
-from ranking.estimator import EstimatorInput, PriceEstimator
+from ranking.estimator import EstimateQuery, EstimatorInput, PriceEstimator

 CURRENT_YEAR = 1405
 TRIM = "پژو 206 تیپ ۲"
@@ -113,3 +113,63 @@ def test_implausible_price_is_flagged_not_rewarded(price: int) -> None:
     assert estimate.price_suspect is True
     assert estimate.deal_score is None and estimate.diff_pct is None
     assert estimate.est_price == 1000  # the estimate itself is still reported
+
+
+def test_single_estimate_uses_the_same_formulas_as_the_bulk_pass() -> None:
+    peers = [make_row(800, km=100_000, insurance_months=12) for _ in range(6)]
+    target = make_row(900, km=150_000, insurance_months=12)
+    estimator = PriceEstimator([target, *peers], CURRENT_YEAR)
+    bulk = estimator.estimate_all()[0]
+    single = estimator.estimate_for(
+        EstimateQuery(
+            category=Category.LIGHT,
+            trim=TRIM,
+            model=MODEL,
+            year=1398,
+            km=150_000,
+            insurance_months=12,
+        )
+    )
+    assert single.est_basis is EstimateBasis.TRIM_YEAR
+    assert single.km_factor == bulk.km_factor
+    assert single.insurance_factor == bulk.insurance_factor
+    assert single.base == 800  # median of all seven prices, nothing left out
+    assert single.est_price == round(800 * single.km_factor * single.insurance_factor)
+    assert single.low <= single.est_price <= single.high
+    assert single.est_sample_size == 7
+
+
+def test_single_estimate_reports_the_basis_chain_when_nothing_matches() -> None:
+    estimator = PriceEstimator([make_row(800)], CURRENT_YEAR)
+    single = estimator.estimate_for(
+        EstimateQuery(
+            category=Category.LIGHT,
+            trim="ناشناخته",
+            model="ناشناخته",
+            year=1398,
+            km=None,
+            insurance_months=None,
+        )
+    )
+    assert single.est_price is None and single.low is None
+    assert single.tried == (
+        EstimateBasis.TRIM_YEAR,
+        EstimateBasis.TRIM_NEAR_YEAR,
+        EstimateBasis.MODEL_YEAR,
+        EstimateBasis.MODEL_NEAR_YEAR,
+    )
+
+
+def test_single_estimate_range_is_the_interquartile_band() -> None:
+    peers = [make_row(price) for price in (700, 750, 800, 850, 1000)]
+    single = PriceEstimator(peers, CURRENT_YEAR).estimate_for(
+        EstimateQuery(
+            category=Category.LIGHT,
+            trim=TRIM,
+            model=MODEL,
+            year=1398,
+            km=None,
+            insurance_months=None,
+        )
+    )
+    assert (single.low, single.est_price, single.high) == (725, 800, 925)
````

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q`
Expected: collection error `ImportError: cannot import name 'EstimateQuery' from 'ranking.estimator'`.

- [ ] **Step 3: Implement**

Create `backend/api/v1/endpoints/estimates.py`:

````python
from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.providers import get_estimate_service
from schemas.estimate import EstimateRequest, EstimateResponse
from services.estimate_service import EstimateService

router = APIRouter(prefix="/estimates", tags=["estimates"])


@router.post("", response_model=EstimateResponse)
async def create_estimate(
    service: Annotated[EstimateService, Depends(get_estimate_service)],
    request: EstimateRequest,
) -> EstimateResponse:
    return await service.estimate(request)
````

Modify `backend/api/v1/router.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/api/v1/router.py b/backend/api/v1/router.py
index 584bdc9..2a27dd6 100644
--- a/backend/api/v1/router.py
+++ b/backend/api/v1/router.py
@@ -2,7 +2,7 @@

 from fastapi import APIRouter

-from api.v1.endpoints import catalog, facets, listings, models, search
+from api.v1.endpoints import catalog, estimates, facets, listings, models, search

 router = APIRouter()
 router.include_router(search.router)
@@ -10,3 +10,4 @@ router.include_router(listings.router)
 router.include_router(facets.router)
 router.include_router(models.router)
 router.include_router(catalog.router)
+router.include_router(estimates.router)
````

Modify `backend/dependencies/providers.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/dependencies/providers.py b/backend/dependencies/providers.py
index 7ecec30..6051a24 100644
--- a/backend/dependencies/providers.py
+++ b/backend/dependencies/providers.py
@@ -20,6 +20,7 @@ from repositories.health_repository import HealthRepository
 from repositories.listing_repository import ListingRepository
 from schemas.search import SearchIntent
 from services.catalog_service import CatalogService
+from services.estimate_service import EstimateService
 from services.facet_service import FacetService
 from services.intent_resolver import IntentResolver
 from services.listing_service import ListingService
@@ -94,6 +95,15 @@ def get_facet_service(
     )


+def get_estimate_service(
+    session: SessionDep,
+    search: Annotated[SearchService, Depends(get_search_service)],
+) -> EstimateService:
+    return EstimateService(
+        CatalogRepository(session), ListingRepository(session), search
+    )
+
+
 def get_model_stats_service(session: SessionDep) -> ModelStatsService:
     return ModelStatsService(CatalogRepository(session), ListingRepository(session))

````

Modify `backend/errors.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/errors.py b/backend/errors.py
index 8613c12..ef63dfd 100644
--- a/backend/errors.py
+++ b/backend/errors.py
@@ -47,6 +47,14 @@ class InvalidSearchError(AppError):
     code = "invalid_search"


+class NoComparablesError(AppError):
+    status_code = 422
+    code = "no_comparables"
+
+    def __init__(self, tried: list[str]) -> None:
+        super().__init__("Not enough comparable listings", {"tried": tried})
+
+
 class ServiceUnavailableError(AppError):
     status_code = 503
     code = "service_unavailable"
````

Modify `backend/ranking/estimator.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/ranking/estimator.py b/backend/ranking/estimator.py
index e92eb3e..86015cc 100644
--- a/backend/ranking/estimator.py
+++ b/backend/ranking/estimator.py
@@ -1,4 +1,8 @@
-"""Comparables-based price estimate and deal score. Pure Python, no I/O (spec §6.3)."""
+"""Comparables-based price estimate and deal score. Pure Python, no I/O (spec §6.3).
+
+Two entry points share every formula: `estimate_all()` is the ingest bulk pass
+(leave-one-out per listing) and `estimate_for()` answers a single POST /estimates
+query (spec 3 §3.3)."""

 import statistics
 import uuid
@@ -31,6 +35,9 @@ CATCH_ALL_MARKER = "سایر"
 SUSPECT_BELOW_PCT = -40.0
 SUSPECT_ABOVE_PCT = 100.0
 ESTIMATED_CATEGORIES = frozenset({Category.LIGHT, Category.MOTORCYCLE})
+QUARTILES = 4
+LOWER_QUARTILE_INDEX = 0
+UPPER_QUARTILE_INDEX = 2

 # Mirrors frontend/src/lib/catalog.ts BODIES where an equivalent exists.
 BODY_FACTORS: Mapping[BodyCondition, float] = {
@@ -46,6 +53,7 @@ BODY_FACTORS: Mapping[BodyCondition, float] = {
 }

 type GroupKey = tuple[Category, str, int]
+type Groups = Mapping[GroupKey, list[int]]


 @dataclass(frozen=True, slots=True)
@@ -74,6 +82,31 @@ class Estimate:
     price_suspect: bool = False


+@dataclass(frozen=True, slots=True)
+class EstimateQuery:
+    """One hypothetical vehicle, as posted to /estimates (no listing of its own)."""
+
+    category: Category
+    trim: str
+    model: str
+    year: int
+    km: int | None
+    insurance_months: int | None
+
+
+@dataclass(frozen=True, slots=True)
+class SingleEstimate:
+    base: int | None
+    est_price: int | None
+    low: int | None
+    high: int | None
+    est_basis: EstimateBasis
+    est_sample_size: int
+    km_factor: float
+    insurance_factor: float
+    tried: tuple[EstimateBasis, ...]  # the basis chain, for the 422 details
+
+
 def _clamp(value: float, low: float, high: float) -> float:
     return max(low, min(high, value))

@@ -89,6 +122,20 @@ def _is_comparable(row: EstimatorInput) -> bool:
     )


+def insurance_factor_of(insurance_months: int | None) -> float:
+    if insurance_months is None:
+        return 1.0
+    months_over_neutral = insurance_months - INSURANCE_NEUTRAL_MONTHS
+    return 1 + months_over_neutral * INSURANCE_WEIGHT_PER_MONTH
+
+
+def km_factor_of(km: int | None, expected_km: float | None) -> float:
+    if km is None or not expected_km:
+        return 1.0
+    ratio = _clamp((km - expected_km) / expected_km, KM_RATIO_FLOOR, KM_RATIO_CEILING)
+    return 1 - ratio * KM_WEIGHT
+
+
 class PriceEstimator:
     def __init__(self, rows: Sequence[EstimatorInput], current_year: int) -> None:
         self._rows = rows
@@ -103,6 +150,52 @@ class PriceEstimator:
     def estimate_all(self) -> list[Estimate]:
         return [self._estimate(row) for row in self._rows]

+    def estimate_for(self, query: EstimateQuery) -> SingleEstimate:
+        """The bulk formulas applied to a vehicle that is not in the data set, so
+        nothing is left out. `est_price is None` means no basis had enough
+        comparables; `tried` lists the chain for the caller's error details."""
+        km_factor = self._km_factor_of(query.category, query.year, query.km)
+        insurance_factor = insurance_factor_of(query.insurance_months)
+        tried: list[EstimateBasis] = []
+        for groups, name, span, basis in self._attempts(query.trim, query.model):
+            tried.append(basis)
+            prices = self._collect(groups, query.category, name, query.year, span)
+            if len(prices) >= MIN_COMPARABLES:
+                return self._single(prices, basis, km_factor, insurance_factor, tried)
+        return SingleEstimate(
+            base=None,
+            est_price=None,
+            low=None,
+            high=None,
+            est_basis=EstimateBasis.NONE,
+            est_sample_size=0,
+            km_factor=km_factor,
+            insurance_factor=insurance_factor,
+            tried=tuple(tried),
+        )
+
+    @staticmethod
+    def _single(
+        prices: list[int],
+        basis: EstimateBasis,
+        km_factor: float,
+        insurance_factor: float,
+        tried: list[EstimateBasis],
+    ) -> SingleEstimate:
+        scale = km_factor * insurance_factor
+        quartiles = statistics.quantiles(prices, n=QUARTILES)
+        return SingleEstimate(
+            base=round(statistics.median(prices)),
+            est_price=round(statistics.median(prices) * scale),
+            low=round(quartiles[LOWER_QUARTILE_INDEX] * scale),
+            high=round(quartiles[UPPER_QUARTILE_INDEX] * scale),
+            est_basis=basis,
+            est_sample_size=len(prices),
+            km_factor=km_factor,
+            insurance_factor=insurance_factor,
+            tried=tuple(tried),
+        )
+
     def _build_expected_km(
         self, rows: Iterable[EstimatorInput]
     ) -> dict[tuple[Category, int], float]:
@@ -117,8 +210,8 @@ class PriceEstimator:
         }

     def _estimate(self, row: EstimatorInput) -> Estimate:
-        km_factor = self._km_factor(row)
-        insurance_factor = self._insurance_factor(row)
+        km_factor = self._km_factor_of(row.category, row.year, row.km)
+        insurance_factor = insurance_factor_of(row.insurance_months)
         base, basis, sample_size = self._base_price(row)
         if base is None or row.price is None:
             return self._no_estimate(row, km_factor, insurance_factor)
@@ -157,51 +250,45 @@ class PriceEstimator:
             deal_score=None,
         )

+    def _attempts(
+        self, trim: str, model: str
+    ) -> tuple[tuple[Groups, str, int, EstimateBasis], ...]:
+        """The basis chain, most specific first (spec §6.3)."""
+        return (
+            (self._by_trim, trim, 0, EstimateBasis.TRIM_YEAR),
+            (self._by_trim, trim, NEAR_YEAR_SPAN, EstimateBasis.TRIM_NEAR_YEAR),
+            (self._by_model, model, 0, EstimateBasis.MODEL_YEAR),
+            (self._by_model, model, FAR_YEAR_SPAN, EstimateBasis.MODEL_NEAR_YEAR),
+        )
+
     def _base_price(
         self, row: EstimatorInput
     ) -> tuple[float | None, EstimateBasis, int]:
         if not _is_comparable(row):
             return None, EstimateBasis.NONE, 0
-        attempts = (
-            (self._by_trim, row.trim, 0, EstimateBasis.TRIM_YEAR),
-            (self._by_trim, row.trim, NEAR_YEAR_SPAN, EstimateBasis.TRIM_NEAR_YEAR),
-            (self._by_model, row.model, 0, EstimateBasis.MODEL_YEAR),
-            (self._by_model, row.model, FAR_YEAR_SPAN, EstimateBasis.MODEL_NEAR_YEAR),
-        )
-        for groups, name, span, basis in attempts:
-            prices = self._comparables(groups, row, name, span)
+        for groups, name, span, basis in self._attempts(row.trim, row.model):
+            prices = self._collect(groups, row.category, name, row.year, span)
+            prices.remove(row.price)  # leave-one-out: a listing never validates itself
             if len(prices) >= MIN_COMPARABLES:
                 return statistics.median(prices), basis, len(prices)
         return None, EstimateBasis.NONE, 0

-    def _comparables(
-        self,
-        groups: Mapping[GroupKey, list[int]],
-        row: EstimatorInput,
-        name: str,
-        span: int,
+    @staticmethod
+    def _collect(
+        groups: Groups, category: Category, name: str, year: int, span: int
     ) -> list[int]:
         prices: list[int] = []
-        for year in range(row.year - span, row.year + span + 1):
-            prices.extend(groups.get((row.category, name, year), ()))
-        prices.remove(row.price)  # leave-one-out: a listing never validates itself
+        for candidate_year in range(year - span, year + span + 1):
+            prices.extend(groups.get((category, name, candidate_year), ()))
         return prices

-    def _km_factor(self, row: EstimatorInput) -> float:
-        if row.km is None or row.year is None:
-            return 1.0
-        expected = self._expected_km.get((row.category, self._current_year - row.year))
-        if not expected:
-            return 1.0
-        ratio = _clamp((row.km - expected) / expected, KM_RATIO_FLOOR, KM_RATIO_CEILING)
-        return 1 - ratio * KM_WEIGHT
-
-    @staticmethod
-    def _insurance_factor(row: EstimatorInput) -> float:
-        if row.insurance_months is None:
+    def _km_factor_of(
+        self, category: Category, year: int | None, km: int | None
+    ) -> float:
+        if year is None:
             return 1.0
-        months_over_neutral = row.insurance_months - INSURANCE_NEUTRAL_MONTHS
-        return 1 + months_over_neutral * INSURANCE_WEIGHT_PER_MONTH
+        expected = self._expected_km.get((category, self._current_year - year))
+        return km_factor_of(km, expected)

     @staticmethod
     def _deal_score(
````

Modify `backend/repositories/catalog_repository.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/repositories/catalog_repository.py b/backend/repositories/catalog_repository.py
index f60e8f7..96095c2 100644
--- a/backend/repositories/catalog_repository.py
+++ b/backend/repositories/catalog_repository.py
@@ -163,6 +163,26 @@ class CatalogRepository:
             for brand, model, trim, category_value, count in found
         ]

+    async def find_trim(
+        self, category: Category, trim_normalized: str
+    ) -> CatalogEntry | None:
+        statement = select(
+            VehicleCatalog.category,
+            VehicleCatalog.brand,
+            VehicleCatalog.model,
+            VehicleCatalog.trim,
+        ).where(
+            VehicleCatalog.category == category,
+            VehicleCatalog.trim_normalized == trim_normalized,
+        )
+        row = (await self._session.execute(statement)).first()
+        if row is None:
+            return None
+        category_value, brand, model, trim = row
+        return CatalogEntry(
+            category=category_value, brand=brand, model=model, trim=trim
+        )
+
     async def find_model(self, model: str) -> CatalogModel | None:
         statement = (
             select(VehicleCatalog.brand, VehicleCatalog.model, VehicleCatalog.category)
````

Modify `backend/repositories/listing_repository.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/repositories/listing_repository.py b/backend/repositories/listing_repository.py
index 90441df..bf7594d 100644
--- a/backend/repositories/listing_repository.py
+++ b/backend/repositories/listing_repository.py
@@ -79,20 +79,23 @@ class ListingRepository:
                 )
             )

-    async def load_estimator_inputs(self) -> list[EstimatorInput]:
-        found = await self._session.execute(
-            select(
-                Listing.id,
-                Listing.category,
-                VehicleCatalog.trim,
-                VehicleCatalog.model,
-                Listing.year,
-                Listing.km,
-                Listing.price,
-                Listing.insurance_months,
-                Listing.body_condition,
-            ).outerjoin(VehicleCatalog, Listing.catalog_id == VehicleCatalog.id)
-        )
+    async def load_estimator_inputs(
+        self, category: Category | None = None
+    ) -> list[EstimatorInput]:
+        statement = select(
+            Listing.id,
+            Listing.category,
+            VehicleCatalog.trim,
+            VehicleCatalog.model,
+            Listing.year,
+            Listing.km,
+            Listing.price,
+            Listing.insurance_months,
+            Listing.body_condition,
+        ).outerjoin(VehicleCatalog, Listing.catalog_id == VehicleCatalog.id)
+        if category is not None:
+            statement = statement.where(Listing.category == category)
+        found = await self._session.execute(statement)
         return [EstimatorInput(*row) for row in found]

     async def apply_estimates(self, estimates: Sequence[Estimate]) -> None:
````

Create `backend/schemas/estimate.py`:

````python
from datetime import date
from typing import Self

from pydantic import BaseModel, Field, PositiveInt, model_validator

from core.text import MIN_JALALI_YEAR, jalali_year
from enums import BodyCondition, Category, EstimateBasis, Verdict
from schemas.listing import ListingCard

MAX_TRIM_LENGTH = 255
MAX_KM = 2_000_000
MAX_INSURANCE_MONTHS = 24
SIMILAR_YEAR_SPAN = 1  # /estimates "similar" = trim, year ± 1, category


class EstimateRequest(BaseModel):
    category: Category
    trim: str = Field(min_length=1, max_length=MAX_TRIM_LENGTH)
    year: int
    km: int | None = Field(default=None, ge=0, le=MAX_KM)
    insurance_months: int | None = Field(default=None, ge=0, le=MAX_INSURANCE_MONTHS)
    body_condition: BodyCondition | None = None
    asking_price: PositiveInt | None = Field(default=None, description="toman")

    @model_validator(mode="after")
    def _check_year(self) -> Self:
        # ± SIMILAR_YEAR_SPAN must stay inside SearchIntent's own year bounds.
        newest = jalali_year(date.today())
        oldest = MIN_JALALI_YEAR + SIMILAR_YEAR_SPAN
        if not oldest <= self.year <= newest:
            raise ValueError(
                f"year must be a Jalali year between {oldest} and {newest}"
            )
        return self


class EstimateBreakdown(BaseModel):
    base: int
    km_adjustment: int
    insurance_adjustment: int


class EstimateResponse(BaseModel):
    est_price: int
    low: int
    high: int
    est_basis: EstimateBasis
    est_sample_size: int
    breakdown: EstimateBreakdown
    asking_verdict: Verdict | None
    asking_diff_pct: float | None
    similar: list[ListingCard]
````

Create `backend/services/estimate_service.py`:

````python
"""POST /estimates: the ingest estimator's formulas for one hypothetical vehicle."""

from datetime import UTC, datetime

from core.text import jalali_year, normalize_persian
from errors import InvalidSearchError, NoComparablesError
from ranking.estimator import EstimateQuery, PriceEstimator, SingleEstimate
from repositories.catalog_repository import CatalogEntry, CatalogRepository
from repositories.listing_repository import ListingRepository
from schemas.estimate import (
    SIMILAR_YEAR_SPAN,
    EstimateBreakdown,
    EstimateRequest,
    EstimateResponse,
)
from schemas.listing import ListingCard
from schemas.search import SearchIntent, VehicleMention
from services.listing_views import verdict_of
from services.search_service import SearchService

SIMILAR_LIMIT = 4
FIRST_PAGE = 1
PERCENT = 100


class EstimateService:
    def __init__(
        self,
        catalog: CatalogRepository,
        listings: ListingRepository,
        search: SearchService,
    ) -> None:
        self._catalog = catalog
        self._listings = listings
        self._search = search

    async def estimate(self, request: EstimateRequest) -> EstimateResponse:
        entry = await self._catalog.find_trim(
            request.category, normalize_persian(request.trim)
        )
        if entry is None:
            raise InvalidSearchError("Unknown trim", {"trim": request.trim})
        estimate = await self._run_estimator(request, entry)
        if estimate.est_price is None or estimate.base is None:
            raise NoComparablesError([basis.value for basis in estimate.tried])
        asking_diff = _asking_diff(request, estimate.est_price)
        return EstimateResponse(
            est_price=estimate.est_price,
            low=estimate.low or estimate.est_price,
            high=estimate.high or estimate.est_price,
            est_basis=estimate.est_basis,
            est_sample_size=estimate.est_sample_size,
            breakdown=_breakdown(estimate, estimate.base),
            asking_verdict=verdict_of(asking_diff) if asking_diff is not None else None,
            asking_diff_pct=asking_diff,
            similar=await self._similar(request, entry),
        )

    async def _run_estimator(
        self, request: EstimateRequest, entry: CatalogEntry
    ) -> SingleEstimate:
        # ponytail: loads the category's rows (≈5k) per request; cache the built
        # estimator per data version if /estimates ever shows up in latency logs.
        newest = await self._listings.newest_fetched_at() or datetime.now(UTC)
        rows = await self._listings.load_estimator_inputs(request.category)
        query = EstimateQuery(
            category=request.category,
            trim=entry.trim,
            model=entry.model,
            year=request.year,
            km=request.km,
            insurance_months=request.insurance_months,
        )
        return PriceEstimator(rows, jalali_year(newest.date())).estimate_for(query)

    async def _similar(
        self, request: EstimateRequest, entry: CatalogEntry
    ) -> list[ListingCard]:
        intent = SearchIntent(
            category=request.category,
            vehicles=[VehicleMention(trim=entry.trim)],
            year_min=request.year - SIMILAR_YEAR_SPAN,
            year_max=request.year + SIMILAR_YEAR_SPAN,
        )
        ranked, _ = await self._search.rank(intent)
        return await self._search.page_of(ranked.results, FIRST_PAGE, SIMILAR_LIMIT)


def _breakdown(estimate: SingleEstimate, base: int) -> EstimateBreakdown:
    return EstimateBreakdown(
        base=base,
        km_adjustment=round(base * (estimate.km_factor - 1)),
        insurance_adjustment=round(base * (estimate.insurance_factor - 1)),
    )


def _asking_diff(request: EstimateRequest, est_price: int) -> float | None:
    if request.asking_price is None:
        return None
    return round((request.asking_price - est_price) / est_price * PERCENT, 1)
````

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run black --check .`
Expected: `215 passed` (+3 pure, +8 API incl. 4 parametrised 422 cases).

- [ ] **Step 5: Commit**

From the repo root (`cd ..`), stage explicit paths only (never `git add -A`):

````bash
git add backend/api/v1/endpoints/estimates.py backend/api/v1/router.py backend/dependencies/providers.py backend/errors.py backend/ranking/estimator.py backend/repositories/catalog_repository.py backend/repositories/listing_repository.py backend/schemas/estimate.py backend/services/estimate_service.py backend/tests/api/test_estimates_api.py backend/tests/ranking/test_estimator.py
git commit -m "feat(api): extract the estimator and add POST /estimates

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git log -1 --format='%(trailers)'   # must print exactly: Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
````

---

### Task 5: Assistant endpoint — Pydantic AI agent with a rules fallback

**Files:**
- Create: `backend/api/v1/endpoints/assistant.py`
- Modify: `backend/api/v1/router.py`
- Modify: `backend/core/config.py`
- Modify: `backend/dependencies/providers.py`
- Modify: `backend/enums.py`
- Create: `backend/llm/assistant_agent.py`
- Create: `backend/schemas/assistant.py`
- Create: `backend/services/assistant_service.py`
- Create: `backend/tests/api/test_assistant_api.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/services/test_assistant_service.py`

**Interfaces:**
- Consumes: `llm.model_factory.build_model`, `SearchService.rank`/`page_of` (search tool), `ListingRepository.get_by_ids` (compare tool), `QueryParser.parse` (rules path), `services.query_parser.LLM_FAILURES`, `ranking.labels.format_toman`, `core.text.to_persian_digits`.
- Produces: `enums.ChatRole`; `core.config.Settings.assistant_timeout_seconds` (default 20.0, env `ASSISTANT_TIMEOUT_SECONDS`); `schemas.assistant.AssistantMessage(role, text ≤ 500)`, `AssistantRequest(messages 1…10, compare_ids ≤ 3; last message must be the user's)`, `AssistantResponse(text, listings, answered_by: ParsedBy)`; `llm.assistant_agent.AssistantDeps(search, listings)`, `AssistantReply(text, listing_ids ≤ 3)`, `build_prompt(messages, compare_ids)`, `build_assistant_agent(model) -> Agent[AssistantDeps, AssistantReply]` with tools `search_listings(intent: SearchIntent)` and `compare_listings(listing_ids)`; `AssistantService(agent, parser, search, listings, timeout_seconds).reply(request)`; `POST /api/v1/assistant`; providers `get_assistant_agent` (lru-cached, `None` without a key) and `get_assistant_service`; the `api` test fixture overrides `get_assistant_agent` to `None`.

Spec §3.4. Stateless: the request carries the capped history and compare ids, which `build_prompt` folds into one prompt. The LLM never writes SQL — its tools call the existing services and its only output type is `AssistantReply`; the service hydrates cards from the ids. Rules path (no key, timeout, provider error): a "which is better" question with ≥ 2 compare ids answers with the highest deal score; otherwise the last message is parsed, ranked, every ranked card (≤ 500) is hydrated for the count/median/below-market numbers, and the top 3 are exact matches first, then best deal (Deviation 7). `RuntimeError`s from a model are **not** absorbed (only `LLM_FAILURES`), so the failure test raises `ModelAPIError`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/api/test_assistant_api.py`:

````python
"""POST /assistant on the seeded fixture DB (no LLM → rules path)."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.db


async def test_rules_answer_carries_real_cards(api: AsyncClient) -> None:
    body = {"messages": [{"role": "user", "text": "۲۰۶ تهران"}], "compare_ids": []}
    response = await api.post("/api/v1/assistant", json=body)
    assert response.status_code == 200, response.text
    reply = response.json()
    assert reply["answered_by"] == "rules"
    assert "آگهی پیدا کردم" in reply["text"]
    assert 0 < len(reply["listings"]) <= 3
    assert all(card["model"] == "پژو 206" for card in reply["listings"])


@pytest.mark.parametrize(
    "body",
    [
        {"messages": []},
        {"messages": [{"role": "user", "text": "پ" * 501}]},
        {"messages": [{"role": "assistant", "text": "سلام"}]},
        {"messages": [{"role": "user", "text": "سلام"}] * 11},
    ],
)
async def test_invalid_chat_bodies_are_422_envelopes(
    api: AsyncClient, body: dict
) -> None:
    response = await api.post("/api/v1/assistant", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
````

Modify `backend/tests/conftest.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/tests/conftest.py b/backend/tests/conftest.py
index 204f238..0ef1b3d 100644
--- a/backend/tests/conftest.py
+++ b/backend/tests/conftest.py
@@ -12,7 +12,7 @@ from sqlalchemy.pool import NullPool

 from core.config import get_settings
 from db.session import get_session
-from dependencies.providers import get_cache, get_intent_agent
+from dependencies.providers import get_assistant_agent, get_cache, get_intent_agent
 from ingest.pipeline import IngestPipeline
 from main import create_app
 from repositories.catalog_repository import CatalogRepository
@@ -97,6 +97,7 @@ async def api(
     app.dependency_overrides[get_session] = use_seeded_session
     app.dependency_overrides[get_cache] = lambda: cache
     app.dependency_overrides[get_intent_agent] = lambda: None
+    app.dependency_overrides[get_assistant_agent] = lambda: None
     transport = ASGITransport(app=app, raise_app_exceptions=False)
     async with AsyncClient(transport=transport, base_url="http://test") as http:
         yield http
````

Create `backend/tests/services/test_assistant_service.py`:

````python
"""AssistantService in isolation: rules path with stubs, LLM path with a
FunctionModel that calls the search tool. No test reaches a provider."""

import uuid
from datetime import UTC, datetime

from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.exceptions import ModelAPIError
from pydantic_ai.models.function import AgentInfo, FunctionModel

from enums import Category, ChatRole, ParsedBy, Verdict
from llm.assistant_agent import build_assistant_agent
from ranking.types import RankedListing
from schemas.assistant import AssistantMessage, AssistantRequest
from schemas.listing import ListingCard
from schemas.search import SearchIntent
from services.assistant_service import AssistantService
from services.query_parser import ParsedQuery
from services.search_service import RankedSearch

NOW = datetime(2026, 9, 17, 20, 0, tzinfo=UTC)
IDS = [uuid.UUID(int=number) for number in range(1, 4)]
MILLION = 1_000_000


def make_card(listing_id: uuid.UUID, price: int, deal_score: int | None) -> ListingCard:
    return ListingCard(
        id=listing_id,
        token=f"tok{listing_id.int}",
        title=f"پژو ۲۰۶ شمارهٔ {listing_id.int}",
        category=Category.LIGHT,
        brand="پژو",
        model="پژو 206",
        trim="پژو 206 تیپ ۲",
        year=1398,
        km=60_000,
        price=price,
        city="تهران",
        district=None,
        lat=None,
        lng=None,
        gearbox=None,
        fuel=None,
        body_condition=None,
        insurance_months=None,
        thumbnail_url=None,
        posted_at=NOW,
        est_price=900 * MILLION,
        diff_pct=(price - 900 * MILLION) / (900 * MILLION) * 100,
        deal_score=deal_score,
        verdict=Verdict.FAIR,
    )


CARDS = {
    IDS[0]: make_card(IDS[0], 800 * MILLION, 90),
    IDS[1]: make_card(IDS[1], 900 * MILLION, 50),
    IDS[2]: make_card(IDS[2], 1_000 * MILLION, None),
}


class StubParser:
    async def parse(self, text: str) -> ParsedQuery:
        return ParsedQuery(SearchIntent(text=text), ParsedBy.RULES)


class StubSearch:
    def __init__(self, ids: list[uuid.UUID]) -> None:
        self.ids = ids
        self.intents: list[SearchIntent] = []

    async def rank(
        self, intent: SearchIntent, exclude_id: uuid.UUID | None = None
    ) -> tuple[RankedSearch, bool]:
        self.intents.append(intent)
        results = tuple(RankedListing(i, 1.0, 1.0, True, ()) for i in self.ids)
        return RankedSearch(("پژو 206",), results), False

    async def page_of(
        self, results: tuple[RankedListing, ...], page: int, page_size: int
    ) -> list[ListingCard]:
        return [CARDS[item.id] for item in results[:page_size]]


class StubListings:
    async def get_by_ids(self, listing_ids: list[uuid.UUID]) -> list[object]:
        return [_as_orm(CARDS[i]) for i in listing_ids if i in CARDS]


class _AsOrm:
    """Just enough of a Listing for to_card()."""

    def __init__(self, card: ListingCard) -> None:
        self.__dict__.update(card.model_dump(exclude={"brand", "model", "trim"}))
        self.thumbnail_urls: list[str] = []
        self.image_urls: list[str] = []
        self.city = type("City", (), {"name": card.city, "lat": None, "lng": None})()
        self.catalog = type(
            "Catalog", (), {"brand": card.brand, "model": card.model, "trim": card.trim}
        )()


def _as_orm(card: ListingCard) -> _AsOrm:
    return _AsOrm(card)


def ask(text: str, compare_ids: list[uuid.UUID] | None = None) -> AssistantRequest:
    return AssistantRequest(
        messages=[AssistantMessage(role=ChatRole.USER, text=text)],
        compare_ids=compare_ids or [],
    )


def make_service(agent, search: StubSearch) -> AssistantService:
    return AssistantService(agent, StubParser(), search, StubListings(), 1.0)


async def test_rules_reply_counts_medians_and_ranks_by_deal_score() -> None:
    response = await make_service(None, StubSearch(IDS)).reply(ask("۲۰۶ تهران"))
    assert response.answered_by is ParsedBy.RULES
    assert "۳ آگهی پیدا کردم (پژو 206)" in response.text
    assert "۹۰۰ میلیون" in response.text  # median of 800/900/1000 million
    assert "۱ تا زیر قیمت بازار" in response.text
    assert [card.id for card in response.listings] == [IDS[0], IDS[1], IDS[2]]


async def test_rules_reply_without_matches_suggests_a_relaxation() -> None:
    response = await make_service(None, StubSearch([])).reply(
        ask("تارا زیر ۱۰۰ میلیون")
    )
    assert response.listings == [] and "آگهی فعالی نداریم" in response.text


async def test_which_is_better_picks_the_highest_deal_score_among_compared() -> None:
    service = make_service(None, StubSearch(IDS))
    response = await service.reply(
        ask("کدوم به‌صرفه‌تره؟", compare_ids=[IDS[1], IDS[0]])
    )
    assert [card.id for card in response.listings] == [IDS[0]]
    assert "امتیاز ۹۰" in response.text


async def test_llm_path_calls_the_search_tool_and_hydrates_cards() -> None:
    def scripted(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        returned = [
            part
            for message in messages
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]
        if not returned:
            intent = {"vehicles": [{"model": "۲۰۶"}], "cities": ["تهران"]}
            return ModelResponse(
                parts=[ToolCallPart("search_listings", {"intent": intent})]
            )
        found = returned[0].content["listings"]
        reply = {"text": "این‌ها را ببین", "listing_ids": [found[0]["id"]]}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, reply)])

    search = StubSearch(IDS)
    service = make_service(build_assistant_agent(FunctionModel(scripted)), search)
    response = await service.reply(ask("یه ۲۰۶ تو تهران"))
    assert response.answered_by is ParsedBy.LLM
    assert response.text == "این‌ها را ببین"
    assert [card.id for card in response.listings] == [IDS[0]]
    assert search.intents[0].cities == ["تهران"]


async def test_llm_failure_falls_back_to_the_rules_reply() -> None:
    def broken(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise ModelAPIError("function-model", "provider down")

    service = make_service(
        build_assistant_agent(FunctionModel(broken)), StubSearch(IDS)
    )
    response = await service.reply(ask("۲۰۶ تهران"))
    assert response.answered_by is ParsedBy.RULES
````

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q`
Expected: `ImportError while loading conftest … cannot import name 'get_assistant_agent' from 'dependencies.providers'`.

- [ ] **Step 3: Implement**

Create `backend/api/v1/endpoints/assistant.py`:

````python
from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.providers import get_assistant_service
from schemas.assistant import AssistantRequest, AssistantResponse
from services.assistant_service import AssistantService

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("", response_model=AssistantResponse)
async def ask_assistant(
    service: Annotated[AssistantService, Depends(get_assistant_service)],
    request: AssistantRequest,
) -> AssistantResponse:
    return await service.reply(request)
````

Modify `backend/api/v1/router.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/api/v1/router.py b/backend/api/v1/router.py
index 2a27dd6..b118869 100644
--- a/backend/api/v1/router.py
+++ b/backend/api/v1/router.py
@@ -2,7 +2,15 @@

 from fastapi import APIRouter

-from api.v1.endpoints import catalog, estimates, facets, listings, models, search
+from api.v1.endpoints import (
+    assistant,
+    catalog,
+    estimates,
+    facets,
+    listings,
+    models,
+    search,
+)

 router = APIRouter()
 router.include_router(search.router)
@@ -11,3 +19,4 @@ router.include_router(facets.router)
 router.include_router(models.router)
 router.include_router(catalog.router)
 router.include_router(estimates.router)
+router.include_router(assistant.router)
````

Modify `backend/core/config.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/core/config.py b/backend/core/config.py
index 2df156d..86299e3 100644
--- a/backend/core/config.py
+++ b/backend/core/config.py
@@ -23,6 +23,7 @@ class Settings(BaseSettings):
     llm_api_key: SecretStr = SecretStr("")
     llm_base_url: str | None = None
     llm_timeout_seconds: float = 4.0
+    assistant_timeout_seconds: float = 20.0  # tool calls need two round trips


 @lru_cache
````

Modify `backend/dependencies/providers.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/dependencies/providers.py b/backend/dependencies/providers.py
index 6051a24..ce8c0d9 100644
--- a/backend/dependencies/providers.py
+++ b/backend/dependencies/providers.py
@@ -11,6 +11,7 @@ from sqlalchemy.ext.asyncio import AsyncSession
 from core.cache import Cache
 from core.config import Settings, get_settings
 from db.session import get_session
+from llm.assistant_agent import AssistantDeps, AssistantReply, build_assistant_agent
 from llm.intent_agent import build_intent_agent
 from llm.model_factory import build_model
 from ranking.ranker import ListingRanker
@@ -19,6 +20,7 @@ from repositories.city_repository import CityRepository
 from repositories.health_repository import HealthRepository
 from repositories.listing_repository import ListingRepository
 from schemas.search import SearchIntent
+from services.assistant_service import AssistantService
 from services.catalog_service import CatalogService
 from services.estimate_service import EstimateService
 from services.facet_service import FacetService
@@ -44,6 +46,12 @@ def get_intent_agent() -> Agent[None, SearchIntent] | None:
     return build_intent_agent(model) if model is not None else None


+@lru_cache
+def get_assistant_agent() -> Agent[AssistantDeps, AssistantReply] | None:
+    model = build_model(get_settings())
+    return build_assistant_agent(model) if model is not None else None
+
+
 CacheDep = Annotated[Cache, Depends(get_cache)]
 AgentDep = Annotated[Agent[None, SearchIntent] | None, Depends(get_intent_agent)]

@@ -95,6 +103,21 @@ def get_facet_service(
     )


+def get_assistant_service(
+    session: SessionDep,
+    settings: SettingsDep,
+    parser: Annotated[QueryParser, Depends(get_query_parser)],
+    search: Annotated[SearchService, Depends(get_search_service)],
+) -> AssistantService:
+    return AssistantService(
+        get_assistant_agent(),
+        parser,
+        search,
+        ListingRepository(session),
+        settings.assistant_timeout_seconds,
+    )
+
+
 def get_estimate_service(
     session: SessionDep,
     search: Annotated[SearchService, Depends(get_search_service)],
````

Modify `backend/enums.py` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/backend/enums.py b/backend/enums.py
index ca9ac53..2e036cf 100644
--- a/backend/enums.py
+++ b/backend/enums.py
@@ -66,6 +66,11 @@ class LlmProvider(StrEnum):
     OPENAI_COMPATIBLE = "openai_compatible"


+class ChatRole(StrEnum):
+    USER = "user"
+    ASSISTANT = "assistant"
+
+
 class ParsedBy(StrEnum):
     LLM = "llm"
     RULES = "rules"
````

Create `backend/llm/assistant_agent.py`:

````python
"""The shopping-assistant agent (spec 3 §3.4). Its two tools call the existing search
and listing services; its only output type is AssistantReply. It never writes SQL."""

import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from repositories.listing_repository import ListingRepository
from schemas.assistant import AssistantMessage
from schemas.listing import ListingCard
from schemas.search import SearchIntent
from services.listing_views import to_card
from services.search_service import SearchService

OUTPUT_RETRIES = 2
TOOL_RESULT_LIMIT = 8
FIRST_PAGE = 1
_CARD_FIELDS = {
    "id",
    "title",
    "trim",
    "year",
    "km",
    "price",
    "city",
    "gearbox",
    "est_price",
    "diff_pct",
    "deal_score",
    "verdict",
    "is_exact",
    "near_miss_labels",
}

_INSTRUCTIONS = """\
You are ترب‌کار's shopping assistant for used vehicles on Divar (Iran). Answer in
short, friendly Persian (2–4 sentences), in the same informal register as the user.

- To find vehicles call `search_listings` with a SearchIntent built from the user's
  words: years are Jalali, money is toman as a full integer (۸۰۰ میلیون = 800000000),
  km_max in kilometres, vehicles as the user wrote them. Never invent listings.
- To judge "which is better" between the vehicles the user is comparing, call
  `compare_listings` with the compare ids given in the prompt; prefer the highest
  deal_score and explain why (price vs. estimate, km, year).
- Put the ids of the listings you mention in `listing_ids` (at most 3), in the
  order you recommend them. Mention prices in میلیون/میلیارد تومان words.
- If nothing matches, say so and suggest one concrete relaxation (higher budget,
  another city, older model). Do not answer questions unrelated to buying a vehicle.
"""


@dataclass(frozen=True, slots=True)
class AssistantDeps:
    search: SearchService
    listings: ListingRepository


class AssistantReply(BaseModel):
    text: str
    listing_ids: list[uuid.UUID] = Field(default_factory=list, max_length=3)


def _brief(card: ListingCard) -> dict[str, Any]:
    return card.model_dump(mode="json", include=_CARD_FIELDS)


def build_prompt(messages: list[AssistantMessage], compare_ids: list[uuid.UUID]) -> str:
    """The stateless request as one prompt: the (capped) history, then the question."""
    history = "\n".join(f"{message.role.value}: {message.text}" for message in messages)
    compare = ", ".join(str(listing_id) for listing_id in compare_ids) or "none"
    return f"Conversation so far:\n{history}\n\nCompare ids: {compare}"


def build_assistant_agent(model: Model) -> Agent[AssistantDeps, AssistantReply]:
    agent: Agent[AssistantDeps, AssistantReply] = Agent(
        model,
        deps_type=AssistantDeps,
        output_type=AssistantReply,
        instructions=_INSTRUCTIONS,
        retries=OUTPUT_RETRIES,
    )

    @agent.tool
    async def search_listings(
        context: RunContext[AssistantDeps], intent: SearchIntent
    ) -> dict[str, Any]:
        """Search the live listings; returns the total and the best matches."""
        ranked, _ = await context.deps.search.rank(intent)
        cards = await context.deps.search.page_of(
            ranked.results, FIRST_PAGE, TOOL_RESULT_LIMIT
        )
        return {
            "total": len(ranked.results),
            "exact_count": sum(item.is_exact for item in ranked.results),
            "listings": [_brief(card) for card in cards],
        }

    @agent.tool
    async def compare_listings(
        context: RunContext[AssistantDeps], listing_ids: list[uuid.UUID]
    ) -> list[dict[str, Any]]:
        """The listings the user is comparing, with their price verdicts."""
        found = await context.deps.listings.get_by_ids(listing_ids)
        return [_brief(to_card(listing)) for listing in found]

    return agent
````

Create `backend/schemas/assistant.py`:

````python
import uuid
from typing import Self

from pydantic import BaseModel, Field, model_validator

from enums import ChatRole, ParsedBy
from schemas.listing import ListingCard

MAX_MESSAGE_LENGTH = 500
MAX_HISTORY = 10
MAX_COMPARE_IDS = 3


class AssistantMessage(BaseModel):
    role: ChatRole
    text: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


class AssistantRequest(BaseModel):
    messages: list[AssistantMessage] = Field(min_length=1, max_length=MAX_HISTORY)
    compare_ids: list[uuid.UUID] = Field(
        default_factory=list, max_length=MAX_COMPARE_IDS
    )

    @model_validator(mode="after")
    def _last_message_is_the_users(self) -> Self:
        if self.messages[-1].role is not ChatRole.USER:
            raise ValueError("the last message must come from the user")
        return self

    @property
    def question(self) -> str:
        return self.messages[-1].text


class AssistantResponse(BaseModel):
    text: str
    listings: list[ListingCard]
    answered_by: ParsedBy
````

Create `backend/services/assistant_service.py`:

````python
"""POST /assistant: LLM agent first, deterministic rules reply when there is no key,
a timeout or a provider error (spec 3 §3.4)."""

import asyncio
import logging
import re
import statistics
import uuid

from pydantic_ai import Agent

from core.text import to_persian_digits
from enums import ParsedBy
from llm.assistant_agent import AssistantDeps, AssistantReply, build_prompt
from ranking import labels
from ranking.weights import CHEAP_DIFF_PCT
from repositories.listing_repository import ListingRepository
from schemas.assistant import AssistantRequest, AssistantResponse
from schemas.listing import ListingCard
from services.listing_views import to_card
from services.query_parser import LLM_FAILURES, QueryParser
from services.search_service import MAX_RESULTS, SearchService

logger = logging.getLogger(__name__)

SUGGESTED_CARDS = 3
MIN_CARDS_TO_COMPARE = 2
FIRST_PAGE = 1
COMPARE_QUESTION = re.compile(r"کدوم|کدام|بهتر|به\s?صرفه")
NO_MATCH_TEXT = (
    "با این شرایط آگهی فعالی نداریم. سقف قیمت را بالاتر ببر یا شهر را حذف کن."
)


def _deal_score_or_lowest(card: ListingCard) -> int:
    return card.deal_score if card.deal_score is not None else -1


def _exact_then_best_deal(card: ListingCard) -> tuple[bool, int]:
    """Exact matches before near-misses, then the best deal (same tiers as search)."""
    return card.is_exact, _deal_score_or_lowest(card)


class AssistantService:
    def __init__(
        self,
        agent: Agent[AssistantDeps, AssistantReply] | None,
        parser: QueryParser,
        search: SearchService,
        listings: ListingRepository,
        timeout_seconds: float,
    ) -> None:
        self._agent = agent
        self._parser = parser
        self._search = search
        self._listings = listings
        self._timeout_seconds = timeout_seconds

    async def reply(self, request: AssistantRequest) -> AssistantResponse:
        reply = await self._ask_llm(request)
        if reply is None:
            return await self._rules_reply(request)
        cards = await self._cards(reply.listing_ids)
        return AssistantResponse(
            text=reply.text, listings=cards, answered_by=ParsedBy.LLM
        )

    async def _ask_llm(self, request: AssistantRequest) -> AssistantReply | None:
        """None means "use the rules reply". Like QueryParser, an LLM outage must
        never fail the chat, so provider errors are logged and absorbed here."""
        if self._agent is None:
            return None
        deps = AssistantDeps(self._search, self._listings)
        prompt = build_prompt(request.messages, request.compare_ids)
        try:
            result = await asyncio.wait_for(
                self._agent.run(prompt, deps=deps), self._timeout_seconds
            )
        except LLM_FAILURES as error:
            fields = {"error": type(error).__name__, "detail": str(error)}
            logger.warning(
                "assistant llm failed, using rules", extra={"fields": fields}
            )
            return None
        return result.output

    async def _cards(self, listing_ids: list[uuid.UUID]) -> list[ListingCard]:
        found = await self._listings.get_by_ids(listing_ids)
        return [to_card(listing) for listing in found]

    async def _rules_reply(self, request: AssistantRequest) -> AssistantResponse:
        compared = await self._cards(request.compare_ids)
        if COMPARE_QUESTION.search(request.question) and (
            len(compared) >= MIN_CARDS_TO_COMPARE
        ):
            return _best_of(compared)
        parsed = await self._parser.parse(request.question)
        ranked, _ = await self._search.rank(parsed.intent)
        # ponytail: hydrates every ranked card (≤ MAX_RESULTS) for the median; a
        # price-stats repository query would do if this shows up in latency logs.
        cards = await self._search.page_of(ranked.results, FIRST_PAGE, MAX_RESULTS)
        if not cards:
            return AssistantResponse(
                text=NO_MATCH_TEXT, listings=[], answered_by=ParsedBy.RULES
            )
        return _summary_of(cards, ranked.chips)


def _best_of(compared: list[ListingCard]) -> AssistantResponse:
    best = max(compared, key=_deal_score_or_lowest)
    score = to_persian_digits(best.deal_score) if best.deal_score is not None else "—"
    count = to_persian_digits(len(compared))
    text = (
        f"بین {count} خودرویی که مقایسه می‌کنی، «{best.title}» "
        f"بهترین ارزش خرید را دارد (امتیاز {score}/۱۰۰)."
    )
    return AssistantResponse(text=text, listings=[best], answered_by=ParsedBy.RULES)


def _summary_of(cards: list[ListingCard], chips: tuple[str, ...]) -> AssistantResponse:
    prices = [card.price for card in cards if card.price is not None]
    below = sum(1 for card in cards if (card.diff_pct or 0) <= CHEAP_DIFF_PCT)
    median = labels.format_toman(round(statistics.median(prices))) if prices else "—"
    understood = f" ({'، '.join(chips)})" if chips else ""
    text = (
        f"{to_persian_digits(len(cards))} آگهی پیدا کردم{understood}. "
        f"میانهٔ قیمت‌شان {median} است و {to_persian_digits(below)} تا زیر قیمت بازار. "
        "سه‌تای اول از نظر ارزش خرید:"
    )
    top = sorted(cards, key=_exact_then_best_deal, reverse=True)[:SUGGESTED_CARDS]
    return AssistantResponse(text=text, listings=top, answered_by=ParsedBy.RULES)
````

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check . && uv run black --check .`
Expected: `225 passed` (+5 service, +5 API). No test reaches a provider.

- [ ] **Step 5: Commit**

From the repo root (`cd ..`), stage explicit paths only (never `git add -A`):

````bash
git add backend/api/v1/endpoints/assistant.py backend/api/v1/router.py backend/core/config.py backend/dependencies/providers.py backend/enums.py backend/llm/assistant_agent.py backend/schemas/assistant.py backend/services/assistant_service.py backend/tests/api/test_assistant_api.py backend/tests/conftest.py backend/tests/services/test_assistant_service.py
git commit -m "feat(api): add POST /assistant with a tool-calling agent and rules fallback

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git log -1 --format='%(trailers)'   # must print exactly: Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
````

---

### Task 6: Frontend API layer, fixtures captured from the new backend

**Files:**
- Create: `backend/tests/fixtures/capture_api_fixtures.py`
- Create: `frontend/src/lib/api/__fixtures__/assistant.json`
- Create: `frontend/src/lib/api/__fixtures__/error-404.json`
- Create: `frontend/src/lib/api/__fixtures__/error-422.json`
- Create: `frontend/src/lib/api/__fixtures__/estimate.json`
- Create: `frontend/src/lib/api/__fixtures__/facets.json`
- Create: `frontend/src/lib/api/__fixtures__/listing.json`
- Create: `frontend/src/lib/api/__fixtures__/model-stats.json`
- Create: `frontend/src/lib/api/__fixtures__/search.json`
- Create: `frontend/src/lib/api/__fixtures__/similar.json`
- Create: `frontend/src/lib/api/__fixtures__/suggest.json`
- Create: `frontend/src/lib/api/base.ts`
- Create: `frontend/src/lib/api/client.test.ts`
- Create: `frontend/src/lib/api/client.ts`
- Create: `frontend/src/lib/api/types.ts`
- Create: `frontend/src/lib/api/useApi.ts`
- Create: `frontend/src/lib/theme.ts`

**Interfaces:**
- Consumes: the backend of Tasks 1–5 (fixture capture), `process.env.API_INTERNAL_URL`, the error envelope `{ error: { code, message, details } }`.
- Produces: `src/lib/api/types.ts` (hand-written mirrors: `ListingCard`, `ListingDetail`, `PriceBreakdown`, `SearchIntent`, `IntentRead`, `SearchResponse`, `SearchParams`, `Facets`, `ModelStats`, `CatalogSuggestion`, `EstimateRequest/Response`, `AssistantRequest/Response`, `ApiErrorBody`, enums `Category`, `Gearbox`, `Fuel`, `BodyCondition`, `EstimateBasis`, `SortKey`, `Verdict`, `ParsedBy`, `ChatRole`); `src/lib/api/base.ts` `apiBase(inBrowser?) -> string`; `src/lib/api/client.ts` `ApiError(status, code, message, details)`, `buildQuery(params)`, `apiGet<T>(path, params?, signal?)`, `apiPost<T>(path, body, signal?)`, `isAbort(error)`, `NETWORK_ERROR_STATUS = 0` (network failure → `ApiError(0, "network_error")`, non-JSON failure → `ApiError(status, "http_error")`); `src/lib/api/useApi.ts` `useApi<T>(key: string | null, fetcher: (signal) => Promise<T>) -> { data, error, loading, retry }`; `src/lib/theme.ts` colour constants; JSON fixtures under `src/lib/api/__fixtures__/` (`search`, `listing`, `similar`, `facets`, `model-stats`, `suggest`, `estimate`, `assistant`, `error-404`, `error-422`); `backend/tests/fixtures/capture_api_fixtures.py` (re-captures them: `uv run python -m tests.fixtures.capture_api_fixtures` with the test DB up).

Spec §4.1 and §6.3. Fixtures come from **this** backend over the seeded fixture DB, so they carry the new response shapes and no personal data (descriptions are already blank in the fixture CSV; the one listing description is a short placeholder). `useApi` sets state only from promise callbacks and keeps the latest fetcher through `useEffectEvent`, so a superseded request is aborted and can never overwrite a newer one; `key === null` means "nothing to fetch". The browser never caches (`cache: "no-store"`) — Redis caches rankings server-side. **Step 1 order:** create the capture script first, start the test database (`./.scripts/test-db.sh`) and run it from `backend/` — `uv run python -m tests.fixtures.capture_api_fixtures` prints the ten fixture paths — then write `client.test.ts`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/fixtures/capture_api_fixtures.py`:

````python
"""Captures the frontend's JSON fixtures from THIS backend, served over the seeded
test database (no LLM, in-memory cache), into frontend/src/lib/api/__fixtures__/.

    ./.scripts/test-db.sh
    cd backend && uv run python -m tests.fixtures.capture_api_fixtures

The fixture CSV already blanks descriptions and rounds coordinates, so the captured
files hold no personal data; the one description is replaced by a short placeholder
so the listing page fixture still renders a seller text."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import get_settings
from db.session import get_session
from dependencies.providers import get_assistant_agent, get_cache, get_intent_agent
from ingest.pipeline import IngestPipeline
from main import create_app
from repositories.catalog_repository import CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import ListingRepository
from tests.conftest import FIXTURE_CSV
from tests.support import DictCache

OUTPUT_DIR = Path(__file__).resolve().parents[3] / "frontend/src/lib/api/__fixtures__"
DESCRIPTION_PLACEHOLDER = "توضیحات فروشنده (در فیکسچر کوتاه شده است)."
SEARCH_QUERY = "۲۰۶ تیپ ۲ تهران"
MODEL = "پژو 206"
MILLION = 1_000_000


async def _capture(http: AsyncClient) -> dict[str, Any]:
    search = await http.get(
        "/api/v1/search", params={"q": SEARCH_QUERY, "page_size": 14}
    )
    first = search.json()["items"][0]
    detail = (await http.get(f"/api/v1/listings/{first['id']}")).json()
    detail["description"] = DESCRIPTION_PLACEHOLDER
    similar = await http.get(
        f"/api/v1/listings/{first['id']}/similar", params={"limit": 3}
    )
    estimate = await http.post(
        "/api/v1/estimates",
        json={
            "category": "light",
            "trim": first["trim"],
            "year": first["year"],
            "km": first["km"],
            "insurance_months": first["insurance_months"],
            "asking_price": first["price"],
        },
    )
    assistant = await http.post(
        "/api/v1/assistant",
        json={"messages": [{"role": "user", "text": SEARCH_QUERY}], "compare_ids": []},
    )
    missing = "00000000-0000-8000-8000-000000000000"
    return {
        "search": search.json(),
        "listing": detail,
        "similar": similar.json(),
        "facets": (await http.get("/api/v1/facets")).json(),
        "model-stats": (await http.get(f"/api/v1/models/{MODEL}/stats")).json(),
        "suggest": (
            await http.get("/api/v1/catalog/suggest", params={"q": "پژو"})
        ).json(),
        "estimate": estimate.json(),
        "assistant": assistant.json(),
        "error-404": (await http.get(f"/api/v1/listings/{missing}")).json(),
        "error-422": (await http.get("/api/v1/search", params={"year": 1200})).json(),
    }


@asynccontextmanager
async def _seeded_session() -> AsyncIterator[tuple[AsyncSession, DictCache]]:
    engine = create_async_engine(get_settings().test_database_url, poolclass=NullPool)
    cache = DictCache()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False) as session:
            pipeline = IngestPipeline(
                CityRepository(session),
                CatalogRepository(session),
                ListingRepository(session),
                cache,
            )
            await pipeline.run(FIXTURE_CSV)
            yield session, cache
        await transaction.rollback()
    await engine.dispose()


def _app_over(session: AsyncSession, cache: DictCache) -> AsyncClient:
    app = create_app()

    async def use_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = use_session
    app.dependency_overrides[get_cache] = lambda: cache
    app.dependency_overrides[get_intent_agent] = lambda: None
    app.dependency_overrides[get_assistant_agent] = lambda: None
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url="http://test")


async def main() -> None:
    async with _seeded_session() as (session, cache):
        async with _app_over(session, cache) as http:
            captured = await _capture(http)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for name, payload in captured.items():
            path = OUTPUT_DIR / f"{name}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            print(path)


if __name__ == "__main__":
    asyncio.run(main())
````

Create `frontend/src/lib/api/client.test.ts`:

````ts
import { afterEach, expect, test } from "bun:test";
import { apiBase } from "./base";
import { ApiError, apiGet, apiPost, buildQuery } from "./client";
import error404 from "./__fixtures__/error-404.json";
import error422 from "./__fixtures__/error-422.json";
import facets from "./__fixtures__/facets.json";
import type { Facets } from "./types";

interface Call { url: string; init: RequestInit | undefined; }
const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; });

function stubFetch(respond: () => Promise<Response>): Call[] {
  const calls: Call[] = [];
  globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    return respond();
  }) as unknown as typeof fetch;
  return calls;
}
const json = (status: number, body: unknown) => () => Promise.resolve(new Response(JSON.stringify(body), { status }));

async function failure(promise: Promise<unknown>): Promise<ApiError> {
  try { await promise; } catch (error) { if (error instanceof ApiError) return error; throw error; }
  throw new Error("expected the request to fail");
}

test("apiBase: server hits the internal backend, browser stays same-origin", () => {
  expect(apiBase(true)).toBe("/api/v1");
  expect(apiBase(false)).toBe(`${process.env.API_INTERNAL_URL ?? "http://backend:8000"}/api/v1`);
});

test("buildQuery drops empty values and repeats array keys", () => {
  expect(buildQuery({ q: "۲۰۶", models: ["پژو 206", "دنا"], page: 2, only_below: true, year: undefined, category: null, sort: "" }))
    .toBe("?q=%DB%B2%DB%B0%DB%B6&models=%D9%BE%DA%98%D9%88+206&models=%D8%AF%D9%86%D8%A7&page=2&only_below=true");
  expect(buildQuery({})).toBe("");
});

test("apiGet parses JSON and never lets the browser cache", async () => {
  const calls = stubFetch(json(200, facets));
  const body = await apiGet<Facets>("/facets", { category: "light" });
  expect(body.model_count).toBe(facets.model_count);
  expect(calls[0].url.endsWith("/api/v1/facets?category=light")).toBe(true);
  expect(calls[0].init?.cache).toBe("no-store");
});

test("an error envelope becomes an ApiError with the backend's code", async () => {
  stubFetch(json(404, error404));
  const error = await failure(apiGet("/listings/nope"));
  expect([error.status, error.code]).toEqual([404, "listing_not_found"]);
  expect(error.details).toEqual(error404.error.details);
});

test("apiPost sends JSON and surfaces 422 envelopes", async () => {
  const calls = stubFetch(json(422, error422));
  const error = await failure(apiPost("/estimates", { year: 1200 }));
  expect(calls[0].init?.method).toBe("POST");
  expect(calls[0].init?.body).toBe(JSON.stringify({ year: 1200 }));
  expect([error.code, error.message]).toEqual(["invalid_search", "Invalid search filters"]);
});

test("a non-JSON failure and a network failure are still ApiErrors", async () => {
  stubFetch(() => Promise.resolve(new Response("<html>bad gateway</html>", { status: 502, statusText: "Bad Gateway" })));
  const gateway = await failure(apiGet("/facets"));
  expect([gateway.status, gateway.code]).toEqual([502, "http_error"]);
  stubFetch(() => Promise.reject(new TypeError("fetch failed")));
  const offline = await failure(apiGet("/facets"));
  expect([offline.status, offline.code]).toEqual([0, "network_error"]);
});
````

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bun test`
Expected: `error: Cannot find module './base' from …/client.test.ts` and `38 pass, 1 fail, 1 error`.

- [ ] **Step 3: Implement**

`frontend/src/lib/api/__fixtures__/assistant.json` — written by the capture script (Step 1); do not hand-edit, commit it as generated.

`frontend/src/lib/api/__fixtures__/error-404.json` — written by the capture script (Step 1); do not hand-edit, commit it as generated.

`frontend/src/lib/api/__fixtures__/error-422.json` — written by the capture script (Step 1); do not hand-edit, commit it as generated.

`frontend/src/lib/api/__fixtures__/estimate.json` — written by the capture script (Step 1); do not hand-edit, commit it as generated.

`frontend/src/lib/api/__fixtures__/facets.json` — written by the capture script (Step 1); do not hand-edit, commit it as generated.

`frontend/src/lib/api/__fixtures__/listing.json` — written by the capture script (Step 1); do not hand-edit, commit it as generated.

`frontend/src/lib/api/__fixtures__/model-stats.json` — written by the capture script (Step 1); do not hand-edit, commit it as generated.

`frontend/src/lib/api/__fixtures__/search.json` — written by the capture script (Step 1); do not hand-edit, commit it as generated.

`frontend/src/lib/api/__fixtures__/similar.json` — written by the capture script (Step 1); do not hand-edit, commit it as generated.

`frontend/src/lib/api/__fixtures__/suggest.json` — written by the capture script (Step 1); do not hand-edit, commit it as generated.

Create `frontend/src/lib/api/base.ts`:

````ts
// The ONLY place the /api/v1 prefix and the backend host are known.
// Server Components run inside the Compose network and talk to the backend directly;
// the browser goes through Traefik on the same origin, so its base is relative.
const API_PREFIX = "/api/v1";
const DEFAULT_INTERNAL_URL = "http://backend:8000";

export function apiBase(inBrowser: boolean = typeof window !== "undefined"): string {
  if (inBrowser) return API_PREFIX;
  return `${process.env.API_INTERNAL_URL ?? DEFAULT_INTERNAL_URL}${API_PREFIX}`;
}
````

Create `frontend/src/lib/api/client.ts`:

````ts
import { apiBase } from "./base";
import type { ApiErrorBody } from "./types";

export type QueryValue = string | number | boolean | string[] | null | undefined;
export type QueryParams = Record<string, QueryValue>;

export const NETWORK_ERROR_STATUS = 0;

/** The backend's error envelope as an exception. Screens branch on `code`, never on `message`. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const isAbort = (error: unknown): boolean => error instanceof DOMException && error.name === "AbortError";

export function buildQuery(params: QueryParams): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((item) => query.append(key, item));
    else query.append(key, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as ApiErrorBody;
    return new ApiError(response.status, body.error.code, body.error.message, body.error.details);
  } catch {
    return new ApiError(response.status, "http_error", response.statusText || `HTTP ${response.status}`);
  }
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    // Redis already caches rankings server-side; the browser never caches API responses.
    response = await fetch(`${apiBase()}${path}`, { ...init, cache: "no-store" });
  } catch (error) {
    if (isAbort(error)) throw error;
    throw new ApiError(NETWORK_ERROR_STATUS, "network_error", "network failure");
  }
  if (!response.ok) throw await toApiError(response);
  return (await response.json()) as T;
}

export function apiGet<T>(path: string, params: QueryParams = {}, signal?: AbortSignal): Promise<T> {
  return request<T>(`${path}${buildQuery(params)}`, { method: "GET", signal });
}

export function apiPost<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body), headers: { "content-type": "application/json" }, signal });
}
````

Create `frontend/src/lib/api/types.ts`:

````ts
// Hand-written mirrors of the backend Pydantic schemas (backend/schemas/*.py).
// Money is integer toman; years are Jalali; dates are ISO strings.

export type Category = "light" | "heavy" | "motorcycle" | "rental" | "classic";
export type Gearbox = "manual" | "automatic";
export type Fuel = "petrol" | "dual_factory" | "dual_aftermarket" | "hybrid" | "plugin_hybrid" | "electric" | "diesel";
export type BodyCondition =
  | "intact" | "no_paint" | "minor_scratches" | "partial_paint" | "heavy_paint" | "dropped" | "accident" | "original" | "restored";
export type EstimateBasis = "trim_year" | "trim_near_year" | "model_year" | "model_near_year" | "none";
export type SortKey = "relevance" | "deal" | "price" | "km" | "newest";
export type Verdict = "cheap" | "fair" | "expensive" | "unknown";
export type ParsedBy = "llm" | "rules";
export type ChatRole = "user" | "assistant";

export interface ListingCard {
  id: string; token: string; title: string; category: Category;
  brand: string | null; model: string | null; trim: string | null;
  year: number | null; km: number | null; price: number | null;
  city: string; district: string | null; lat: number | null; lng: number | null;
  gearbox: Gearbox | null; fuel: Fuel | null; body_condition: BodyCondition | null; insurance_months: number | null;
  thumbnail_url: string | null; posted_at: string | null;
  est_price: number | null; diff_pct: number | null; deal_score: number | null; verdict: Verdict;
  match_score: number | null; is_exact: boolean; near_miss_labels: string[];
}

export interface PriceBreakdown {
  base: number | null; km_adjustment: number | null; insurance_adjustment: number | null;
  est_basis: EstimateBasis; est_sample_size: number;
}

export interface ListingDetail extends ListingCard {
  url: string; description: string; image_urls: string[]; color: string | null; is_dealer: boolean;
  attributes: Record<string, string>; price_breakdown: PriceBreakdown;
}

export interface VehicleMention { brand: string | null; model: string | null; trim: string | null; }

export interface SearchIntent {
  category: Category | null; vehicles: VehicleMention[]; year_min: number | null; year_max: number | null;
  price_min: number | null; price_max: number | null; km_max: number | null; cities: string[];
  gearbox: Gearbox | null; fuel: Fuel | null; colors: string[]; only_below_market: boolean; text: string | null; sort: SortKey;
}
export interface IntentRead extends SearchIntent { chips: string[]; }

export interface SearchResponse {
  intent: IntentRead; parsed_by: ParsedBy; total: number; exact_count: number; page: number; page_size: number; items: ListingCard[];
}

/** Query parameters of GET /search (backend `SearchParams`). Arrays repeat the key. */
export interface SearchParams {
  q?: string; category?: Category; models?: string[]; cities?: string[]; year?: number;
  price_max?: number; km_max?: number; gearbox?: Gearbox; only_below?: boolean; sort?: SortKey; page?: number; page_size?: number;
}

export interface FacetCount { value: string; count: number; }
export interface ModelFacet { brand: string; model: string; count: number; }
export interface Facets {
  categories: Partial<Record<Category, number>>; models: ModelFacet[]; cities: FacetCount[]; model_count: number; data_as_of: string | null;
}

export interface HistogramBucket { low: number; high: number; count: number; }
export interface TrimStat { trim: string; count: number; price_median: number | null; }
export interface ModelStats {
  model: string; brand: string; category: Category; count: number; year_min: number | null; year_max: number | null;
  price_median: number | null; price_min: number | null; price_max: number | null;
  histogram: HistogramBucket[]; trims: TrimStat[]; top_deals: ListingCard[];
}

export interface CatalogSuggestion { brand: string; model: string; trim: string; category: Category; count: number; }

export interface EstimateRequest {
  category: Category; trim: string; year: number; km: number | null; insurance_months: number | null;
  body_condition: BodyCondition | null; asking_price: number | null;
}
export interface EstimateBreakdown { base: number; km_adjustment: number; insurance_adjustment: number; }
export interface EstimateResponse {
  est_price: number; low: number; high: number; est_basis: EstimateBasis; est_sample_size: number; breakdown: EstimateBreakdown;
  asking_verdict: Verdict | null; asking_diff_pct: number | null; similar: ListingCard[];
}

export interface AssistantMessage { role: ChatRole; text: string; }
export interface AssistantRequest { messages: AssistantMessage[]; compare_ids: string[]; }
export interface AssistantResponse { text: string; listings: ListingCard[]; answered_by: ParsedBy; }

export interface ApiErrorBody { error: { code: string; message: string; details: unknown }; }
````

Create `frontend/src/lib/api/useApi.ts`:

````ts
"use client";
import { useCallback, useEffect, useEffectEvent, useState } from "react";
import { ApiError, isAbort } from "./client";

export interface ApiState<T> { data: T | null; error: ApiError | null; loading: boolean; retry(): void; }

type Fetcher<T> = (signal: AbortSignal) => Promise<T>;
interface Settled<T> { key: string; attempt: number; data: T | null; error: ApiError | null; }

const asApiError = (error: unknown): ApiError =>
  error instanceof ApiError ? error : new ApiError(0, "network_error", error instanceof Error ? error.message : "request failed");

/**
 * Fetch `key` with `fetcher`; a new key aborts the request in flight, so a superseded
 * response never overwrites a newer one. `key === null` means "nothing to fetch".
 * State is only set from the promise callbacks (never synchronously in the effect).
 */
export function useApi<T>(key: string | null, fetcher: Fetcher<T>): ApiState<T> {
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState<Settled<T>>({ key: "", attempt: -1, data: null, error: null });
  const run = useEffectEvent((signal: AbortSignal) => fetcher(signal)); // always the latest fetcher, never a dependency

  useEffect(() => {
    if (key === null) return;
    const controller = new AbortController();
    run(controller.signal)
      .then((data) => setSettled({ key, attempt, data, error: null }))
      .catch((error: unknown) => {
        if (isAbort(error) || controller.signal.aborted) return;
        setSettled({ key, attempt, data: null, error: asApiError(error) });
      });
    return () => controller.abort();
  }, [key, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  const current = key !== null && settled.key === key && settled.attempt === attempt;
  return {
    data: current ? settled.data : null,
    error: current ? settled.error : null,
    loading: key !== null && !current,
    retry,
  };
}
````

Create `frontend/src/lib/theme.ts`:

````ts
// Colour constants shared by verdict badges, score bars, map pins and breakdown rows.
export const RED = "#d9232e";
export const GREEN = "#15803d";
export const AMBER = "#b45309";
export const ORANGE = "#c2410c";
export const INK = "#172033";
export const NEUTRAL = "#667085";
````

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bun test && bunx tsc --noEmit && bun run lint`
Expected: `44 pass` (38 + 6), `tsc` and ESLint clean. Also from `backend/`: `uv run ruff check . && uv run black --check .` clean (the capture script is Python).

- [ ] **Step 5: Commit**

From the repo root (`cd ..`), stage explicit paths only (never `git add -A`):

````bash
git add backend/tests/fixtures/capture_api_fixtures.py frontend/src/lib/api/__fixtures__/assistant.json frontend/src/lib/api/__fixtures__/error-404.json frontend/src/lib/api/__fixtures__/error-422.json frontend/src/lib/api/__fixtures__/estimate.json frontend/src/lib/api/__fixtures__/facets.json frontend/src/lib/api/__fixtures__/listing.json frontend/src/lib/api/__fixtures__/model-stats.json frontend/src/lib/api/__fixtures__/search.json frontend/src/lib/api/__fixtures__/similar.json frontend/src/lib/api/__fixtures__/suggest.json frontend/src/lib/api/base.ts frontend/src/lib/api/client.test.ts frontend/src/lib/api/client.ts frontend/src/lib/api/types.ts frontend/src/lib/api/useApi.ts frontend/src/lib/theme.ts
git commit -m "feat(frontend): add the typed API client, useApi hook and captured fixtures

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git log -1 --format='%(trailers)'   # must print exactly: Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
````

---

### Task 7: Rewrite the frontend libs against the API types; delete the synthetic data

**Files:**
- Delete: `frontend/src/lib/assistant.test.ts`
- Delete: `frontend/src/lib/assistant.ts`
- Delete: `frontend/src/lib/catalog.ts`
- Create: `frontend/src/lib/compare.test.ts`
- Modify: `frontend/src/lib/compare.ts`
- Delete: `frontend/src/lib/estimate.ts`
- Modify: `frontend/src/lib/format.test.ts`
- Modify: `frontend/src/lib/format.ts`
- Create: `frontend/src/lib/labels.ts`
- Delete: `frontend/src/lib/listings.test.ts`
- Delete: `frontend/src/lib/listings.ts`
- Delete: `frontend/src/lib/modelStats.ts`
- Modify: `frontend/src/lib/pricing.test.ts`
- Modify: `frontend/src/lib/pricing.ts`
- Delete: `frontend/src/lib/screens.test.ts`
- Modify: `frontend/src/lib/search.test.ts`
- Modify: `frontend/src/lib/search.ts`
- Create: `frontend/src/lib/specs.test.ts`
- Create: `frontend/src/lib/specs.ts`
- Modify: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/view.test.ts`
- Modify: `frontend/src/lib/view.ts`

**Interfaces:**
- Consumes: `src/lib/api/types.ts`, the fixtures, `src/lib/theme.ts`.
- Produces: `lib/types.ts` (`VerdictStyle`, `BreakdownRow`, `ChatMessage { role, text, listings: ListingCard[] }`, `PriceAlert { title, params: SearchParams, threshold }`); `lib/labels.ts` (`CATEGORY_NAMES`, `GEARBOX_NAMES`, `FUEL_NAMES`, `BODY_NAMES`, `BASIS_NAMES`, `SORT_NAMES`, `BODY_CONDITION_CATEGORIES`, `CATEGORY_ORDER`); `lib/format.ts` (+`formatToman(amount)`, `relativeTime(postedAt, reference)`); `lib/pricing.ts` (`verdictStyle(verdict)`, `diffText(diff | null)`, `scoreColor`, `signedToman`, `deltaColor`, `basisText`, `breakdownRows(detail)`, `summaryOf(detail)`, `verdictNote(detail)`, `estimateBreakdownRows(result, request)`); `lib/view.ts` (`CardView` with `priceText`, `isExact`, `nearMissLabels`; `cardOf(card, dataAsOf?)`, `metaOf`, `PRICE_UNKNOWN`); `lib/compare.ts` `compareRows(cards: ListingCard[])` (9 rows, no tag row); `lib/specs.ts` `specsOf(detail) -> SpecRow[]`; `lib/search.ts` (`SearchOverrides`, `activeFilterCount`, `paramsToQuery`, `queryToParams`, `CATEGORIES`, `GEARBOXES`, `SORTS`, `DEFAULT_PAGE_SIZE = 20`).

Spec §4.2–§4.3. Everything the backend owns is deleted: `lib/listings.ts`, `catalog.ts`, `estimate.ts`, `modelStats.ts`, `assistant.ts` and their tests (`listings.test.ts`, `assistant.test.ts`, `screens.test.ts`); `search.ts` keeps only filter-sheet state; `pricing.ts` computes nothing — every number comes from the API breakdown. `cardOf` shows «توافقی» for a null price and «بدون تخمین» for an unknown verdict (never a made-up number). **After this task `bunx tsc --noEmit` is red** in every screen and component that still imports the deleted modules (`src/app/*`, `src/components/*`, `src/state/AppState.tsx`); that is expected until Task 12 — `bun test` must be green.

- [ ] **Step 1: Write the failing tests**

Delete `frontend/src/lib/assistant.test.ts`: `git rm frontend/src/lib/assistant.test.ts`

Create `frontend/src/lib/compare.test.ts`:

````ts
import { expect, test } from "bun:test";
import search from "./api/__fixtures__/search.json";
import type { ListingCard, SearchResponse } from "./api/types";
import { compareRows } from "./compare";

const cards = (search as SearchResponse).items.slice(0, 3);

test("compareRows: 9 rows, lowest price marked best, single card marks nothing", () => {
  const rows = compareRows(cards);
  expect(rows).toHaveLength(9);
  expect(rows.map((r) => r.label)).toEqual(["قیمت", "نسبت به بازار", "ارزش خرید", "سال ساخت", "کارکرد", "گیربکس", "وضعیت بدنه", "بیمه", "شهر"]);
  const prices = cards.map((c) => c.price ?? Infinity);
  expect(rows[0].cells[prices.indexOf(Math.min(...prices))].best).toBe(true);
  expect(compareRows([cards[0]]).flatMap((r) => r.cells).some((c) => c.best)).toBe(false);
  expect(compareRows([])).toEqual([]);
});

test("unknown values render as a dash and never win a row", () => {
  const unknown: ListingCard = { ...cards[0], price: null, deal_score: null, diff_pct: null, gearbox: null, insurance_months: null };
  const rows = compareRows([unknown, cards[1]]);
  expect(rows[0].cells[0].text).toBe("توافقی");
  expect(rows[0].cells[0].best).toBe(false);
  expect(rows[0].cells[1].best).toBe(true);
  expect(rows[2].cells[0].text).toBe("—");
  expect(rows[5].cells[0].text).toBe("—");
});
````

Modify `frontend/src/lib/format.test.ts` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/lib/format.test.ts b/frontend/src/lib/format.test.ts
index f97b75f..e88af36 100644
--- a/frontend/src/lib/format.test.ts
+++ b/frontend/src/lib/format.test.ts
@@ -1,5 +1,5 @@
 import { expect, test } from "bun:test";
-import { en, fa, num } from "./format";
+import { en, fa, formatToman, num, relativeTime } from "./format";

 test("fa converts latin digits to persian", () => {
   expect(fa(1403)).toBe("۱۴۰۳");
@@ -13,3 +13,20 @@ test("num rounds, groups thousands, and uses persian digits", () => {
   expect(num(62000)).toBe("۶۲,۰۰۰");
   expect(num(669.6)).toBe("۶۷۰");
 });
+test("formatToman uses the backend's millions/billions wording", () => {
+  expect(formatToman(970_000_000)).toBe("۹۷۰ میلیون");
+  expect(formatToman(1_200_000_000)).toBe("۱.۲ میلیارد");
+  expect(formatToman(1_000_000_000)).toBe("۱ میلیارد");
+  expect(formatToman(1_155_000_000)).toBe("۱.۱۶ میلیارد");
+  expect(formatToman(4_598_198)).toBe("۵ میلیون");
+});
+test("relativeTime buckets the age of a listing against the data snapshot", () => {
+  const asOf = "2026-09-17T16:43:20Z";
+  expect(relativeTime("2026-09-17T16:20:00Z", asOf)).toBe("دقایقی پیش");
+  expect(relativeTime("2026-09-17T10:38:38Z", asOf)).toBe("۶ ساعت پیش");
+  expect(relativeTime("2026-09-16T12:00:00Z", asOf)).toBe("دیروز");
+  expect(relativeTime("2026-09-14T12:12:31Z", asOf)).toBe("۳ روز پیش");
+  expect(relativeTime("2026-09-01T12:00:00Z", asOf)).toBe("۲ هفته پیش");
+  expect(relativeTime("2026-06-01T12:00:00Z", asOf)).toBe("۳ ماه پیش");
+  expect(relativeTime(null, asOf)).toBe("");
+});
````

Delete `frontend/src/lib/listings.test.ts`: `git rm frontend/src/lib/listings.test.ts`

Modify `frontend/src/lib/pricing.test.ts` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/lib/pricing.test.ts b/frontend/src/lib/pricing.test.ts
index 865ff51..d7f3e57 100644
--- a/frontend/src/lib/pricing.test.ts
+++ b/frontend/src/lib/pricing.test.ts
@@ -1,46 +1,51 @@
 import { expect, test } from "bun:test";
-import { BODIES, MODELS } from "./catalog";
-import { diffText, priceModel, scoreColor, verdictOf } from "./pricing";
+import estimate from "./api/__fixtures__/estimate.json";
+import listing from "./api/__fixtures__/listing.json";
+import type { EstimateResponse, ListingDetail } from "./api/types";
+import { formatToman } from "./format";
+import { basisText, breakdownRows, diffText, estimateBreakdownRows, scoreColor, summaryOf, verdictNote, verdictStyle } from "./pricing";
+import { GREEN, NEUTRAL, RED } from "./theme";

-const peugeot206 = MODELS.find((m) => m.id === "206")!;
-const dena = MODELS.find((m) => m.id === "dena")!;
-const EXPECTED_KM_FOR_1401 = 62000; // age 3 × 18000 + 8000
+const detail = listing as ListingDetail;

-test("neutral inputs return the base price", () => {
-  const r = priceModel(peugeot206, 1401, EXPECTED_KM_FOR_1401, BODIES[0], "دنده‌ای", 6);
-  expect(r.base).toBe(670);
-  expect(r.expKm).toBe(EXPECTED_KM_FOR_1401);
-  expect(r.est).toBeCloseTo(670, 6);
-});
-test("est is the product of all factors and parts are base × (factor − 1)", () => {
-  const r = priceModel(dena, 1401, 100000, BODIES[2], "اتوماتیک", 12);
-  expect(r.est).toBeCloseTo(r.base * BODIES[2].f * r.kmF * r.insF * r.gearF, 6);
-  expect(r.parts.body).toBeCloseTo(r.base * (BODIES[2].f - 1), 6);
-  expect(r.parts.km).toBeCloseTo(r.base * (r.kmF - 1), 6);
-});
-test("km factor clamps at +4% and −8%", () => {
-  expect(priceModel(peugeot206, 1401, 0, BODIES[0], "دنده‌ای", 6).kmF).toBeCloseTo(1.04, 6);
-  expect(priceModel(peugeot206, 1401, 900000, BODIES[0], "دنده‌ای", 6).kmF).toBeCloseTo(0.92, 6);
-});
-test("automatic premium applies only to models with two gearboxes", () => {
-  expect(priceModel(dena, 1401, EXPECTED_KM_FOR_1401, BODIES[0], "اتوماتیک", 6).gearF).toBe(1.06);
-  const j4 = MODELS.find((m) => m.id === "j4")!;
-  expect(priceModel(j4, 1401, EXPECTED_KM_FOR_1401, BODIES[0], "اتوماتیک", 6).gearF).toBe(1);
-});
-test("unknown model year throws", () => {
-  expect(() => priceModel(peugeot206, 1380, 1000, BODIES[0], "دنده‌ای", 6)).toThrow(RangeError);
-});
-test("verdict thresholds are −5 and +6", () => {
-  expect(verdictOf(-5).label).toBe("ارزان‌تر از بازار");
-  expect(verdictOf(-4.9).label).toBe("قیمت منصفانه");
-  expect(verdictOf(5.9).label).toBe("قیمت منصفانه");
-  expect(verdictOf(6).label).toBe("بالاتر از بازار");
+test("verdictStyle maps the API enum, including unknown", () => {
+  expect(verdictStyle("cheap").label).toBe("ارزان‌تر از بازار");
+  expect(verdictStyle("fair").label).toBe("قیمت منصفانه");
+  expect(verdictStyle("expensive").label).toBe("بالاتر از بازار");
+  expect(verdictStyle("unknown").color).toBe(NEUTRAL);
 });
 test("diffText and scoreColor", () => {
   expect(diffText(7.4)).toBe("۷٪ بالاتر از تخمین");
   expect(diffText(-12)).toBe("۱۲٪ ارزان‌تر از تخمین");
   expect(diffText(0.2)).toBe("برابر تخمین بازار");
-  expect(scoreColor(70)).toBe("#15803d");
+  expect(diffText(null)).toBe("تخمینی برای این آگهی نداریم");
+  expect(scoreColor(70)).toBe(GREEN);
   expect(scoreColor(45)).toBe("#b45309");
-  expect(scoreColor(44)).toBe("#d9232e");
+  expect(scoreColor(44)).toBe(RED);
+});
+test("breakdownRows: base, km and insurance from the API breakdown, basis in words", () => {
+  const rows = breakdownRows(detail);
+  expect(rows.map((r) => r.label)).toEqual(["قیمت پایهٔ تیپ و سال", "کارکرد", "بیمهٔ شخص ثالث"]);
+  expect(rows[0].note).toBe(basisText(detail.price_breakdown.est_basis, detail.price_breakdown.est_sample_size));
+  expect(rows[0].note).toContain("میانهٔ ۸ آگهی همین تیپ و سال");
+  expect(rows[1].val.startsWith("+") || rows[1].val.startsWith("−")).toBe(true);
+});
+test("breakdownRows is empty without an estimate", () => {
+  const none: ListingDetail = { ...detail, price_breakdown: { base: null, km_adjustment: null, insurance_adjustment: null, est_basis: "none", est_sample_size: 0 } };
+  expect(breakdownRows(none)).toEqual([]);
+});
+test("summaryOf and verdictNote use real fields only", () => {
+  const summary = summaryOf(detail);
+  expect(summary).toContain(detail.trim!);
+  expect(summary).toContain("ارزان‌تر از تخمین بازار");
+  expect(verdictNote(detail)).toContain("زیر تخمین ماست");
+  const noEstimate: ListingDetail = { ...detail, est_price: null, verdict: "unknown" };
+  expect(summaryOf(noEstimate)).toContain("تخمین قیمت نداریم");
+  expect(verdictNote(noEstimate)).toContain("کافی برای تخمین نداریم");
+});
+test("estimateBreakdownRows mirrors the /estimates breakdown", () => {
+  const rows = estimateBreakdownRows(estimate as EstimateResponse, { category: "light", trim: "x", year: 1397, km: 90000, insurance_months: 6, body_condition: null, asking_price: null });
+  expect(rows).toHaveLength(3);
+  expect(rows[0].val).toBe(formatToman(estimate.breakdown.base));
+  expect(rows[1].note).toBe("۹۰,۰۰۰ کیلومتر");
 });
````

Delete `frontend/src/lib/screens.test.ts`: `git rm frontend/src/lib/screens.test.ts`

Modify `frontend/src/lib/search.test.ts` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/lib/search.test.ts b/frontend/src/lib/search.test.ts
index 911019d..e704764 100644
--- a/frontend/src/lib/search.test.ts
+++ b/frontend/src/lib/search.test.ts
@@ -1,76 +1,24 @@
 import { expect, test } from "bun:test";
-import { LISTINGS } from "./listings";
-import { DEFAULT_FILTERS, activeFilterCount, alertMatches, chipsOf, filterListings, filtersFromQuery, parseQuery, sortListings } from "./search";
+import { activeFilterCount, paramsToQuery, queryToParams } from "./search";

-test("home example: 206 low-mileage Tehran", () => {
-  const p = parseQuery("پژو ۲۰۶ کم‌کارکرد تهران");
-  expect(p).toMatchObject({ models: ["206"], city: "تهران", maxKm: 90, maxPrice: null, gear: null });
+test("queryToParams keeps valid values and drops junk", () => {
+  const query = new URLSearchParams("q=۲۰۶&category=light&models=پژو 206&models=دنا&cities=تهران&year=1398&price_max=900000000&km_max=abc&gearbox=auto&only_below=true&sort=price&page=3");
+  expect(queryToParams(query)).toEqual({
+    q: "۲۰۶", category: "light", models: ["پژو 206", "دنا"], cities: ["تهران"], year: 1398, price_max: 900000000, only_below: true, sort: "price",
+  });
+  expect(queryToParams(new URLSearchParams("category=spaceship&sort=random&year=-5"))).toEqual({});
 });
-test("home example: Dena automatic under one billion (words)", () => {
-  const p = parseQuery("دنا پلاس اتومات زیر یک میلیارد");
-  expect(p).toMatchObject({ models: ["dena"], maxPrice: 1000, gear: "اتوماتیک" });
-});
-test("home example: Tara cheaper than market", () => {
-  expect(parseQuery("تارا ارزان‌تر از بازار")).toMatchObject({ models: ["tara"], onlyBelow: true, maxPrice: null });
-});
-test("home example: JAC under 900 million", () => {
-  expect(parseQuery("جک J4 زیر ۹۰۰ میلیون")).toMatchObject({ models: ["j4"], maxPrice: 900 });
-});
-test("placeholder query: price is not mistaken for mileage", () => {
-  expect(parseQuery("پژو ۲۰۶ کم‌کارکرد زیر ۷۰۰ میلیون، تهران")).toMatchObject({ maxPrice: 700, maxKm: 90 });
-});
-test("decimal billions, explicit km, year, arabic letters", () => {
-  expect(parseQuery("زیر 1.2 میلیارد").maxPrice).toBe(1200);
-  expect(parseQuery("دنا کارکرد زیر ۵۰ هزار کیلومتر").maxKm).toBe(50);
-  expect(parseQuery("تارا مدل ۱۴۰۲ دنده").year).toBe(1402);
-  expect(parseQuery("تارا مدل ۱۴۰۲ دنده").gear).toBe("دنده‌ای");
-  expect(parseQuery("كرج").city).toBe("کرج");
-});
-test("chips and filters derive from the parsed query", () => {
-  const p = parseQuery("دنا پلاس اتومات زیر یک میلیارد کرج");
-  expect(chipsOf(p)).toEqual(["دنا پلاس", "زیر ۱,۰۰۰ میلیون", "کرج", "اتوماتیک"]);
-  expect(filtersFromQuery(p)).toEqual({ ...DEFAULT_FILTERS, models: ["dena"], cities: ["کرج"], maxPrice: 1000, gear: "اتوماتیک" });
-});
-test("each filter narrows results", () => {
-  expect(filterListings(LISTINGS, DEFAULT_FILTERS)).toHaveLength(LISTINGS.length);
-  expect(filterListings(LISTINGS, { ...DEFAULT_FILTERS, models: ["tara"] }).every((l) => l.modelId === "tara")).toBe(true);
-  expect(filterListings(LISTINGS, { ...DEFAULT_FILTERS, cities: ["کرج"] }).every((l) => l.city === "کرج")).toBe(true);
-  expect(filterListings(LISTINGS, { ...DEFAULT_FILTERS, maxPrice: 700 }).every((l) => l.price <= 700)).toBe(true);
-  expect(filterListings(LISTINGS, { ...DEFAULT_FILTERS, maxKm: 50 }).every((l) => l.km <= 50000)).toBe(true);
-  expect(filterListings(LISTINGS, { ...DEFAULT_FILTERS, gear: "اتوماتیک" }).every((l) => l.gear === "اتوماتیک")).toBe(true);
-  expect(filterListings(LISTINGS, { ...DEFAULT_FILTERS, onlyBelow: true }).every((l) => l.diffPct <= -5)).toBe(true);
-  expect(filterListings(LISTINGS, { ...DEFAULT_FILTERS, year: 1401 }).every((l) => l.year === 1401)).toBe(true);
-});
-test("sorting does not mutate and orders correctly", () => {
-  const copy = [...LISTINGS];
-  const byPrice = sortListings(LISTINGS, "price");
-  expect(LISTINGS).toEqual(copy);
-  expect(byPrice[0].price).toBe(Math.min(...LISTINGS.map((l) => l.price)));
-  expect(sortListings(LISTINGS, "km")[0].km).toBe(Math.min(...LISTINGS.map((l) => l.km)));
-  expect(sortListings(LISTINGS, "score")[0].score).toBe(Math.max(...LISTINGS.map((l) => l.score)));
-  expect(sortListings(LISTINGS, "new")[0].postedIdx).toBe(Math.min(...LISTINGS.map((l) => l.postedIdx)));
-});
-test("regression: a mileage-only clause is never mistaken for a price", () => {
-  const p = parseQuery("دنا کارکرد زیر ۵۰ هزار کیلومتر");
-  expect(p.maxPrice).toBeNull();
-  expect(p.maxKm).toBe(50);
-  expect(filterListings(LISTINGS, filtersFromQuery(p)).length).toBeGreaterThan(0);
-});
-test("regression: an explicit میلیون unit is never upgraded to billions by magnitude", () => {
-  expect(parseQuery("زیر ۴ میلیون").maxPrice).toBe(4);
-});
-test("regression: price parser skips a mileage clause to find a genuine price clause", () => {
-  const p = parseQuery("زیر ۷۰۰ میلیون کارکرد زیر ۵۰ هزار کیلومتر");
-  expect(p.maxPrice).toBe(700);
-  expect(p.maxKm).toBe(50);
-});
-test("activeFilterCount counts non-default filters", () => {
-  expect(activeFilterCount(DEFAULT_FILTERS)).toBe(0);
-  expect(activeFilterCount({ ...DEFAULT_FILTERS, models: ["206", "tara"], maxKm: 100, onlyBelow: true })).toBe(4);
+
+test("paramsToQuery round-trips and omits defaults", () => {
+  const params = { q: "دنا", cities: ["کرج"], price_max: 1_000_000_000, sort: "relevance" as const, only_below: false };
+  const query = paramsToQuery(params);
+  expect(query).not.toContain("sort=");
+  expect(query).not.toContain("only_below");
+  expect(queryToParams(new URLSearchParams(query))).toEqual({ q: "دنا", cities: ["کرج"], price_max: 1_000_000_000 });
+  expect(paramsToQuery({})).toBe("");
 });
-test("alertMatches includes a listing priced exactly at the threshold", () => {
-  const threshold = LISTINGS[0].price;
-  expect(alertMatches(LISTINGS, threshold)).toBe(LISTINGS.filter((l) => l.price <= threshold).length);
-  expect(alertMatches([{ ...LISTINGS[0], price: 500 }], 500)).toBe(1);
-  expect(alertMatches([{ ...LISTINGS[0], price: 501 }], 500)).toBe(0);
+
+test("activeFilterCount counts every set filter", () => {
+  expect(activeFilterCount({})).toBe(0);
+  expect(activeFilterCount({ q: "x", models: ["a", "b"], km_max: 100000, only_below: true, category: "light" })).toBe(5);
 });
````

Create `frontend/src/lib/specs.test.ts`:

````ts
import { expect, test } from "bun:test";
import listing from "./api/__fixtures__/listing.json";
import type { ListingDetail } from "./api/types";
import { specsOf } from "./specs";

const detail = listing as ListingDetail;

test("specsOf lists typed fields and Divar attributes, hiding empty rows", () => {
  const rows = specsOf(detail);
  const keys = rows.map((r) => r.k);
  expect(keys).toContain("برند و مدل");
  expect(keys).toContain("گیربکس");
  expect(keys).toContain("مالکیت"); // from attributes
  expect(rows.every((r) => r.v !== "")).toBe(true);
  expect(keys).not.toContain("وضعیت بدنه"); // null for this car
});

test("motorcycles show engine size from attributes and no gearbox row", () => {
  const moto: ListingDetail = {
    ...detail, category: "motorcycle", gearbox: null, fuel: null, body_condition: "intact",
    attributes: { "حجم موتور": "۱۶۰ سی‌سی", "نوع کلاچ": "اتوماتیک" },
  };
  const rows = specsOf(moto);
  expect(rows.find((r) => r.k === "حجم موتور")?.v).toBe("۱۶۰ سی‌سی");
  expect(rows.find((r) => r.k === "نوع کلاچ")?.v).toBe("اتوماتیک");
  expect(rows.find((r) => r.k === "وضعیت بدنه")?.v).toBe("سالم و بی‌خط و خش");
  expect(rows.some((r) => r.k === "گیربکس")).toBe(false);
});
````

Create `frontend/src/lib/view.test.ts`:

````ts
import { expect, test } from "bun:test";
import search from "./api/__fixtures__/search.json";
import type { ListingCard, SearchResponse } from "./api/types";
import { PRICE_UNKNOWN, cardOf, metaOf } from "./view";

const items = (search as SearchResponse).items;
const first = items[0];
const AS_OF = "2026-09-17T16:43:20Z";

test("cardOf builds href, title, meta and price from a real card", () => {
  const c = cardOf(first, AS_OF);
  expect(c.href).toBe(`/listing/${first.id}`);
  expect(c.title).toBe(String(first.trim));
  expect(c.meta).toContain(first.city);
  expect(c.meta).toContain("کیلومتر");
  expect(c.meta).toContain("دنده‌ای");
  expect(c.priceText).toMatch(/میلیون|میلیارد/);
  expect(c.img).toBe(String(first.thumbnail_url));
  expect(c.posted).not.toBe("");
  expect(c.isExact).toBe(true);
});

test("near-miss cards keep their labels", () => {
  const nearMiss = items.find((item) => !item.is_exact)!;
  const c = cardOf(nearMiss, AS_OF);
  expect(c.isExact).toBe(false);
  expect(c.nearMissLabels).toEqual(nearMiss.near_miss_labels);
  expect(c.nearMissLabels.length).toBeGreaterThan(0);
});

test("unknown price, score and verdict render as neutral text, never as numbers", () => {
  const unknown: ListingCard = { ...first, price: null, deal_score: null, diff_pct: null, verdict: "unknown", gearbox: null, body_condition: null, insurance_months: null, year: null, km: null, thumbnail_url: null };
  const c = cardOf(unknown, AS_OF);
  expect(c.priceText).toBe(PRICE_UNKNOWN);
  expect(c.scoreFa).toBe("—");
  expect(c.score).toBe(0);
  expect(c.verdict.label).toBe("بدون تخمین");
  expect(c.diffText).toBe("تخمینی برای این آگهی نداریم");
  expect(c.body).toBe("—");
  expect(metaOf(unknown)).toBe(unknown.district ? `${unknown.city}، ${unknown.district}` : unknown.city);
  expect(c.img).toBe("/icons/icon-192.png");
});
````

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bun test`
Expected: failures such as `Export named 'formatToman' not found in module …/format.ts`, `Cannot find module './specs'`, `Export named 'queryToParams' not found`, plus `TypeError: undefined is not an object (evaluating 'l.body.f')` from the old `compare.ts`.

- [ ] **Step 3: Implement**

Delete `frontend/src/lib/assistant.ts`: `git rm frontend/src/lib/assistant.ts`

Delete `frontend/src/lib/catalog.ts`: `git rm frontend/src/lib/catalog.ts`

Modify `frontend/src/lib/compare.ts` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/lib/compare.ts b/frontend/src/lib/compare.ts
index 3f09bca..91efbf5 100644
--- a/frontend/src/lib/compare.ts
+++ b/frontend/src/lib/compare.ts
@@ -1,40 +1,45 @@
-import { fa, num } from "./format";
-import { diffText, scoreColor, verdictOf } from "./pricing";
-import type { Listing } from "./types";
+import type { ListingCard } from "./api/types";
+import { fa, formatToman, num } from "./format";
+import { BODY_NAMES, GEARBOX_NAMES } from "./labels";
+import { diffText, scoreColor, verdictStyle } from "./pricing";
+import { INK } from "./theme";

 export interface CompareCell { text: string; color: string; best: boolean; }
 export interface CompareRow { label: string; cells: CompareCell[]; }

-const INK = "#172033";
 type Better = (a: number, b: number) => boolean;
 const lower: Better = (a, b) => a < b;
 const higher: Better = (a, b) => a > b;
+const DASH = "—";

-function indexOfBest(values: number[], better: Better): number {
-  return values.reduce((best, v, i) => (best === -1 || better(v, values[best]) ? i : best), -1);
+/** Index of the best known value; unknown (null) values never win. */
+function indexOfBest(values: (number | null)[], better: Better): number {
+  return values.reduce<number>((best, v, i) => (v !== null && (best === -1 || better(v, values[best] as number)) ? i : best), -1);
 }

-function numericRow(label: string, cars: Listing[], get: (l: Listing) => number, text: (l: Listing) => string, better: Better, color: (v: number) => string = () => INK): CompareRow {
-  const values = cars.map(get);
-  const best = cars.length > 1 ? indexOfBest(values, better) : -1;
-  return { label, cells: cars.map((l, i) => ({ text: text(l), color: color(values[i]), best: i === best })) };
+function numericRow(
+  label: string, cards: ListingCard[], get: (l: ListingCard) => number | null, text: (l: ListingCard) => string, better: Better,
+  color: (v: number | null) => string = () => INK,
+): CompareRow {
+  const values = cards.map(get);
+  const best = cards.length > 1 ? indexOfBest(values, better) : -1;
+  return { label, cells: cards.map((l, i) => ({ text: text(l), color: color(values[i]), best: i === best })) };
 }

-const textRow = (label: string, cars: Listing[], text: (l: Listing) => string): CompareRow =>
-  ({ label, cells: cars.map((l) => ({ text: text(l), color: INK, best: false })) });
+const textRow = (label: string, cards: ListingCard[], text: (l: ListingCard) => string): CompareRow =>
+  ({ label, cells: cards.map((l) => ({ text: text(l), color: INK, best: false })) });

-export function compareRows(cars: Listing[]): CompareRow[] {
-  if (!cars.length) return [];
+export function compareRows(cards: ListingCard[]): CompareRow[] {
+  if (!cards.length) return [];
   return [
-    numericRow("قیمت", cars, (l) => l.price, (l) => `${num(l.price)} میلیون`, lower),
-    numericRow("نسبت به بازار", cars, (l) => l.diffPct, (l) => diffText(l.diffPct), lower, (v) => verdictOf(v).color),
-    numericRow("ارزش خرید", cars, (l) => l.score, (l) => `${fa(l.score)}/۱۰۰`, higher, scoreColor),
-    numericRow("سال ساخت", cars, (l) => l.year, (l) => fa(l.year), higher),
-    numericRow("کارکرد", cars, (l) => l.km, (l) => `${num(l.km)} کیلومتر`, lower),
-    textRow("گیربکس", cars, (l) => l.gear),
-    numericRow("وضعیت بدنه", cars, (l) => l.body.f, (l) => l.body.name, higher),
-    numericRow("بیمه", cars, (l) => l.ins, (l) => `${fa(l.ins)} ماه`, higher),
-    textRow("شهر", cars, (l) => l.city),
-    textRow("نکات آگهی", cars, (l) => l.tags.join("، ") || "—"),
+    numericRow("قیمت", cards, (l) => l.price, (l) => (l.price === null ? "توافقی" : formatToman(l.price)), lower),
+    numericRow("نسبت به بازار", cards, (l) => l.diff_pct, (l) => diffText(l.diff_pct), lower, (v) => verdictStyle(v === null ? "unknown" : v <= -5 ? "cheap" : v >= 6 ? "expensive" : "fair").color),
+    numericRow("ارزش خرید", cards, (l) => l.deal_score, (l) => (l.deal_score === null ? DASH : `${fa(l.deal_score)}/۱۰۰`), higher, (v) => (v === null ? INK : scoreColor(v))),
+    numericRow("سال ساخت", cards, (l) => l.year, (l) => (l.year === null ? DASH : fa(l.year)), higher),
+    numericRow("کارکرد", cards, (l) => l.km, (l) => (l.km === null ? DASH : `${num(l.km)} کیلومتر`), lower),
+    textRow("گیربکس", cards, (l) => (l.gearbox ? GEARBOX_NAMES[l.gearbox] : DASH)),
+    textRow("وضعیت بدنه", cards, (l) => (l.body_condition ? BODY_NAMES[l.body_condition] : DASH)),
+    numericRow("بیمه", cards, (l) => l.insurance_months, (l) => (l.insurance_months === null ? DASH : `${fa(l.insurance_months)} ماه`), higher),
+    textRow("شهر", cards, (l) => (l.district ? `${l.city}، ${l.district}` : l.city)),
   ];
 }
````

Delete `frontend/src/lib/estimate.ts`: `git rm frontend/src/lib/estimate.ts`

Modify `frontend/src/lib/format.ts` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/lib/format.ts b/frontend/src/lib/format.ts
index 4e05a1d..e88af5d 100644
--- a/frontend/src/lib/format.ts
+++ b/frontend/src/lib/format.ts
@@ -1,5 +1,12 @@
 const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
 const AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";
+const TOMAN_PER_MILLION = 1_000_000;
+const MILLIONS_PER_BILLION = 1_000;
+const MINUTE_MS = 60_000;
+const HOUR_MS = 60 * MINUTE_MS;
+const DAY_MS = 24 * HOUR_MS;
+const WEEK_MS = 7 * DAY_MS;
+const MONTH_MS = 30 * DAY_MS;

 export const fa = (value: string | number): string =>
   String(value).replace(/\d/g, (d) => FA_DIGITS[Number(d)]);
@@ -10,3 +17,25 @@ export const en = (value: string | number): string =>
     .replace(/[٠-٩]/g, (d) => String(AR_DIGITS.indexOf(d)));

 export const num = (n: number): string => fa(Math.round(n).toLocaleString("en-US"));
+
+/** Toman → «۹۷۰ میلیون» / «۱.۲ میلیارد», the same wording as the backend's labels. */
+export function formatToman(amount: number): string {
+  const millions = Math.round(amount / TOMAN_PER_MILLION);
+  if (millions >= MILLIONS_PER_BILLION) {
+    const billions = (millions / MILLIONS_PER_BILLION).toFixed(2).replace(/\.?0+$/, "");
+    return `${fa(billions)} میلیارد`;
+  }
+  return `${fa(millions)} میلیون`;
+}
+
+/** «۳ روز پیش»-style age of `postedAt` relative to `reference` (usually the data snapshot). */
+export function relativeTime(postedAt: string | null, reference: string | Date): string {
+  if (!postedAt) return "";
+  const elapsed = new Date(reference).getTime() - new Date(postedAt).getTime();
+  if (Number.isNaN(elapsed) || elapsed < HOUR_MS) return "دقایقی پیش";
+  if (elapsed < DAY_MS) return `${fa(Math.floor(elapsed / HOUR_MS))} ساعت پیش`;
+  if (elapsed < 2 * DAY_MS) return "دیروز";
+  if (elapsed < WEEK_MS) return `${fa(Math.floor(elapsed / DAY_MS))} روز پیش`;
+  if (elapsed < MONTH_MS) return `${fa(Math.floor(elapsed / WEEK_MS))} هفته پیش`;
+  return `${fa(Math.floor(elapsed / MONTH_MS))} ماه پیش`;
+}
````

Create `frontend/src/lib/labels.ts`:

````ts
// Persian names for the API's closed vocabularies (backend/enums.py).
import type { BodyCondition, Category, EstimateBasis, Fuel, Gearbox, SortKey } from "./api/types";

export const CATEGORY_NAMES: Record<Category, string> = {
  light: "سواری و شاسی‌بلند", heavy: "سنگین و نیمه‌سنگین", motorcycle: "موتورسیکلت", rental: "اجاره", classic: "کلاسیک",
};
export const GEARBOX_NAMES: Record<Gearbox, string> = { manual: "دنده‌ای", automatic: "اتوماتیک" };
export const FUEL_NAMES: Record<Fuel, string> = {
  petrol: "بنزینی", dual_factory: "دوگانه‌سوز شرکتی", dual_aftermarket: "دوگانه‌سوز دستی", hybrid: "هیبرید",
  plugin_hybrid: "پلاگین هیبرید", electric: "برقی", diesel: "گازوئیلی",
};
export const BODY_NAMES: Record<BodyCondition, string> = {
  intact: "سالم و بی‌خط و خش", no_paint: "بدون رنگ", minor_scratches: "خط و خش جزئی", partial_paint: "رنگ‌شدگی جزئی",
  heavy_paint: "رنگ‌شدگی زیاد", dropped: "زمین‌خوردگی", accident: "تصادفی", original: "فابریک", restored: "بازسازی‌شدهٔ کامل",
};
export const BASIS_NAMES: Record<EstimateBasis, string> = {
  trim_year: "همین تیپ و سال", trim_near_year: "همین تیپ، سال‌های مجاور", model_year: "همین مدل و سال",
  model_near_year: "همین مدل، سال‌های مجاور", none: "بدون تخمین",
};
export const SORT_NAMES: Record<SortKey, string> = {
  relevance: "مرتبط‌ترین", deal: "بهترین ارزش خرید", price: "ارزان‌ترین", km: "کم‌کارکردترین", newest: "جدیدترین",
};
/** Categories whose listings carry a body-condition field on Divar. */
export const BODY_CONDITION_CATEGORIES: Category[] = ["motorcycle", "heavy"];
export const CATEGORY_ORDER: Category[] = ["light", "motorcycle", "heavy", "classic", "rental"];
````

Delete `frontend/src/lib/listings.ts`: `git rm frontend/src/lib/listings.ts`

Delete `frontend/src/lib/modelStats.ts`: `git rm frontend/src/lib/modelStats.ts`

Modify `frontend/src/lib/pricing.ts` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/lib/pricing.ts b/frontend/src/lib/pricing.ts
index 49d5a95..890ad3a 100644
--- a/frontend/src/lib/pricing.ts
+++ b/frontend/src/lib/pricing.ts
@@ -1,72 +1,78 @@
-import { AMBER, GREEN, NOW_YEAR, RED, isNegativeIssue } from "./catalog";
-import { fa, num } from "./format";
-import type { BodyCondition, BreakdownRow, CarModel, Gear, Listing, PriceModelResult, Verdict } from "./types";
+import type { EstimateBasis, EstimateRequest, EstimateResponse, ListingDetail, Verdict } from "./api/types";
+import { fa, formatToman, num } from "./format";
+import { BASIS_NAMES, BODY_NAMES } from "./labels";
+import { AMBER, GREEN, INK, NEUTRAL, RED } from "./theme";
+import type { BreakdownRow, VerdictStyle } from "./types";

-const KM_PER_YEAR = 18000;
-const KM_BASELINE = 8000;
-const KM_WEIGHT = 0.08;
-const INSURANCE_NEUTRAL_MONTHS = 6;
-const INSURANCE_WEIGHT_PER_MONTH = 0.002;
-const AUTOMATIC_PREMIUM = 1.06;
-export const CHEAP_THRESHOLD_PCT = -5;
-export const EXPENSIVE_THRESHOLD_PCT = 6;
-const NEUTRAL_COLOR = "#667085";
-const INK = "#172033";
+const VERDICTS: Record<Verdict, VerdictStyle> = {
+  cheap: { label: "ارزان‌تر از بازار", color: GREEN, bg: "#ecfdf3", icon: "M16 17h6v-6M22 17l-8.5-8.5-5 5L2 7" },
+  expensive: { label: "بالاتر از بازار", color: RED, bg: "#fdecec", icon: "M16 7h6v6M22 7l-8.5 8.5-5-5L2 17" },
+  fair: { label: "قیمت منصفانه", color: AMBER, bg: "#fffbeb", icon: "M20 6 9 17l-5-5" },
+  unknown: { label: "بدون تخمین", color: NEUTRAL, bg: "#f1f3f6", icon: "M12 8v4M12 16h.01" },
+};
+const NO_ESTIMATE_TEXT = "تخمینی برای این آگهی نداریم";
+const HIGH_KM_FACTOR = 1.02;
+const LOW_KM_FACTOR = 0.97;

-export function priceModel(model: CarModel, year: number, km: number, body: BodyCondition, gear: Gear, insMonths: number): PriceModelResult {
-  const base = model.base[year];
-  if (base === undefined) throw new RangeError(`No base price for ${model.id} year ${year}`);
-  const age = Math.max(0.5, NOW_YEAR - year);
-  const expKm = age * KM_PER_YEAR + KM_BASELINE;
-  const kmF = 1 - Math.max(-0.5, Math.min(1, (km - expKm) / expKm)) * KM_WEIGHT;
-  const insF = 1 + (insMonths - INSURANCE_NEUTRAL_MONTHS) * INSURANCE_WEIGHT_PER_MONTH;
-  const gearF = gear === "اتوماتیک" && model.gears.length > 1 ? AUTOMATIC_PREMIUM : 1;
-  const est = base * body.f * kmF * insF * gearF;
-  return { base, expKm, kmF, insF, gearF, est, parts: { km: base * (kmF - 1), body: base * (body.f - 1), ins: base * (insF - 1), gear: base * (gearF - 1) } };
-}
-
-export function verdictOf(diffPct: number): Verdict {
-  if (diffPct <= CHEAP_THRESHOLD_PCT) return { label: "ارزان‌تر از بازار", color: GREEN, bg: "#ecfdf3", icon: "M16 17h6v-6M22 17l-8.5-8.5-5 5L2 7" };
-  if (diffPct >= EXPENSIVE_THRESHOLD_PCT) return { label: "بالاتر از بازار", color: RED, bg: "#fdecec", icon: "M16 7h6v6M22 7l-8.5 8.5-5-5L2 17" };
-  return { label: "قیمت منصفانه", color: AMBER, bg: "#fffbeb", icon: "M20 6 9 17l-5-5" };
-}
+export const verdictStyle = (verdict: Verdict): VerdictStyle => VERDICTS[verdict];

-export const diffText = (d: number): string =>
-  d > 0.5 ? `${fa(Math.abs(d).toFixed(0))}٪ بالاتر از تخمین`
+export const diffText = (d: number | null): string =>
+  d === null ? NO_ESTIMATE_TEXT
+  : d > 0.5 ? `${fa(Math.abs(d).toFixed(0))}٪ بالاتر از تخمین`
   : d < -0.5 ? `${fa(Math.abs(d).toFixed(0))}٪ ارزان‌تر از تخمین`
   : "برابر تخمین بازار";

 export const scoreColor = (score: number): string => (score >= 70 ? GREEN : score >= 45 ? AMBER : RED);

-export const signedMillions = (d: number): string => (d >= 0 ? "+" : "−") + num(Math.abs(d));
-export const deltaColor = (d: number): string => (Math.abs(d) < 1 ? NEUTRAL_COLOR : d > 0 ? GREEN : RED);
+export const signedToman = (d: number): string => (d >= 0 ? "+" : "−") + formatToman(Math.abs(d));
+export const deltaColor = (d: number): string => (Math.abs(d) < 1 ? NEUTRAL : d > 0 ? GREEN : RED);
+
+export const basisText = (basis: EstimateBasis, sampleSize: number): string =>
+  basis === "none" ? BASIS_NAMES.none : `میانهٔ ${fa(sampleSize)} آگهی ${BASIS_NAMES[basis]}`;

-export function breakdownRows(l: Listing): BreakdownRow[] {
-  const p = l.pm;
-  const rows: BreakdownRow[] = [
-    { label: "قیمت پایهٔ مدل و سال", note: `میانهٔ آگهی‌های ${l.modelName} مدل ${fa(l.year)}`, val: `${num(p.base)} میلیون`, color: INK },
-    { label: "کارکرد", note: `${num(l.km)} کیلومتر در برابر انتظار ${num(p.expKm)}`, val: signedMillions(p.parts.km), color: deltaColor(p.parts.km) },
-    { label: "وضعیت بدنه", note: l.body.name, val: signedMillions(p.parts.body), color: deltaColor(p.parts.body) },
-    { label: "بیمهٔ شخص ثالث", note: `${fa(l.ins)} ماه باقی‌مانده`, val: signedMillions(p.parts.ins), color: deltaColor(p.parts.ins) },
+/** Base, km and insurance rows from the API breakdown — nothing is computed client-side. */
+export function breakdownRows(detail: ListingDetail): BreakdownRow[] {
+  const p = detail.price_breakdown;
+  if (p.base === null || p.km_adjustment === null || p.insurance_adjustment === null) return [];
+  return [
+    { label: "قیمت پایهٔ تیپ و سال", note: basisText(p.est_basis, p.est_sample_size), val: formatToman(p.base), color: INK },
+    { label: "کارکرد", note: detail.km === null ? "کارکرد نامشخص" : `${num(detail.km)} کیلومتر`, val: signedToman(p.km_adjustment), color: deltaColor(p.km_adjustment) },
+    { label: "بیمهٔ شخص ثالث", note: detail.insurance_months === null ? "نامشخص" : `${fa(detail.insurance_months)} ماه باقی‌مانده`, val: signedToman(p.insurance_adjustment), color: deltaColor(p.insurance_adjustment) },
   ];
-  if (p.gearF !== 1) rows.push({ label: "گیربکس اتوماتیک", note: "نسبت به نسخهٔ دنده‌ای", val: signedMillions(p.parts.gear), color: GREEN });
-  if (l.extra) rows.push({ label: "تعویض موتور", note: "استخراج‌شده از متن آگهی", val: signedMillions(p.base * l.extra), color: RED });
-  return rows;
 }

-export function summaryOf(l: Listing): string {
-  const v = verdictOf(l.diffPct);
-  const neg = l.tags.filter(isNegativeIssue);
-  const pos = l.tags.filter((t) => !isNegativeIssue(t));
-  const kmWord = l.pm.kmF > 1.02 ? "کم‌کارکرد" : l.pm.kmF < 0.97 ? "پرکارکرد" : "با کارکرد معمول";
-  const priceWord = v.label === "قیمت منصفانه" ? "در محدودهٔ بازار" : v.label.replace("بازار", "تخمین بازار");
-  const advice = l.diffPct <= CHEAP_THRESHOLD_PCT ? "ارزش بازدید سریع دارد، ولی دلیل قیمت پایین را حضوری بپرس."
-    : l.diffPct >= EXPENSIVE_THRESHOLD_PCT ? "جای مذاکره دارد." : "اگر بازدید رضایت‌بخش بود قیمت منطقی است.";
-  return `${l.modelName} مدل ${fa(l.year)}، ${kmWord} نسبت به سنش. بدنه «${l.body.name}»${neg.length ? ` و فروشنده به ${neg.join(" و ")} اشاره کرده` : ""}. ${pos.length ? `نکات مثبت: ${pos.join("، ")}. ` : ""}قیمت ${priceWord} است؛ ${advice}`;
+const kmWord = (detail: ListingDetail): string => {
+  const p = detail.price_breakdown;
+  if (p.base === null || p.km_adjustment === null) return "";
+  const factor = 1 + p.km_adjustment / p.base;
+  return factor > HIGH_KM_FACTOR ? "کم‌کارکرد نسبت به سنش" : factor < LOW_KM_FACTOR ? "پرکارکرد نسبت به سنش" : "با کارکرد معمول";
+};
+
+/** One-paragraph summary from real fields only: title, km, body, verdict and advice. */
+export function summaryOf(detail: ListingDetail): string {
+  const parts = [detail.trim ?? detail.title, detail.year ? `مدل ${fa(detail.year)}` : "", kmWord(detail)].filter(Boolean).join("، ");
+  const body = detail.body_condition ? ` بدنه «${BODY_NAMES[detail.body_condition]}».` : "";
+  const price =
+    detail.verdict === "cheap" ? " قیمت ارزان‌تر از تخمین بازار است؛ ارزش بازدید سریع دارد، ولی دلیل قیمت پایین را حضوری بپرس."
+    : detail.verdict === "expensive" ? " قیمت بالاتر از تخمین بازار است؛ جای مذاکره دارد."
+    : detail.verdict === "fair" ? " قیمت در محدودهٔ بازار است؛ اگر بازدید رضایت‌بخش بود منطقی است."
+    : " برای این آگهی تخمین قیمت نداریم؛ با آگهی‌های مشابه مقایسه کن.";
+  return `${parts}.${body}${price}`;
 }

-export function verdictNote(l: Listing): string {
-  if (l.diffPct <= CHEAP_THRESHOLD_PCT) return `این آگهی حدود ${num(l.est - l.price)} میلیون زیر تخمین ماست. قبل از پرداخت، دلیل قیمت پایین (سند، رنگ، تصادف) رو حضوری چک کن.`;
-  if (l.diffPct >= EXPENSIVE_THRESHOLD_PCT) return `حدود ${num(l.price - l.est)} میلیون بالاتر از تخمین. با اشاره به آگهی‌های مشابه، جای مذاکره داری.`;
+export function verdictNote(detail: ListingDetail): string {
+  if (detail.est_price === null || detail.price === null) return "برای این آگهی آگهی‌های مشابه کافی برای تخمین نداریم.";
+  if (detail.verdict === "cheap") return `این آگهی حدود ${formatToman(detail.est_price - detail.price)} زیر تخمین ماست. قبل از پرداخت، دلیل قیمت پایین (سند، رنگ، تصادف) رو حضوری چک کن.`;
+  if (detail.verdict === "expensive") return `حدود ${formatToman(detail.price - detail.est_price)} بالاتر از تخمین. با اشاره به آگهی‌های مشابه، جای مذاکره داری.`;
   return "قیمت در بازهٔ منطقی آگهی‌های مشابه است.";
 }
+
+/** Rows for the /estimates result: the same three rows, from the API breakdown. */
+export function estimateBreakdownRows(result: EstimateResponse, request: EstimateRequest | null): BreakdownRow[] {
+  const b = result.breakdown;
+  return [
+    { label: "قیمت پایهٔ تیپ و سال", note: basisText(result.est_basis, result.est_sample_size), val: formatToman(b.base), color: INK },
+    { label: "کارکرد", note: request?.km == null ? "کارکرد نامشخص" : `${num(request.km)} کیلومتر`, val: signedToman(b.km_adjustment), color: deltaColor(b.km_adjustment) },
+    { label: "بیمهٔ شخص ثالث", note: request?.insurance_months == null ? "نامشخص" : `${fa(request.insurance_months)} ماه`, val: signedToman(b.insurance_adjustment), color: deltaColor(b.insurance_adjustment) },
+  ];
+}
````

Modify `frontend/src/lib/search.ts` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/lib/search.ts b/frontend/src/lib/search.ts
index d67ba8f..808687b 100644
--- a/frontend/src/lib/search.ts
+++ b/frontend/src/lib/search.ts
@@ -1,96 +1,51 @@
-import { CITIES, MODELS, findModel } from "./catalog";
-import { en, fa, num } from "./format";
-import { CHEAP_THRESHOLD_PCT } from "./pricing";
-import type { Filters, Listing, ParsedQuery, SortKey } from "./types";
-
-export const DEFAULT_MAX_PRICE = 1400;
-export const DEFAULT_MAX_KM = 250;
-const LOW_MILEAGE_KM = 90;
-const BILLION_TO_MILLION = 1000;
-const IMPLICIT_BILLION_BELOW = 5; // "زیر ۱.۲" means billions
-const THOUSAND_WORD = "هزار";
-const MILEAGE_UNIT_WORD = "کیلومتر";
-const MILEAGE_CONTEXT_WORD = "کارکرد";
-const BILLION_WORD = "میلیارد";
-const MILLION_WORD = "میلیون";
-
-export const DEFAULT_FILTERS: Filters = { models: [], cities: [], maxPrice: DEFAULT_MAX_PRICE, maxKm: DEFAULT_MAX_KM, gear: "همه", onlyBelow: false, year: null };
-
-const normalize = (q: string): string => en(q).toLowerCase().replace(/ي/g, "ی").replace(/ك/g, "ک");
-
-// A quantity clause ("زیر ۵۰ هزار کیلومتر") is a mileage clause, not a price clause, when its
-// unit is explicitly km/mileage-context, or when "هزار" appears with no price unit stated at all.
-const isMileageClause = (thousand: string | undefined, unit: string | undefined): boolean =>
-  unit === MILEAGE_UNIT_WORD || unit === MILEAGE_CONTEXT_WORD || (Boolean(thousand) && !unit);
-
-function parseMaxPrice(text: string): number | null {
-  const candidates = text.matchAll(
-    new RegExp(`(?:زیر|کمتر از|تا|حداکثر)\\s*(\\d+(?:\\.\\d+)?)\\s*(${THOUSAND_WORD})?\\s*(${BILLION_WORD}|${MILLION_WORD}|${MILEAGE_UNIT_WORD}|${MILEAGE_CONTEXT_WORD})?`, "g"),
-  );
-  for (const [, rawValue, thousand, unit] of candidates) {
-    if (isMileageClause(thousand, unit)) continue;
-    const value = parseFloat(rawValue);
-    const inBillions = unit === BILLION_WORD || (!unit && value < IMPLICIT_BILLION_BELOW);
-    return Math.round(value * (inBillions ? BILLION_TO_MILLION : 1));
-  }
-  return /یک میلیارد/.test(text) ? BILLION_TO_MILLION : null;
-}
-
-function parseMaxKm(text: string): number | null {
-  const explicit = text.match(/(?:کارکرد\s*)?(?:زیر|کمتر از)\s*(\d+)\s*(?:هزار)?\s*(?:کیلومتر|تا کارکرد|کارکرد)/);
-  if (explicit) return parseInt(explicit[1], 10);
-  return /کم[\s‌]?کارکرد|کم کار/.test(text) ? LOW_MILEAGE_KM : null;
-}
-
-export function parseQuery(q: string): ParsedQuery {
-  const text = normalize(q);
-  const year = text.match(/(?:مدل|سال)\s*(1[34]\d\d)/);
-  return {
-    models: MODELS.filter((m) => [m.name, ...m.aliases].some((a) => text.includes(normalize(a)))).map((m) => m.id),
-    city: CITIES.find((c) => text.includes(c.name))?.name ?? null,
-    maxPrice: parseMaxPrice(text),
-    maxKm: parseMaxKm(text),
-    gear: /اتومات/.test(text) ? "اتوماتیک" : /دنده/.test(text) ? "دنده‌ای" : null,
-    year: year ? parseInt(year[1], 10) : null,
-    onlyBelow: /ارزان|زیر قیمت|به‌?صرفه|به صرفه/.test(text),
-  };
+// Filter-sheet state only. The URL is the single source of truth: every filter change
+// becomes new query params and a new /search request.
+import type { Category, Gearbox, SearchParams, SortKey } from "./api/types";
+import { buildQuery } from "./api/client";
+
+export const CATEGORIES: Category[] = ["light", "heavy", "motorcycle", "rental", "classic"];
+export const GEARBOXES: Gearbox[] = ["manual", "automatic"];
+export const SORTS: SortKey[] = ["relevance", "deal", "price", "km", "newest"];
+export const DEFAULT_PAGE_SIZE = 20;
+
+const isCategory = (v: string | null): v is Category => v !== null && (CATEGORIES as string[]).includes(v);
+const isGearbox = (v: string | null): v is Gearbox => v !== null && (GEARBOXES as string[]).includes(v);
+const isSort = (v: string | null): v is SortKey => v !== null && (SORTS as string[]).includes(v);
+const positive = (v: string | null): number | undefined => (v && /^\d+$/.test(v) && Number(v) > 0 ? Number(v) : undefined);
+
+/** Everything the filter sheet can set, i.e. SearchParams without paging. */
+export type SearchOverrides = Omit<SearchParams, "page" | "page_size">;
+
+export const activeFilterCount = (o: SearchOverrides): number =>
+  (o.category ? 1 : 0) + (o.models?.length ?? 0) + (o.cities?.length ?? 0) + (o.year ? 1 : 0) + (o.price_max ? 1 : 0) +
+  (o.km_max ? 1 : 0) + (o.gearbox ? 1 : 0) + (o.only_below ? 1 : 0);
+
+/** SearchParams → the query string of /results (and of GET /search), without paging. */
+export const paramsToQuery = (params: SearchParams): string =>
+  buildQuery({
+    q: params.q, category: params.category, models: params.models, cities: params.cities, year: params.year,
+    price_max: params.price_max, km_max: params.km_max, gearbox: params.gearbox, only_below: params.only_below || undefined,
+    sort: params.sort === "relevance" ? undefined : params.sort,
+  });
+
+/** URL search params → SearchParams. Unknown or malformed values are dropped, never guessed. */
+export function queryToParams(query: URLSearchParams): SearchParams {
+  const q = query.get("q")?.trim();
+  const category = query.get("category");
+  const gearbox = query.get("gearbox");
+  const sort = query.get("sort");
+  const models = query.getAll("models").filter(Boolean);
+  const cities = query.getAll("cities").filter(Boolean);
+  const params: SearchParams = {};
+  if (q) params.q = q;
+  if (isCategory(category)) params.category = category;
+  if (models.length) params.models = models;
+  if (cities.length) params.cities = cities;
+  if (positive(query.get("year"))) params.year = positive(query.get("year"));
+  if (positive(query.get("price_max"))) params.price_max = positive(query.get("price_max"));
+  if (positive(query.get("km_max"))) params.km_max = positive(query.get("km_max"));
+  if (isGearbox(gearbox)) params.gearbox = gearbox;
+  if (query.get("only_below") === "true") params.only_below = true;
+  if (isSort(sort)) params.sort = sort;
+  return params;
 }
-
-export const hasCriteria = (p: ParsedQuery): boolean => p.models.length > 0 || p.maxPrice !== null || p.city !== null || p.maxKm !== null;
-
-export function chipsOf(p: ParsedQuery): string[] {
-  const chips = p.models.map((id) => findModel(id)!.name);
-  if (p.year) chips.push(`مدل ${fa(p.year)}`);
-  if (p.maxPrice) chips.push(`زیر ${num(p.maxPrice)} میلیون`);
-  if (p.maxKm) chips.push(`کارکرد زیر ${fa(p.maxKm)} هزار`);
-  if (p.city) chips.push(p.city);
-  if (p.gear) chips.push(p.gear);
-  if (p.onlyBelow) chips.push("فقط ارزان‌تر از بازار");
-  return chips;
-}
-
-export const filtersFromQuery = (p: ParsedQuery): Filters => ({
-  models: p.models, cities: p.city ? [p.city] : [], maxPrice: p.maxPrice ?? DEFAULT_MAX_PRICE, maxKm: p.maxKm ?? DEFAULT_MAX_KM,
-  gear: p.gear ?? "همه", onlyBelow: p.onlyBelow, year: p.year,
-});
-
-export const matchesParsed = (l: Listing, p: ParsedQuery): boolean =>
-  (!p.models.length || p.models.includes(l.modelId)) && (!p.city || l.city === p.city) && (!p.maxPrice || l.price <= p.maxPrice) &&
-  (!p.maxKm || l.km <= p.maxKm * 1000) && (!p.gear || l.gear === p.gear) && (!p.year || l.year === p.year);
-
-export const filterListings = (list: Listing[], f: Filters): Listing[] =>
-  list.filter((l) =>
-    (!f.models.length || f.models.includes(l.modelId)) && (!f.cities.length || f.cities.includes(l.city)) &&
-    l.price <= f.maxPrice && l.km <= f.maxKm * 1000 && (f.gear === "همه" || l.gear === f.gear) &&
-    (!f.onlyBelow || l.diffPct <= CHEAP_THRESHOLD_PCT) && (!f.year || l.year === f.year));
-
-const COMPARATORS: Record<SortKey, (a: Listing, b: Listing) => number> = {
-  price: (a, b) => a.price - b.price, km: (a, b) => a.km - b.km, new: (a, b) => a.postedIdx - b.postedIdx, score: (a, b) => b.score - a.score,
-};
-export const sortListings = (list: Listing[], sort: SortKey): Listing[] => [...list].sort(COMPARATORS[sort]);
-
-export const alertMatches = (listings: Listing[], threshold: number): number =>
-  listings.filter((l) => l.price <= threshold).length;
-
-export const activeFilterCount = (f: Filters): number =>
-  f.models.length + f.cities.length + Number(f.maxPrice < DEFAULT_MAX_PRICE) + Number(f.maxKm < DEFAULT_MAX_KM) + Number(f.gear !== "همه") + Number(f.onlyBelow);
````

Create `frontend/src/lib/specs.ts`:

````ts
import type { ListingDetail } from "./api/types";
import { fa, num } from "./format";
import { BODY_NAMES, CATEGORY_NAMES, FUEL_NAMES, GEARBOX_NAMES } from "./labels";

export interface SpecRow { k: string; v: string; }

// Divar attribute keys worth a row on the specs grid (see backend/ingest/column_maps.py).
const ATTRIBUTE_ROWS: [key: string, label: string][] = [
  ["حجم موتور", "حجم موتور"],
  ["مالکیت خودرو", "مالکیت"],
  ["مایل به معاوضه", "معاوضه"],
  ["معاینه فنی", "معاینه فنی"],
  ["وضعیت سند و مدارک", "سند و مدارک"],
  ["وضعیت فنی موتور", "وضعیت فنی موتور"],
  ["وضعیت فنی موتور و گیربکس", "موتور و گیربکس"],
  ["نوع استارت", "نوع استارت"],
  ["نوع کلاچ", "نوع کلاچ"],
  ["وضعیت لاستیک‌ها", "لاستیک‌ها"],
];

const row = (k: string, v: string | null | undefined): SpecRow | null => (v ? { k, v } : null);

/** Per-category spec rows from typed fields plus Divar attributes; empty rows are dropped. */
export function specsOf(l: ListingDetail): SpecRow[] {
  const typed = [
    row("دسته", CATEGORY_NAMES[l.category]),
    row("برند و مدل", l.trim),
    row("سال ساخت", l.year === null ? null : fa(l.year)),
    row("کارکرد", l.km === null ? null : `${num(l.km)} کیلومتر`),
    row("رنگ", l.color),
    row("گیربکس", l.gearbox ? GEARBOX_NAMES[l.gearbox] : null),
    row("نوع سوخت", l.fuel ? FUEL_NAMES[l.fuel] : null),
    row("وضعیت بدنه", l.body_condition ? BODY_NAMES[l.body_condition] : null),
    row("مهلت بیمهٔ شخص ثالث", l.insurance_months === null ? null : `${fa(l.insurance_months)} ماه`),
    row("فروشنده", l.is_dealer ? "نمایشگاه" : "شخصی"),
    row("محل", l.district ? `${l.city}، ${l.district}` : l.city),
  ];
  const attributes = ATTRIBUTE_ROWS.map(([key, label]) => row(label, l.attributes[key]));
  return [...typed, ...attributes].filter((spec): spec is SpecRow => spec !== null);
}
````

Modify `frontend/src/lib/types.ts` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/lib/types.ts b/frontend/src/lib/types.ts
index ebb6b99..a90fdc5 100644
--- a/frontend/src/lib/types.ts
+++ b/frontend/src/lib/types.ts
@@ -1,30 +1,8 @@
-export type Gear = "دنده‌ای" | "اتوماتیک";
-export type GearFilter = Gear | "همه";
-export type SortKey = "score" | "price" | "km" | "new";
+import type { ListingCard, SearchParams } from "./api/types";

-export interface CarModel { id: string; name: string; aliases: string[]; base: Record<number, number>; gears: Gear[]; }
-export interface BodyCondition { name: string; f: number; }
-export interface City { name: string; lat: number; lng: number; districts: string[]; }
-export interface Issue { name: string; neg: boolean; }
-
-export interface PriceParts { km: number; body: number; ins: number; gear: number; }
-export interface PriceModelResult { base: number; expKm: number; kmF: number; insF: number; gearF: number; est: number; parts: PriceParts; }
-
-export interface SellerAssessment { engine: string; chassis: string; bodyA: string; gearbox: string; }
-
-export interface Listing {
-  id: string; modelId: string; modelName: string; year: number; km: number; body: BodyCondition;
-  city: string; district: string; gear: Gear; ins: number; color: string;
-  price: number; est: number; diffPct: number; score: number; tags: string[]; desc: string;
-  pm: PriceModelResult; extra: number; img: string; posted: string; postedIdx: number;
-  photos: string[]; assess: SellerAssessment; lat: number; lng: number; token: string;
-}
-
-export interface Verdict { label: string; color: string; bg: string; icon: string; }
+/** How a verdict is drawn (label, colours, badge icon path). */
+export interface VerdictStyle { label: string; color: string; bg: string; icon: string; }
 export interface BreakdownRow { label: string; note: string; val: string; color: string; }

-export interface ParsedQuery { models: string[]; city: string | null; maxPrice: number | null; maxKm: number | null; gear: Gear | null; year: number | null; onlyBelow: boolean; }
-export interface Filters { models: string[]; cities: string[]; maxPrice: number; maxKm: number; gear: GearFilter; onlyBelow: boolean; year: number | null; }
-
-export interface ChatMessage { role: "user" | "assistant"; text: string; cardIds?: string[]; }
-export interface PriceAlert { title: string; threshold: number; matches: number; }
+export interface ChatMessage { role: "user" | "assistant"; text: string; listings: ListingCard[]; }
+export interface PriceAlert { title: string; params: SearchParams; threshold: number; }
````

Modify `frontend/src/lib/view.ts` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/lib/view.ts b/frontend/src/lib/view.ts
index eab783c..5d4254a 100644
--- a/frontend/src/lib/view.ts
+++ b/frontend/src/lib/view.ts
@@ -1,11 +1,32 @@
-import { fa, num } from "./format";
-import { diffText, scoreColor, verdictOf } from "./pricing";
-import type { Listing, Verdict } from "./types";
+import type { ListingCard } from "./api/types";
+import { fa, formatToman, num, relativeTime } from "./format";
+import { BODY_NAMES, GEARBOX_NAMES } from "./labels";
+import { diffText, scoreColor, verdictStyle } from "./pricing";
+import type { VerdictStyle } from "./types";

-export interface CardView { id: string; href: string; img: string; title: string; posted: string; meta: string; priceFa: string; verdict: Verdict; diffText: string; score: number; scoreFa: string; scoreColor: string; body: string; insFa: string; }
+export interface CardView {
+  id: string; href: string; img: string; title: string; posted: string; meta: string; priceText: string;
+  verdict: VerdictStyle; diffText: string; score: number; scoreFa: string; scoreColor: string; body: string; insFa: string;
+  isExact: boolean; nearMissLabels: string[];
+}

-export const cardOf = (l: Listing): CardView => ({
-  id: l.id, href: `/listing/${l.id}`, img: l.img, title: `${l.modelName} مدل ${fa(l.year)}`, posted: l.posted,
-  meta: `${num(l.km)} کیلومتر · ${l.city}، ${l.district} · ${l.gear}`, priceFa: num(l.price), verdict: verdictOf(l.diffPct),
-  diffText: diffText(l.diffPct), score: l.score, scoreFa: fa(l.score), scoreColor: scoreColor(l.score), body: l.body.name, insFa: fa(l.ins),
+export const PRICE_UNKNOWN = "توافقی";
+const PLACEHOLDER_IMAGE = "/icons/icon-192.png";
+
+export const metaOf = (l: ListingCard): string =>
+  [
+    l.year === null ? "" : `مدل ${fa(l.year)}`,
+    l.km === null ? "" : `${num(l.km)} کیلومتر`,
+    l.district ? `${l.city}، ${l.district}` : l.city,
+    l.gearbox ? GEARBOX_NAMES[l.gearbox] : "",
+  ].filter(Boolean).join(" · ");
+
+/** `dataAsOf` is the snapshot time from /facets; without it, "posted" is relative to now. */
+export const cardOf = (l: ListingCard, dataAsOf: string | null = null): CardView => ({
+  id: l.id, href: `/listing/${l.id}`, img: l.thumbnail_url ?? PLACEHOLDER_IMAGE, title: l.trim ?? l.title,
+  posted: relativeTime(l.posted_at, dataAsOf ?? new Date()), meta: metaOf(l),
+  priceText: l.price === null ? PRICE_UNKNOWN : formatToman(l.price), verdict: verdictStyle(l.verdict), diffText: diffText(l.diff_pct),
+  score: l.deal_score ?? 0, scoreFa: l.deal_score === null ? "—" : fa(l.deal_score), scoreColor: scoreColor(l.deal_score ?? 0),
+  body: l.body_condition ? BODY_NAMES[l.body_condition] : "—", insFa: l.insurance_months === null ? "—" : fa(l.insurance_months),
+  isExact: l.is_exact, nearMissLabels: l.near_miss_labels,
 });
````

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bun test`
Expected: `27 pass, 0 fail` (6 client + 5 format + 3 view + 6 pricing + 2 compare + 2 specs + 3 search). `bunx tsc --noEmit` is expected to fail outside `src/lib` (see above).

- [ ] **Step 5: Commit**

From the repo root (`cd ..`), stage explicit paths only (never `git add -A`):

````bash
git add frontend/src/lib/assistant.test.ts frontend/src/lib/assistant.ts frontend/src/lib/catalog.ts frontend/src/lib/compare.test.ts frontend/src/lib/compare.ts frontend/src/lib/estimate.ts frontend/src/lib/format.test.ts frontend/src/lib/format.ts frontend/src/lib/labels.ts frontend/src/lib/listings.test.ts frontend/src/lib/listings.ts frontend/src/lib/modelStats.ts frontend/src/lib/pricing.test.ts frontend/src/lib/pricing.ts frontend/src/lib/screens.test.ts frontend/src/lib/search.test.ts frontend/src/lib/search.ts frontend/src/lib/specs.test.ts frontend/src/lib/specs.ts frontend/src/lib/types.ts frontend/src/lib/view.test.ts frontend/src/lib/view.ts
git commit -m "refactor(frontend): rewrite lib modules against the API types and drop synthetic data

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git log -1 --format='%(trailers)'   # must print exactly: Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
````

---

### Task 8: AppState v2, chat panel, alerts dropdown and shared cards

**Files:**
- Modify: `frontend/src/components/AlertsDropdown.tsx`
- Modify: `frontend/src/components/BreakdownCard.tsx`
- Modify: `frontend/src/components/ChatPanel.tsx`
- Create: `frontend/src/components/ErrorBanner.module.css`
- Create: `frontend/src/components/ErrorBanner.tsx`
- Modify: `frontend/src/components/Footer.tsx`
- Modify: `frontend/src/components/ListingCard.module.css`
- Modify: `frontend/src/components/ListingCard.tsx`
- Modify: `frontend/src/components/ListingRow.tsx`
- Modify: `frontend/src/components/MiniListing.tsx`
- Create: `frontend/src/components/Skeleton.module.css`
- Create: `frontend/src/components/Skeleton.tsx`
- Modify: `frontend/src/components/VerdictBadge.tsx`
- Modify: `frontend/src/state/AppState.tsx`

**Interfaces:**
- Consumes: `apiPost`, `apiGet`, `useApi`, `cardOf`, `CardView`, `VerdictStyle`, `ChatMessage`, `PriceAlert`, `formatToman`.
- Produces: `AppStateProvider`/`useAppState()` (localStorage key `torobcar:v2`; `sendChat` posts `{ messages: last 10, compare_ids }` to `/assistant` and appends `{ role, text, listings }`, rendering a 422 message or «الان به سرویس جست‌وجو دسترسی ندارم…» as an assistant bubble on failure); `ChatPanel` (renders `m.listings` as `MiniListing`s); `AlertsDropdown` (live count per alert via `/search?…&price_max=threshold&page_size=1` → `total`, fetched when the dropdown mounts); card components reading `card.priceText`; `ListingCard` shows `nearMissLabels`; `VerdictBadge`/`BreakdownCard` take `VerdictStyle` (`BreakdownCard` props `estText`/`priceText`); `ErrorBanner({ error, onRetry })` + `errorText(error)` + `SERVICE_UNAVAILABLE`; `Skeleton({ lines, width })`, `CardSkeletons({ count })`.

Spec §4.4, §5 (chat panel, alerts dropdown), §6.1–§6.2. The old `torobcar:v1` key (synthetic ids) is ignored; persisted alerts are validated on read. `ErrorBanner` shows the backend's own message for 422 and «سرویس جست‌وجو در دسترس نیست» with a retry button otherwise. **`tsc` still red in:** `src/app/compare/page.tsx`, `src/app/estimate/page.tsx`, `src/app/listing/[id]/page.tsx`, `src/app/model/[id]/page.tsx`, `src/app/page.tsx`, `src/components/{CompareTable,EstimateForm,EstimateResultCard,FiltersPanel,IssueBars,ListingScreen,ListingsMap,MapCard,ModelCard,ModelScreen,PriceCard,PriceHistogram,ResultsScreen,ResultsToolbar,SellerAssessmentCard,SummaryCard}.tsx` — exactly these 21 files, nothing else.

- [ ] **Step 1: Implement**

Modify `frontend/src/components/AlertsDropdown.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/AlertsDropdown.tsx b/frontend/src/components/AlertsDropdown.tsx
index 8ac113f..af64cd8 100644
--- a/frontend/src/components/AlertsDropdown.tsx
+++ b/frontend/src/components/AlertsDropdown.tsx
@@ -1,11 +1,27 @@
 "use client";
-import { fa, num } from "@/lib/format";
+import { apiGet } from "@/lib/api/client";
+import type { SearchResponse } from "@/lib/api/types";
+import { useApi } from "@/lib/api/useApi";
+import { fa, formatToman } from "@/lib/format";
+import type { PriceAlert } from "@/lib/types";
 import { useAppState } from "@/state/AppState";
 import { Icon } from "./Icon";
 import styles from "./AlertsDropdown.module.css";

+/** One /search per alert, capped at the threshold, page_size 1 → `total` is the live match count. */
+const countMatches = (alert: PriceAlert, signal: AbortSignal): Promise<number> =>
+  apiGet<SearchResponse>("/search", { ...alert.params, price_max: alert.threshold, page_size: 1 }, signal).then((r) => r.total);
+
+function matchText(count: number | undefined, loading: boolean, failed: boolean): string {
+  if (loading) return "در حال شمارش…";
+  if (failed || count === undefined) return "شمارش در دسترس نیست";
+  return `الان ${fa(count)} آگهی زیر این قیمت`;
+}
+
 export function AlertsDropdown() {
   const { alerts, loggedIn, removeAlert, toggleLogin } = useAppState();
+  // Fetched live every time the dropdown opens (this component mounts on open).
+  const counts = useApi(alerts.length ? JSON.stringify(alerts) : null, (signal) => Promise.all(alerts.map((a) => countMatches(a, signal))));

   return (
     <div className={styles.panel}>
@@ -30,7 +46,7 @@ export function AlertsDropdown() {
           </div>
           <div className={styles.text}>
             <div className={styles.title}>{a.title}</div>
-            <div className={styles.meta}>{`قیمت کمتر از ${num(a.threshold)} میلیون · الان ${fa(a.matches)} آگهی زیر این قیمت`}</div>
+            <div className={styles.meta}>{`قیمت کمتر از ${formatToman(a.threshold)} · ${matchText(counts.data?.[i], counts.loading, counts.error !== null)}`}</div>
           </div>
           <button className={styles.remove} onClick={() => removeAlert(i)} title="حذف">×</button>
         </div>
````

Modify `frontend/src/components/BreakdownCard.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/BreakdownCard.tsx b/frontend/src/components/BreakdownCard.tsx
index 2689ddc..145a26f 100644
--- a/frontend/src/components/BreakdownCard.tsx
+++ b/frontend/src/components/BreakdownCard.tsx
@@ -1,11 +1,11 @@
-import type { BreakdownRow, Verdict } from "@/lib/types";
+import type { BreakdownRow, VerdictStyle } from "@/lib/types";
 import { BreakdownRows } from "./BreakdownList";
 import { VerdictBadge } from "./VerdictBadge";
 import styles from "./BreakdownCard.module.css";

-interface Props { verdict: Verdict; diffText: string; rows: BreakdownRow[]; estFa: string; priceFa: string; note: string; }
+interface Props { verdict: VerdictStyle; diffText: string; rows: BreakdownRow[]; estText: string; priceText: string; note: string; }

-export function BreakdownCard({ verdict, diffText, rows, estFa, priceFa, note }: Props) {
+export function BreakdownCard({ verdict, diffText, rows, estText, priceText, note }: Props) {
   return (
     <div className={styles.card}>
       <div className={styles.head} style={{ background: verdict.bg }}>
@@ -18,11 +18,11 @@ export function BreakdownCard({ verdict, diffText, rows, estFa, priceFa, note }:
         <BreakdownRows rows={rows} />
         <div className={styles.total}>
           <span>تخمین قیمت بازار</span>
-          <span>{estFa} میلیون</span>
+          <span>{estText}</span>
         </div>
         <div className={styles.totalLast}>
           <span>قیمت آگهی</span>
-          <span>{priceFa} میلیون</span>
+          <span>{priceText}</span>
         </div>
         <div className={styles.summary}>{note}</div>
       </div>
````

Modify `frontend/src/components/ChatPanel.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/ChatPanel.tsx b/frontend/src/components/ChatPanel.tsx
index 72f73de..163e40d 100644
--- a/frontend/src/components/ChatPanel.tsx
+++ b/frontend/src/components/ChatPanel.tsx
@@ -1,6 +1,5 @@
 "use client";
 import { useEffect, useRef, useState } from "react";
-import { findListing } from "@/lib/listings";
 import { cardOf } from "@/lib/view";
 import { useAppState } from "@/state/AppState";
 import { Avatar } from "./Avatar";
@@ -8,9 +7,9 @@ import { Icon } from "./Icon";
 import { MiniListing } from "./MiniListing";
 import styles from "./ChatPanel.module.css";

-const OPENING = ["دنا پلاس زیر ۹۰۰ میلیون", "کم‌کارکردترین ۲۰۶ تهران", "تارا اتومات به‌صرفه"];
+const OPENING = ["پژو ۲۰۶ تیپ ۲ تهران", "پراید زیر ۳۰۰ میلیون", "دنا پلاس اتومات"];
 const COMPARING = ["بین این‌ها کدوم به‌صرفه‌تره؟"];
-const FOLLOW_UP = ["ارزان‌ترین جک J4", "فقط ارزان‌تر از بازار نشون بده"];
+const FOLLOW_UP = ["ارزان‌ترین سمند مشهد", "فقط ارزان‌تر از بازار نشون بده"];

 export function ChatPanel() {
   const { chatOpen, setChatOpen, chatMessages, chatBusy, avatarAnimation, compare, sendChat } = useAppState();
@@ -33,9 +32,9 @@ export function ChatPanel() {
         {chatMessages.map((m, i) => (
           <div key={i} className={m.role === "user" ? styles.fromUser : styles.fromAssistant}>
             <div className={styles.bubble}>{m.text}</div>
-            {m.cardIds && (
+            {m.listings.length > 0 && (
               <div className={styles.cards}>
-                {m.cardIds.map((id) => { const l = findListing(id); return l ? <MiniListing key={id} card={cardOf(l)} bordered /> : null; })}
+                {m.listings.map((l) => <MiniListing key={l.id} card={cardOf(l)} bordered />)}
               </div>
             )}
           </div>
@@ -46,8 +45,8 @@ export function ChatPanel() {
         {suggestions.map((s) => <button key={s} className={styles.chip} onClick={() => sendChat(s)}>{s}</button>)}
       </div>
       <form className={styles.form} onSubmit={submit}>
-        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="مثلاً: بین این‌ها کدوم به‌صرفه‌تره؟" className={styles.input} aria-label="پیام" />
-        <button type="submit" className={styles.send} aria-label="ارسال"><Icon name="send" stroke="#fff" /></button>
+        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="مثلاً: بین این‌ها کدوم به‌صرفه‌تره؟" className={styles.input} aria-label="پیام" maxLength={500} />
+        <button type="submit" className={styles.send} aria-label="ارسال" disabled={chatBusy}><Icon name="send" stroke="#fff" /></button>
       </form>
     </aside>
   );
````

Create `frontend/src/components/ErrorBanner.module.css`:

````css
.banner { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px; border: 1px solid #f5c2c7; background: var(--red-soft); color: var(--red-ink); border-radius: 12px; font-size: 13px; }
.retry { border: 1px solid var(--red); background: var(--surface); color: var(--red-ink); border-radius: 8px; padding: 6px 12px; font: inherit; font-size: 12px; font-weight: 600; cursor: pointer; }
````

Create `frontend/src/components/ErrorBanner.tsx`:

````tsx
import type { ApiError } from "@/lib/api/client";
import styles from "./ErrorBanner.module.css";

export const SERVICE_UNAVAILABLE = "سرویس جست‌وجو در دسترس نیست";

/** 422 → the backend's own message (a user problem); anything else → service unavailable. */
export const errorText = (error: ApiError): string => (error.status === 422 ? error.message : SERVICE_UNAVAILABLE);

export function ErrorBanner({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div className={styles.banner} role="alert">
      <span>{errorText(error)}</span>
      {onRetry && error.status !== 422 && <button type="button" className={styles.retry} onClick={onRetry}>تلاش دوباره</button>}
    </div>
  );
}
````

Modify `frontend/src/components/Footer.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/Footer.tsx b/frontend/src/components/Footer.tsx
index 1e715e3..f0b6a69 100644
--- a/frontend/src/components/Footer.tsx
+++ b/frontend/src/components/Footer.tsx
@@ -1,5 +1,5 @@
 import styles from "./Footer.module.css";

 export function Footer() {
-  return <footer className={styles.footer}>ترب‌کار · نمونهٔ اولیه · داده‌ها نمایشی و بر پایهٔ ساختار آگهی‌های دیوار</footer>;
+  return <footer className={styles.footer}>ترب‌کار · نمونهٔ اولیه · داده‌ها از آگهی‌های عمومی دیوار</footer>;
 }
````

Modify `frontend/src/components/ListingCard.module.css` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/ListingCard.module.css b/frontend/src/components/ListingCard.module.css
index 49acb37..e90b0ee 100644
--- a/frontend/src/components/ListingCard.module.css
+++ b/frontend/src/components/ListingCard.module.css
@@ -12,3 +12,5 @@
 .price { font-size: 17px; font-weight: 800; }
 .unit { font-size: 11px; font-weight: 500; color: var(--muted); }
 .diff { font-size: 12px; font-weight: 600; }
+.labels { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
+.label { font-size: 10px; padding: 2px 6px; border-radius: 6px; background: var(--amber-soft); color: var(--amber); }
````

Modify `frontend/src/components/ListingCard.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/ListingCard.tsx b/frontend/src/components/ListingCard.tsx
index a22cc62..0c4a6c8 100644
--- a/frontend/src/components/ListingCard.tsx
+++ b/frontend/src/components/ListingCard.tsx
@@ -15,10 +15,13 @@ export function ListingCard({ card }: { card: CardView }) {
         <div className={styles.titleRow}><span className={styles.title}>{card.title}</span><span className={styles.posted}>{card.posted}</span></div>
         <div className={styles.meta}>{card.meta}</div>
         <div className={styles.priceRow}>
-          <span className={styles.price}>{card.priceFa} <span className={styles.unit}>میلیون</span></span>
+          <span className={styles.price}>{card.priceText}</span>
           <span className={styles.diff} style={{ color: card.verdict.color }}>{card.diffText}</span>
         </div>
         <ScoreBar score={card.score} scoreFa={card.scoreFa} color={card.scoreColor} />
+        {card.nearMissLabels.length > 0 && (
+          <div className={styles.labels}>{card.nearMissLabels.map((label) => <span key={label} className={styles.label}>{label}</span>)}</div>
+        )}
       </div>
     </Link>
   );
````

Modify `frontend/src/components/ListingRow.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/ListingRow.tsx b/frontend/src/components/ListingRow.tsx
index 2d0c63c..c8cec89 100644
--- a/frontend/src/components/ListingRow.tsx
+++ b/frontend/src/components/ListingRow.tsx
@@ -13,10 +13,10 @@ export function ListingRow({ card }: { card: CardView }) {
           <VerdictBadge verdict={card.verdict} size="sm" />
         </div>
         <div className={styles.meta}>{card.meta}</div>
-        <div className={styles.meta}>{card.body} · بیمه {card.insFa} ماه</div>
+        <div className={styles.meta}>بدنه {card.body} · بیمه {card.insFa} ماه</div>
       </div>
       <div className={styles.price}>
-        <div className={styles.amount}>{card.priceFa} <span className={styles.unit}>میلیون</span></div>
+        <div className={styles.amount}>{card.priceText}</div>
         <div className={styles.diff} style={{ color: card.verdict.color }}>{card.diffText}</div>
         <div className={styles.score}>ارزش خرید <b className={styles.scoreVal}>{card.scoreFa}</b>/۱۰۰</div>
       </div>
````

Modify `frontend/src/components/MiniListing.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/MiniListing.tsx b/frontend/src/components/MiniListing.tsx
index 91fb032..4e9f5df 100644
--- a/frontend/src/components/MiniListing.tsx
+++ b/frontend/src/components/MiniListing.tsx
@@ -11,7 +11,7 @@ export function MiniListing({ card, bordered = false }: { card: CardView; border
         <div className={styles.meta}>{card.meta}</div>
       </div>
       <div className={styles.price}>
-        <div className={styles.amount}>{card.priceFa}</div>
+        <div className={styles.amount}>{card.priceText}</div>
         <div className={styles.verdict} style={{ color: card.verdict.color }}>{card.verdict.label}</div>
       </div>
     </Link>
````

Create `frontend/src/components/Skeleton.module.css`:

````css
.stack { display: flex; flex-direction: column; gap: 10px; }
.block { border-radius: 10px; background: linear-gradient(90deg, var(--fill) 25%, var(--line-soft) 50%, var(--fill) 75%); background-size: 200% 100%; animation: shimmer 1.2s infinite; }
@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }
````

Create `frontend/src/components/Skeleton.tsx`:

````tsx
import styles from "./Skeleton.module.css";

/** Pulsing placeholder blocks; `lines` rows of the given heights (px). */
export function Skeleton({ lines = [24, 16, 16], width = "100%" }: { lines?: number[]; width?: string }) {
  return (
    <div className={styles.stack} style={{ width }} aria-busy="true" aria-label="در حال بارگذاری">
      {lines.map((height, i) => <div key={i} className={styles.block} style={{ height }} />)}
    </div>
  );
}

export function CardSkeletons({ count }: { count: number }) {
  return <>{Array.from({ length: count }, (_, i) => <Skeleton key={i} lines={[150, 18, 14, 14]} />)}</>;
}
````

Modify `frontend/src/components/VerdictBadge.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/VerdictBadge.tsx b/frontend/src/components/VerdictBadge.tsx
index 05e6ed0..ee747bf 100644
--- a/frontend/src/components/VerdictBadge.tsx
+++ b/frontend/src/components/VerdictBadge.tsx
@@ -1,8 +1,8 @@
 import { Icon } from "./Icon";
-import type { Verdict } from "@/lib/types";
+import type { VerdictStyle } from "@/lib/types";
 import styles from "./VerdictBadge.module.css";

-export function VerdictBadge({ verdict, size = "md" }: { verdict: Verdict; size?: "sm" | "md" | "lg" }) {
+export function VerdictBadge({ verdict, size = "md" }: { verdict: VerdictStyle; size?: "sm" | "md" | "lg" }) {
   return (
     <span className={`${styles.badge} ${styles[size]}`} style={{ background: verdict.color }}>
       <Icon d={verdict.icon} size={14} stroke="#fff" />
````

Modify `frontend/src/state/AppState.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/state/AppState.tsx b/frontend/src/state/AppState.tsx
index 41684eb..af3bf16 100644
--- a/frontend/src/state/AppState.tsx
+++ b/frontend/src/state/AppState.tsx
@@ -1,18 +1,19 @@
 "use client";

 import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
-import { scriptedReply } from "@/lib/assistant";
-import { LISTINGS } from "@/lib/listings";
+import { ApiError, apiPost } from "@/lib/api/client";
+import type { AssistantRequest, AssistantResponse } from "@/lib/api/types";
 import type { ChatMessage, PriceAlert } from "@/lib/types";

 export const MAX_COMPARE = 3;
 export type AvatarAnimation = "idle" | "thinking" | "happy";

-const STORAGE_KEY = "torobcar:v1";
+const STORAGE_KEY = "torobcar:v2"; // v1 held synthetic ids and is ignored
 const TOAST_MS = 2200;
-const REPLY_DELAY_MS = 700;
 const HAPPY_MS = 2500;
-const GREETING: ChatMessage = { role: "assistant", text: "سلام! بگو دنبال چه ماشینی هستی، یا بپرس کدوم آگهی به‌صرفه‌تره. من همهٔ آگهی‌های فعال رو می‌بینم." };
+const HISTORY_LIMIT = 10; // the backend caps history at 10 messages
+const GREETING: ChatMessage = { role: "assistant", text: "سلام! بگو دنبال چه ماشینی هستی، یا بپرس کدوم آگهی به‌صرفه‌تره. من همهٔ آگهی‌های فعال رو می‌بینم.", listings: [] };
+const CHAT_UNAVAILABLE = "الان به سرویس جست‌وجو دسترسی ندارم؛ چند لحظه بعد دوباره بپرس.";

 interface Persisted { compare: string[]; saved: string[]; alerts: PriceAlert[]; loggedIn: boolean; }
 const EMPTY: Persisted = { compare: [], saved: [], alerts: [], loggedIn: false };
@@ -45,6 +46,9 @@ export interface AppStateValue extends Persisted {

 const AppStateContext = createContext<AppStateValue | null>(null);

+const isAlert = (a: unknown): a is PriceAlert =>
+  typeof a === "object" && a !== null && typeof (a as PriceAlert).title === "string" && typeof (a as PriceAlert).threshold === "number" && typeof (a as PriceAlert).params === "object";
+
 function readPersisted(): Persisted {
   try {
     const raw = window.localStorage.getItem(STORAGE_KEY);
@@ -53,7 +57,7 @@ function readPersisted(): Persisted {
     return {
       compare: Array.isArray(parsed.compare) ? parsed.compare.slice(0, MAX_COMPARE) : EMPTY.compare,
       saved: Array.isArray(parsed.saved) ? parsed.saved : EMPTY.saved,
-      alerts: Array.isArray(parsed.alerts) ? parsed.alerts : EMPTY.alerts,
+      alerts: Array.isArray(parsed.alerts) ? parsed.alerts.filter(isAlert) : EMPTY.alerts,
       loggedIn: typeof parsed.loggedIn === "boolean" ? parsed.loggedIn : EMPTY.loggedIn,
     };
   } catch {
@@ -61,6 +65,9 @@ function readPersisted(): Persisted {
   }
 }

+const toAssistantMessages = (messages: ChatMessage[]): AssistantRequest["messages"] =>
+  messages.slice(-HISTORY_LIMIT).map(({ role, text }) => ({ role, text }));
+
 export function AppStateProvider({ children }: { children: React.ReactNode }) {
   const [persisted, setPersisted] = useState<Persisted>(EMPTY);
   const [hydrated, setHydrated] = useState(false);
@@ -72,9 +79,10 @@ export function AppStateProvider({ children }: { children: React.ReactNode }) {
   const [toast, setToast] = useState("");
   const toastTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
   const happyTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
-  const replyTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
   const persistedRef = useRef<Persisted>(EMPTY);
+  const chatRef = useRef<ChatMessage[]>([GREETING]);
   const chatBusyRef = useRef(false);
+  const mountedRef = useRef(true);

   // Load after mount so server and first client render match.
   useEffect(() => {
@@ -92,10 +100,11 @@ export function AppStateProvider({ children }: { children: React.ReactNode }) {
   // Clear pending timers on unmount so a fired timeout never calls setState
   // after teardown (Strict Mode mounts/unmounts/remounts in dev).
   useEffect(() => {
+    mountedRef.current = true;
     return () => {
+      mountedRef.current = false;
       clearTimeout(toastTimer.current);
       clearTimeout(happyTimer.current);
-      clearTimeout(replyTimer.current);
     };
   }, []);

@@ -150,23 +159,32 @@ export function AppStateProvider({ children }: { children: React.ReactNode }) {
     setBellOpen(false);
   }, [showToast]);

+  const appendChat = useCallback((message: ChatMessage) => {
+    chatRef.current = [...chatRef.current, message];
+    setChatMessages(chatRef.current);
+  }, []);
+
+  // Stateless assistant: every call carries the recent history and the compare ids.
   const sendChat = useCallback((raw: string) => {
     const text = raw.trim();
     if (!text || chatBusyRef.current) return;
     chatBusyRef.current = true;
-    setChatMessages((m) => [...m, { role: "user", text }]);
     setChatBusy(true);
-    const compareIds = persistedRef.current.compare;
-    clearTimeout(replyTimer.current);
-    replyTimer.current = setTimeout(() => {
-      setChatMessages((m) => [...m, { role: "assistant", ...scriptedReply(text, LISTINGS, compareIds) }]);
-      chatBusyRef.current = false;
-      setChatBusy(false);
-      setRecentReply(true);
-      clearTimeout(happyTimer.current);
-      happyTimer.current = setTimeout(() => setRecentReply(false), HAPPY_MS);
-    }, REPLY_DELAY_MS);
-  }, []);
+    appendChat({ role: "user", text, listings: [] });
+    const body: AssistantRequest = { messages: toAssistantMessages(chatRef.current), compare_ids: persistedRef.current.compare };
+    apiPost<AssistantResponse>("/assistant", body)
+      .then((reply) => ({ role: "assistant" as const, text: reply.text, listings: reply.listings }))
+      .catch((error: unknown) => ({ role: "assistant" as const, text: error instanceof ApiError && error.status === 422 ? error.message : CHAT_UNAVAILABLE, listings: [] }))
+      .then((message) => {
+        if (!mountedRef.current) return;
+        appendChat(message);
+        chatBusyRef.current = false;
+        setChatBusy(false);
+        setRecentReply(true);
+        clearTimeout(happyTimer.current);
+        happyTimer.current = setTimeout(() => setRecentReply(false), HAPPY_MS);
+      });
+  }, [appendChat]);

   const avatarAnimation: AvatarAnimation = chatBusy ? "thinking" : recentReply ? "happy" : "idle";

````

- [ ] **Step 2: Run the tests to verify they pass**

Run: `bun test`
Expected: `27 pass, 0 fail`; `bunx tsc --noEmit 2>&1 | cut -d'(' -f1 | sort -u` lists only the 21 files above.

- [ ] **Step 3: Commit**

From the repo root (`cd ..`), stage explicit paths only (never `git add -A`):

````bash
git add frontend/src/components/AlertsDropdown.tsx frontend/src/components/BreakdownCard.tsx frontend/src/components/ChatPanel.tsx frontend/src/components/ErrorBanner.module.css frontend/src/components/ErrorBanner.tsx frontend/src/components/Footer.tsx frontend/src/components/ListingCard.module.css frontend/src/components/ListingCard.tsx frontend/src/components/ListingRow.tsx frontend/src/components/MiniListing.tsx frontend/src/components/Skeleton.module.css frontend/src/components/Skeleton.tsx frontend/src/components/VerdictBadge.tsx frontend/src/state/AppState.tsx
git commit -m "feat(frontend): wire app state, chat and alerts to the API

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git log -1 --format='%(trailers)'   # must print exactly: Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
````

---

### Task 9: Home page (server) and the results island

**Files:**
- Create: `frontend/src/app/error.tsx`
- Create: `frontend/src/app/loading.tsx`
- Modify: `frontend/src/app/page.module.css`
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/app/results/page.tsx`
- Modify: `frontend/src/components/FiltersPanel.module.css`
- Modify: `frontend/src/components/FiltersPanel.tsx`
- Modify: `frontend/src/components/HomeSearch.tsx`
- Modify: `frontend/src/components/ListingsMap.tsx`
- Modify: `frontend/src/components/MapCard.tsx`
- Modify: `frontend/src/components/ModelCard.tsx`
- Modify: `frontend/src/components/ParsedChips.module.css`
- Modify: `frontend/src/components/ParsedChips.tsx`
- Modify: `frontend/src/components/ResultsScreen.module.css`
- Modify: `frontend/src/components/ResultsScreen.tsx`
- Modify: `frontend/src/components/ResultsToolbar.tsx`

**Interfaces:**
- Consumes: `apiGet<Facets>`, `apiGet<SearchResponse>`, `apiGet<ModelStats>`, `useApi`, `queryToParams`/`paramsToQuery`/`activeFilterCount`/`DEFAULT_PAGE_SIZE`, `cardOf`, `ErrorBanner`, `CardSkeletons`, `useAppState().addAlert`, `connection` from `next/server`.
- Produces: `app/page.tsx` (Server Component: total ads, model count, «به‌روزرسانی» from `data_as_of`, per-category links to `/results?category=`); `app/error.tsx` (`retry`), `app/loading.tsx`; `app/results/page.tsx` (client, `Suspense`, keyed by the query string); `ResultsScreen({ params: SearchParams })`; `FiltersPanel({ params, facets, onChange, onReset, open, onClose, resultCount })`; `ResultsToolbar` (sorts from `SORTS`/`SORT_NAMES`); `ModelCard({ stats, axisMin, axisMax })`; `ParsedChips({ chips, hint? })`; `MapCard`/`ListingsMap` over `ListingCard[]` (cards without coordinates are skipped).

Spec §5 (`/` and `/results`), §6. The URL is the single source of truth: every filter/sort change is `router.replace('/results' + paramsToQuery(next))`, which remounts the screen (the page keys on the query string) and issues a new `/search`. "بیشتر" appends the next page from a click handler (`setMore`), never from an effect. Exact matches render first, then the «آگهی‌های مشابه» divider and the near-misses with their labels. One `/models/{model}/stats` range card per resolved model (≤ 4, or the `models` filter), drawn on an axis from the lowest `price_min` to the highest `price_max` shown. «تفسیر: قواعد» appears when `parsed_by === "rules"`. Save & alert stores `params` + threshold (Deviation 12). The filter sheet's category selector, top models/cities with counts and gearbox (cars or no category only) come from `/facets?category=`. `await connection()` on the home page is what keeps `next build` from calling the API (Deviation 5). **`tsc` still red in:** `src/app/compare/page.tsx`, `src/app/estimate/page.tsx`, `src/app/listing/[id]/page.tsx`, `src/app/model/[id]/page.tsx`, `src/components/{CompareTable,EstimateForm,EstimateResultCard,IssueBars,ListingScreen,ModelScreen,PriceCard,PriceHistogram,SellerAssessmentCard,SummaryCard}.tsx` — 14 files.

- [ ] **Step 1: Implement**

Create `frontend/src/app/error.tsx`:

````tsx
"use client"; // error boundaries must be Client Components
import { useEffect } from "react";
import { SERVICE_UNAVAILABLE } from "@/components/ErrorBanner";
import styles from "./not-found.module.css";

// Next 16 passes `retry` (not `reset`) to error boundaries.
export default function RouteError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => { console.error(error); }, [error]);
  return (
    <section className={styles.screen}>
      <div className={styles.card}>
        <h1 className={styles.title}>{SERVICE_UNAVAILABLE}</h1>
        <p className={styles.lead}>چند لحظه بعد دوباره امتحان کن.</p>
        <button type="button" className={styles.cta} onClick={() => retry()}>تلاش دوباره</button>
      </div>
    </section>
  );
}
````

Create `frontend/src/app/loading.tsx`:

````tsx
import { Skeleton } from "@/components/Skeleton";

export default function Loading() {
  return (
    <section style={{ padding: "48px 0" }}>
      <Skeleton lines={[40, 56, 20]} width="min(680px, 100%)" />
    </section>
  );
}
````

Modify `frontend/src/app/page.module.css` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/app/page.module.css b/frontend/src/app/page.module.css
index 1de1c62..422db9d 100644
--- a/frontend/src/app/page.module.css
+++ b/frontend/src/app/page.module.css
@@ -44,3 +44,8 @@
     gap: 16px;
   }
 }
+
+.categories { margin-top: 20px; display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }
+.category { font-size: 13px; color: var(--ink-2); background: var(--surface); border: 1px solid var(--line); border-radius: 999px; padding: 6px 14px; }
+.category b { color: var(--ink); font-weight: 700; margin-inline-start: 4px; }
+.category:hover { border-color: var(--line-strong); color: var(--ink); }
````

Modify `frontend/src/app/page.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/app/page.tsx b/frontend/src/app/page.tsx
index e30b4ed..d72add0 100644
--- a/frontend/src/app/page.tsx
+++ b/frontend/src/app/page.tsx
@@ -1,10 +1,19 @@
+import Link from "next/link";
+import { connection } from "next/server";
 import { HomeSearch } from "@/components/HomeSearch";
-import { MODELS } from "@/lib/catalog";
-import { fa } from "@/lib/format";
-import { LISTINGS } from "@/lib/listings";
+import { apiGet } from "@/lib/api/client";
+import type { Facets } from "@/lib/api/types";
+import { fa, relativeTime } from "@/lib/format";
+import { CATEGORY_NAMES, CATEGORY_ORDER } from "@/lib/labels";
 import styles from "./page.module.css";

-export default function HomePage() {
+// Server Component: fetched on every request inside the Compose network; a failure
+// renders app/error.tsx («سرویس جست‌وجو در دسترس نیست»), never made-up numbers.
+export default async function HomePage() {
+  await connection(); // Next 16 would otherwise prerender this page (and call the API) at build time
+  const facets = await apiGet<Facets>("/facets");
+  const total = Object.values(facets.categories).reduce((sum, count) => sum + (count ?? 0), 0);
+  const updated = facets.data_as_of ? relativeTime(facets.data_as_of, new Date()) : "نامشخص";
   return (
     <section className={styles.home}>
       {/* eslint-disable-next-line @next/next/no-img-element */}
@@ -12,10 +21,17 @@ export default function HomePage() {
       <h1 className={styles.title}>ماشین می‌خوای؟ فقط بگو چی.</h1>
       <HomeSearch />
       <div className={styles.stats}>
-        <span><b className={styles.statNum}>{fa(LISTINGS.length)}</b> آگهی فعال</span>
-        <span><b className={styles.statNum}>{fa(MODELS.length)}</b> مدل</span>
-        <span>به‌روزرسانی: <b className={styles.statNum}>۱۲ دقیقه پیش</b></span>
+        <span><b className={styles.statNum}>{fa(total.toLocaleString("en-US"))}</b> آگهی فعال</span>
+        <span><b className={styles.statNum}>{fa(facets.model_count)}</b> مدل</span>
+        <span>به‌روزرسانی: <b className={styles.statNum} suppressHydrationWarning>{updated}</b></span>
       </div>
+      <nav className={styles.categories} aria-label="دسته‌ها">
+        {CATEGORY_ORDER.filter((category) => facets.categories[category]).map((category) => (
+          <Link key={category} href={`/results?category=${category}`} className={styles.category}>
+            {CATEGORY_NAMES[category]} <b>{fa((facets.categories[category] ?? 0).toLocaleString("en-US"))}</b>
+          </Link>
+        ))}
+      </nav>
     </section>
   );
 }
````

Modify `frontend/src/app/results/page.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/app/results/page.tsx b/frontend/src/app/results/page.tsx
index 61e0aef..6e61cce 100644
--- a/frontend/src/app/results/page.tsx
+++ b/frontend/src/app/results/page.tsx
@@ -1,13 +1,17 @@
 "use client";
 import { useSearchParams } from "next/navigation";
-import { Suspense } from "react";
+import { Suspense, useMemo } from "react";
 import { ResultsScreen } from "@/components/ResultsScreen";
+import { CardSkeletons } from "@/components/Skeleton";
+import { queryToParams } from "@/lib/search";

 function Results() {
-  const query = useSearchParams().get("q") ?? "";
-  return <ResultsScreen key={query} query={query} />; // key resets filters when the query changes
+  const query = useSearchParams();
+  const params = useMemo(() => queryToParams(query), [query]);
+  // The URL is the single source of truth: a new query string is a new screen.
+  return <ResultsScreen key={query.toString()} params={params} />;
 }

 export default function ResultsPage() {
-  return <Suspense fallback={null}><Results /></Suspense>;
+  return <Suspense fallback={<CardSkeletons count={4} />}><Results /></Suspense>;
 }
````

Modify `frontend/src/components/FiltersPanel.module.css` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/FiltersPanel.module.css b/frontend/src/components/FiltersPanel.module.css
index bc7bce1..2aa9098 100644
--- a/frontend/src/components/FiltersPanel.module.css
+++ b/frontend/src/components/FiltersPanel.module.css
@@ -229,3 +229,4 @@
     min-height: 40px;
   }
 }
+.select { display: block; width: 100%; margin-top: 6px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); font: inherit; font-size: 13px; color: var(--ink); }
````

Modify `frontend/src/components/FiltersPanel.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/FiltersPanel.tsx b/frontend/src/components/FiltersPanel.tsx
index c91db93..2b47a5a 100644
--- a/frontend/src/components/FiltersPanel.tsx
+++ b/frontend/src/components/FiltersPanel.tsx
@@ -1,39 +1,83 @@
 "use client";
-import { CITIES, MODELS } from "@/lib/catalog";
-import { fa, num } from "@/lib/format";
-import { listingsOfModel } from "@/lib/listings";
-import type { Filters, GearFilter } from "@/lib/types";
+import type { Category, Facets, Gearbox } from "@/lib/api/types";
+import { fa, formatToman } from "@/lib/format";
+import { CATEGORY_NAMES, CATEGORY_ORDER, GEARBOX_NAMES } from "@/lib/labels";
+import type { SearchOverrides } from "@/lib/search";
 import styles from "./FiltersPanel.module.css";

-const GEARS: GearFilter[] = ["همه", "دنده‌ای", "اتوماتیک"];
-const toggle = <T,>(list: T[], item: T): T[] => (list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);
+const MILLION = 1_000_000;
+const PRICE_CAPS = [200, 300, 500, 700, 1_000, 1_500, 2_000, 3_000, 5_000].map((m) => m * MILLION);
+const KM_CAPS = [30_000, 50_000, 90_000, 120_000, 150_000, 200_000, 300_000];
+const CURRENT_YEAR = 1405;
+const YEARS = Array.from({ length: 26 }, (_, i) => CURRENT_YEAR - i);
+const TOP_MODELS = 12;
+const TOP_CITIES = 12;
+const toggle = (list: string[] | undefined, item: string): string[] | undefined => {
+  const next = list?.includes(item) ? list.filter((x) => x !== item) : [...(list ?? []), item];
+  return next.length ? next : undefined;
+};

-interface Props { filters: Filters; onChange(next: Filters): void; onReset(): void; open: boolean; onClose(): void; resultCount: number; }
+interface Props { params: SearchOverrides; facets: Facets | null; onChange(next: SearchOverrides): void; onReset(): void; open: boolean; onClose(): void; resultCount: number | null; }

-export function FiltersPanel({ filters, onChange, onReset, open, onClose, resultCount }: Props) {
-  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
+export function FiltersPanel({ params, facets, onChange, onReset, open, onClose, resultCount }: Props) {
+  const set = (patch: Partial<SearchOverrides>) => onChange({ ...params, ...patch });
+  const models = [...new Set([...(params.models ?? []), ...(facets?.models.slice(0, TOP_MODELS).map((m) => m.model) ?? [])])];
+  const cities = [...new Set([...(params.cities ?? []), ...(facets?.cities.slice(0, TOP_CITIES).map((c) => c.value) ?? [])])];
+  const countOf = (list: { model?: string; value?: string; count: number }[] | undefined, name: string): string =>
+    list?.find((item) => (item.model ?? item.value) === name)?.count.toString() ?? "";
+  const showGearbox = !params.category || params.category === "light";
   return (
     <>
       <aside className={styles.panel} data-open={open}>
         <div className={styles.sheetHead}><span className={styles.grabber} /><div className={styles.sheetTitleRow}><span className={styles.sheetTitle}>فیلترها</span><button className={styles.clear} onClick={onReset}>پاک‌کردن</button></div></div>
         <div className={styles.deskHead}>فیلترها</div>
         <div className={styles.body}>
+          <div className={styles.label}>دسته</div>
+          <div className={styles.cities}>
+            <button className={styles.pill} data-on={!params.category} aria-pressed={!params.category} onClick={() => set({ category: undefined, models: undefined, gearbox: undefined })}>همه</button>
+            {CATEGORY_ORDER.map((category: Category) => (
+              <button key={category} className={styles.pill} data-on={params.category === category} aria-pressed={params.category === category} onClick={() => set({ category, models: undefined, gearbox: category === "light" ? params.gearbox : undefined })}>
+                {CATEGORY_NAMES[category]}{!params.category && facets?.categories[category] ? ` (${fa(facets.categories[category] ?? 0)})` : ""}
+              </button>
+            ))}
+          </div>
           <div className={styles.label}>مدل</div>
-          <div className={styles.models}>{MODELS.map((m) => (
-            <label key={m.id} className={styles.check}><input type="checkbox" checked={filters.models.includes(m.id)} onChange={() => set({ models: toggle(filters.models, m.id) })} />{m.name}<span className={styles.count}>{fa(listingsOfModel(m.id).length)}</span></label>
+          <div className={styles.models}>{models.map((model) => (
+            <label key={model} className={styles.check}><input type="checkbox" checked={params.models?.includes(model) ?? false} onChange={() => set({ models: toggle(params.models, model) })} />{model}<span className={styles.count}>{fa(countOf(facets?.models, model))}</span></label>
           ))}</div>
           <div className={styles.label}>شهر</div>
-          <div className={styles.cities}>{CITIES.map((c) => <button key={c.name} className={styles.pill} data-on={filters.cities.includes(c.name)} aria-pressed={filters.cities.includes(c.name)} onClick={() => set({ cities: toggle(filters.cities, c.name) })}>{c.name}</button>)}</div>
-          <div className={styles.rangeHead}><span>حداکثر قیمت</span><b>{num(filters.maxPrice)} میلیون</b></div>
-          <input type="range" min={300} max={1400} step={10} value={filters.maxPrice} onChange={(e) => set({ maxPrice: Number(e.target.value) })} className={styles.range} aria-label="حداکثر قیمت" />
-          <div className={styles.rangeHead}><span>حداکثر کارکرد</span><b>{fa(filters.maxKm)} هزار کیلومتر</b></div>
-          <input type="range" min={10} max={250} step={5} value={filters.maxKm} onChange={(e) => set({ maxKm: Number(e.target.value) })} className={styles.range} aria-label="حداکثر کارکرد" />
-          <div className={styles.label}>گیربکس</div>
-          <div className={styles.gears}>{GEARS.map((g) => <button key={g} className={styles.gear} data-on={filters.gear === g} aria-pressed={filters.gear === g} onClick={() => set({ gear: g })}>{g}</button>)}</div>
-          <label className={`${styles.check} ${styles.onlyBelow}`}><input type="checkbox" checked={filters.onlyBelow} onChange={() => set({ onlyBelow: !filters.onlyBelow })} />فقط ارزان‌تر از بازار</label>
+          <div className={styles.cities}>{cities.map((city) => <button key={city} className={styles.pill} data-on={params.cities?.includes(city) ?? false} aria-pressed={params.cities?.includes(city) ?? false} onClick={() => set({ cities: toggle(params.cities, city) })}>{city} <span className={styles.count}>{fa(countOf(facets?.cities, city))}</span></button>)}</div>
+          <label className={styles.label}>حداکثر قیمت
+            <select className={styles.select} value={params.price_max ?? ""} onChange={(e) => set({ price_max: e.target.value ? Number(e.target.value) : undefined })} aria-label="حداکثر قیمت">
+              <option value="">بدون سقف</option>
+              {PRICE_CAPS.map((cap) => <option key={cap} value={cap}>{formatToman(cap)}</option>)}
+            </select>
+          </label>
+          <label className={styles.label}>حداکثر کارکرد
+            <select className={styles.select} value={params.km_max ?? ""} onChange={(e) => set({ km_max: e.target.value ? Number(e.target.value) : undefined })} aria-label="حداکثر کارکرد">
+              <option value="">بدون سقف</option>
+              {KM_CAPS.map((cap) => <option key={cap} value={cap}>{fa(cap / 1000)} هزار کیلومتر</option>)}
+            </select>
+          </label>
+          <label className={styles.label}>مدل (سال)
+            <select className={styles.select} value={params.year ?? ""} onChange={(e) => set({ year: e.target.value ? Number(e.target.value) : undefined })} aria-label="سال">
+              <option value="">همهٔ سال‌ها</option>
+              {YEARS.map((year) => <option key={year} value={year}>{fa(year)}</option>)}
+            </select>
+          </label>
+          {showGearbox && (
+            <>
+              <div className={styles.label}>گیربکس</div>
+              <div className={styles.gears}>
+                <button className={styles.gear} data-on={!params.gearbox} aria-pressed={!params.gearbox} onClick={() => set({ gearbox: undefined })}>همه</button>
+                {(["manual", "automatic"] as Gearbox[]).map((g) => <button key={g} className={styles.gear} data-on={params.gearbox === g} aria-pressed={params.gearbox === g} onClick={() => set({ gearbox: g })}>{GEARBOX_NAMES[g]}</button>)}
+              </div>
+            </>
+          )}
+          <label className={`${styles.check} ${styles.onlyBelow}`}><input type="checkbox" checked={params.only_below ?? false} onChange={() => set({ only_below: params.only_below ? undefined : true })} />فقط ارزان‌تر از بازار</label>
           <button className={styles.deskReset} onClick={onReset}>پاک‌کردن فیلترها</button>
         </div>
-        <div className={styles.sheetFoot}><button className={styles.apply} onClick={onClose}>نمایش {fa(resultCount)} آگهی</button></div>
+        <div className={styles.sheetFoot}><button className={styles.apply} onClick={onClose}>{resultCount === null ? "نمایش آگهی‌ها" : `نمایش ${fa(resultCount)} آگهی`}</button></div>
       </aside>
       {open && <div className={styles.backdrop} onClick={onClose} />}
     </>
````

Modify `frontend/src/components/HomeSearch.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/HomeSearch.tsx b/frontend/src/components/HomeSearch.tsx
index 07358fa..04156f1 100644
--- a/frontend/src/components/HomeSearch.tsx
+++ b/frontend/src/components/HomeSearch.tsx
@@ -5,11 +5,12 @@ import { useState } from "react";
 import { Icon } from "./Icon";
 import styles from "./HomeSearch.module.css";

+// Real queries that return results on the crawled data (checked against the API).
 const EXAMPLES = [
-  "پژو ۲۰۶ کم‌کارکرد تهران",
-  "دنا پلاس اتومات زیر یک میلیارد",
-  "تارا ارزان‌تر از بازار",
-  "جک J4 زیر ۹۰۰ میلیون",
+  "پژو ۲۰۶ تیپ ۲ تهران",
+  "پراید زیر ۳۰۰ میلیون",
+  "دنا پلاس اتومات",
+  "سمند مدل ۹۵ به بالا مشهد",
 ];

 export function HomeSearch() {
````

Modify `frontend/src/components/ListingsMap.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/ListingsMap.tsx b/frontend/src/components/ListingsMap.tsx
index 11b2657..5679abd 100644
--- a/frontend/src/components/ListingsMap.tsx
+++ b/frontend/src/components/ListingsMap.tsx
@@ -4,35 +4,39 @@ import L from "leaflet";
 import "leaflet/dist/leaflet.css";
 import { useRouter } from "next/navigation";
 import { useEffect, useRef } from "react";
-import { RED } from "@/lib/catalog";
-import { fa, num } from "@/lib/format";
-import { verdictOf } from "@/lib/pricing";
-import type { Listing } from "@/lib/types";
+import type { ListingCard } from "@/lib/api/types";
+import { formatToman } from "@/lib/format";
+import { verdictStyle } from "@/lib/pricing";
+import { RED } from "@/lib/theme";

 const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
 const SINGLE_ZOOM = 13;
 const APPROXIMATE_RADIUS_M = 900;
 const BOUNDS_PADDING = 0.3;

-export default function ListingsMap({ listings, single = false }: { listings: Listing[]; single?: boolean }) {
+type Pinned = ListingCard & { lat: number; lng: number };
+const pinnable = (l: ListingCard): l is Pinned => l.lat !== null && l.lng !== null;
+
+export default function ListingsMap({ listings, single = false }: { listings: ListingCard[]; single?: boolean }) {
   const elementRef = useRef<HTMLDivElement>(null);
   const router = useRouter();

   useEffect(() => {
-    if (!elementRef.current || listings.length === 0) return;
+    const pins = listings.filter(pinnable);
+    if (!elementRef.current || pins.length === 0) return;
     const map = L.map(elementRef.current, { scrollWheelZoom: !single });
     L.tileLayer(TILE_URL, { attribution: "© OpenStreetMap" }).addTo(map);
-    for (const l of listings) {
-      L.circleMarker([l.lat, l.lng], { radius: 9, color: "#fff", weight: 2, fillColor: verdictOf(l.diffPct).color, fillOpacity: 0.95 })
-        .bindTooltip(`${l.modelName} ${fa(l.year)} · ${num(l.price)} میلیون`, { direction: "top" })
+    for (const l of pins) {
+      L.circleMarker([l.lat, l.lng], { radius: 9, color: "#fff", weight: 2, fillColor: verdictStyle(l.verdict).color, fillOpacity: 0.95 })
+        .bindTooltip(`${l.trim ?? l.title} · ${l.price === null ? "توافقی" : formatToman(l.price)}`, { direction: "top" })
         .on("click", () => router.push(`/listing/${l.id}`)).addTo(map);
     }
     if (single) {
-      const [only] = listings;
+      const [only] = pins;
       L.circle([only.lat, only.lng], { radius: APPROXIMATE_RADIUS_M, color: RED, weight: 1, fillColor: RED, fillOpacity: 0.12 }).addTo(map);
       map.setView([only.lat, only.lng], SINGLE_ZOOM);
     } else {
-      map.fitBounds(L.latLngBounds(listings.map((l) => [l.lat, l.lng] as [number, number])).pad(BOUNDS_PADDING));
+      map.fitBounds(L.latLngBounds(pins.map((l) => [l.lat, l.lng] as [number, number])).pad(BOUNDS_PADDING));
     }
     return () => { map.remove(); };
   }, [listings, single, router]);
````

Modify `frontend/src/components/MapCard.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/MapCard.tsx b/frontend/src/components/MapCard.tsx
index 2052283..f9d5985 100644
--- a/frontend/src/components/MapCard.tsx
+++ b/frontend/src/components/MapCard.tsx
@@ -1,12 +1,12 @@
 "use client";

 import dynamic from "next/dynamic";
-import type { Listing } from "@/lib/types";
+import type { ListingCard } from "@/lib/api/types";
 import styles from "./MapCard.module.css";

 const ListingsMap = dynamic(() => import("./ListingsMap"), { ssr: false });

-interface Props { title: string; hint: string; listings: Listing[]; single?: boolean; sticky?: boolean; }
+interface Props { title: string; hint: string; listings: ListingCard[]; single?: boolean; sticky?: boolean; }

 export function MapCard({ title, hint, listings, single = false, sticky = false }: Props) {
   return (
````

Modify `frontend/src/components/ModelCard.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/ModelCard.tsx b/frontend/src/components/ModelCard.tsx
index f7ee1f9..c892cad 100644
--- a/frontend/src/components/ModelCard.tsx
+++ b/frontend/src/components/ModelCard.tsx
@@ -1,17 +1,28 @@
 import Link from "next/link";
-import type { ModelRange } from "@/lib/modelStats";
+import type { ModelStats } from "@/lib/api/types";
+import { fa, formatToman } from "@/lib/format";
 import styles from "./ModelCard.module.css";

-export function ModelCard({ range }: { range: ModelRange }) {
+interface Props { stats: ModelStats; axisMin: number; axisMax: number; }
+
+/** Price range bar on an axis shared by every model card shown (lowest min → highest max). */
+export function ModelCard({ stats, axisMin, axisMax }: Props) {
+  const span = Math.max(1, axisMax - axisMin);
+  const min = stats.price_min ?? axisMin;
+  const max = stats.price_max ?? min;
+  const start = Math.max(0, Math.min(100, ((min - axisMin) / span) * 100));
+  const width = Math.max(1, Math.min(100 - start, ((max - min) / span) * 100));
   return (
-    <Link href={`/model/${range.id}`} className={styles.card}>
+    <Link href={`/model/${encodeURIComponent(stats.model)}`} className={styles.card}>
       <div className={styles.head}>
-        <span className={styles.name}>{range.name}</span>
-        <span className={styles.count}>{range.countFa} آگهی</span>
+        <span className={styles.name}>{stats.model}</span>
+        <span className={styles.count}>{fa(stats.count)} آگهی</span>
+      </div>
+      <div className={styles.range}>
+        {stats.price_min === null || stats.price_max === null ? "بدون قیمت" : <>از <b className={styles.bold}>{formatToman(stats.price_min)}</b> تا <b className={styles.bold}>{formatToman(stats.price_max)}</b></>}
       </div>
-      <div className={styles.range}>از <b className={styles.bold}>{range.minFa}</b> تا <b className={styles.bold}>{range.maxFa}</b> میلیون</div>
       <div className={styles.bar}>
-        <div className={styles.barFill} style={{ right: `${range.barStartPct}%`, width: `${range.barWidthPct}%` }} />
+        <div className={styles.barFill} style={{ right: `${start}%`, width: `${width}%` }} />
       </div>
       <div className={styles.cta}>مشاهده صفحهٔ مدل ←</div>
     </Link>
````

Modify `frontend/src/components/ParsedChips.module.css` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/ParsedChips.module.css b/frontend/src/components/ParsedChips.module.css
index f65ce32..0d4f38e 100644
--- a/frontend/src/components/ParsedChips.module.css
+++ b/frontend/src/components/ParsedChips.module.css
@@ -25,3 +25,4 @@
   font-weight: 600;
   font-size: 12px;
 }
+.hint { font-size: 11px; color: var(--faint); margin-inline-start: auto; }
````

Modify `frontend/src/components/ParsedChips.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/ParsedChips.tsx b/frontend/src/components/ParsedChips.tsx
index 7eda66d..5451f93 100644
--- a/frontend/src/components/ParsedChips.tsx
+++ b/frontend/src/components/ParsedChips.tsx
@@ -1,7 +1,7 @@
 import { Icon } from "./Icon";
 import styles from "./ParsedChips.module.css";

-export function ParsedChips({ chips }: { chips: string[] }) {
+export function ParsedChips({ chips, hint }: { chips: string[]; hint?: string }) {
   return (
     <div className={styles.row}>
       <span className={styles.label}>
@@ -11,6 +11,7 @@ export function ParsedChips({ chips }: { chips: string[] }) {
       {chips.map((chip) => (
         <span key={chip} className={styles.chip}>{chip}</span>
       ))}
+      {hint && <span className={styles.hint}>{hint}</span>}
     </div>
   );
 }
````

Modify `frontend/src/components/ResultsScreen.module.css` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/ResultsScreen.module.css b/frontend/src/components/ResultsScreen.module.css
index 93a60de..4d0dbee 100644
--- a/frontend/src/components/ResultsScreen.module.css
+++ b/frontend/src/components/ResultsScreen.module.css
@@ -39,3 +39,7 @@
     gap: 14px;
   }
 }
+.divider { margin: 20px 0 10px; font-size: 13px; font-weight: 700; color: var(--muted); display: flex; align-items: center; gap: 12px; }
+.divider::before, .divider::after { content: ""; flex: 1; height: 1px; background: var(--line); }
+.more { display: block; width: 100%; margin-top: 16px; padding: 12px; border: 1px solid var(--line); border-radius: 12px; background: var(--surface); color: var(--ink); font: inherit; font-weight: 600; cursor: pointer; }
+.more:disabled { opacity: .6; cursor: default; }
````

Modify `frontend/src/components/ResultsScreen.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/ResultsScreen.tsx b/frontend/src/components/ResultsScreen.tsx
index 6d434ea..534568d 100644
--- a/frontend/src/components/ResultsScreen.tsx
+++ b/frontend/src/components/ResultsScreen.tsx
@@ -1,55 +1,115 @@
 "use client";
 import { useRouter } from "next/navigation";
-import { useEffect, useMemo, useState } from "react";
-import { fa } from "@/lib/format";
-import { LISTINGS } from "@/lib/listings";
-import { modelRange } from "@/lib/modelStats";
-import { CHEAP_THRESHOLD_PCT } from "@/lib/pricing";
-import { DEFAULT_FILTERS, activeFilterCount, alertMatches, chipsOf, filterListings, filtersFromQuery, parseQuery, sortListings } from "@/lib/search";
-import type { Filters, SortKey } from "@/lib/types";
+import { useEffect, useState } from "react";
+import { ApiError, apiGet } from "@/lib/api/client";
+import type { Facets, ListingCard as ListingCardData, ModelStats, SearchParams, SearchResponse, SortKey } from "@/lib/api/types";
+import { useApi } from "@/lib/api/useApi";
+import { fa, formatToman } from "@/lib/format";
+import { DEFAULT_PAGE_SIZE, activeFilterCount, paramsToQuery } from "@/lib/search";
 import { cardOf } from "@/lib/view";
 import { useAppState } from "@/state/AppState";
+import { ErrorBanner } from "./ErrorBanner";
 import { FiltersPanel } from "./FiltersPanel";
 import { ListingCard } from "./ListingCard";
+import { MapCard } from "./MapCard";
 import { ModelCard } from "./ModelCard";
 import { ParsedChips } from "./ParsedChips";
 import { ResultsToolbar } from "./ResultsToolbar";
+import { CardSkeletons } from "./Skeleton";
 import styles from "./ResultsScreen.module.css";

 const MAX_MODEL_CARDS = 4;
+const RULES_HINT = "تفسیر: قواعد";
+const ALERT_ROUNDING = 10_000_000;

-export function ResultsScreen({ query }: { query: string }) {
+const uniqueModels = (items: ListingCardData[]): string[] =>
+  [...new Set(items.filter((l) => l.is_exact && l.model).map((l) => l.model as string))];
+
+const medianPrice = (items: ListingCardData[]): number => {
+  const prices = items.map((l) => l.price).filter((p): p is number => p !== null).sort((a, b) => a - b);
+  return prices.length ? prices[Math.floor(prices.length / 2)] : 0;
+};
+
+export function ResultsScreen({ params }: { params: SearchParams }) {
   const router = useRouter();
   const { addAlert } = useAppState();
-  const parsed = useMemo(() => (query ? parseQuery(query) : null), [query]);
-  const [filters, setFilters] = useState<Filters>(() => (parsed ? filtersFromQuery(parsed) : DEFAULT_FILTERS));
-  const [sort, setSort] = useState<SortKey>("score");
   const [sheetOpen, setSheetOpen] = useState(false);
+  const [more, setMore] = useState<ListingCardData[]>([]);
+  const [moreError, setMoreError] = useState<ApiError | null>(null);
+  const [loadingMore, setLoadingMore] = useState(false);
+
+  const query = paramsToQuery(params);
+  const search = useApi(`search${query}`, (signal) => apiGet<SearchResponse>("/search", { ...params, page: 1, page_size: DEFAULT_PAGE_SIZE }, signal));
+  const facets = useApi(`facets:${params.category ?? ""}`, (signal) => apiGet<Facets>("/facets", { category: params.category }, signal));
+
+  const items = [...(search.data?.items ?? []), ...more];
+  const modelsInResults = uniqueModels(items);
+  const modelNames = params.models?.length ? params.models : modelsInResults.length <= MAX_MODEL_CARDS ? modelsInResults : [];
+  const stats = useApi(modelNames.length ? `stats:${modelNames.join("|")}` : null, (signal) =>
+    Promise.all(modelNames.map((model) => apiGet<ModelStats>(`/models/${encodeURIComponent(model)}/stats`, {}, signal))));

   useEffect(() => { document.body.style.overflow = sheetOpen ? "hidden" : ""; return () => { document.body.style.overflow = ""; }; }, [sheetOpen]);

-  const filtered = useMemo(() => filterListings(LISTINGS, filters), [filters]);
-  const results = useMemo(() => sortListings(filtered, sort), [filtered, sort]);
-  const chips = parsed ? chipsOf(parsed) : [];
-  const modelsInResults = [...new Set(filtered.map((l) => l.modelId))];
-  const modelCardIds = filters.models.length ? filters.models : modelsInResults.length <= MAX_MODEL_CARDS ? modelsInResults : [];
-  const cheaperCount = filtered.filter((l) => l.diffPct <= CHEAP_THRESHOLD_PCT).length;
-  const activeCount = activeFilterCount(filters);
+  const navigate = (next: SearchParams) => router.replace(`/results${paramsToQuery(next)}`);
+  const exact = items.filter((l) => l.is_exact);
+  const nearMisses = items.filter((l) => !l.is_exact);
+  const total = search.data?.total ?? 0;
+  const hasMore = total > items.length;
+  const dataAsOf = facets.data?.data_as_of ?? null;
+
+  async function loadMore() {
+    if (!search.data || loadingMore) return;
+    setLoadingMore(true);
+    setMoreError(null);
+    const page = Math.floor(items.length / DEFAULT_PAGE_SIZE) + 1;
+    try {
+      const next = await apiGet<SearchResponse>("/search", { ...params, page, page_size: DEFAULT_PAGE_SIZE });
+      setMore((loaded) => [...loaded, ...next.items]);
+    } catch (error) {
+      setMoreError(error instanceof ApiError ? error : new ApiError(0, "network_error", "network failure"));
+    } finally {
+      setLoadingMore(false);
+    }
+  }

-  function resetFilters() { setFilters(DEFAULT_FILTERS); if (query) router.replace("/results"); }
   function saveSearch() {
-    addAlert({ title: chips.length ? chips.slice(0, 2).join(" · ") : "جست‌وجوی فعلی", threshold: filters.maxPrice, matches: alertMatches(filtered, filters.maxPrice) });
+    const chips = search.data?.intent.chips ?? [];
+    const threshold = params.price_max ?? Math.round(medianPrice(exact) / ALERT_ROUNDING) * ALERT_ROUNDING;
+    if (!threshold) return;
+    addAlert({ title: chips.length ? chips.slice(0, 2).join(" · ") : "جست‌وجوی فعلی", params, threshold });
   }

+  const axisMin = Math.min(...(stats.data ?? []).map((s) => s.price_min ?? Infinity));
+  const axisMax = Math.max(...(stats.data ?? []).map((s) => s.price_max ?? -Infinity));
+  const cheaperCount = exact.filter((l) => l.verdict === "cheap").length;
+  const activeCount = activeFilterCount(params);
+
   return (
     <section className={styles.layout}>
-      <FiltersPanel filters={filters} onChange={setFilters} onReset={resetFilters} open={sheetOpen} onClose={() => setSheetOpen(false)} resultCount={results.length} />
+      <FiltersPanel params={params} facets={facets.data} onChange={navigate} onReset={() => navigate(params.q ? { q: params.q } : {})} open={sheetOpen} onClose={() => setSheetOpen(false)} resultCount={search.data ? total : null} />
       <div className={styles.main}>
-        {chips.length > 0 && <ParsedChips chips={chips} />}
-        <ResultsToolbar countFa={fa(results.length)} subtitle={`${fa(cheaperCount)} آگهی ارزان‌تر از بازار`} filtersLabel={activeCount ? `فیلترها (${fa(activeCount)})` : "فیلترها"} onOpenFilters={() => setSheetOpen(true)} sort={sort} onSort={setSort} onSave={saveSearch} />
-        {modelCardIds.length > 0 && <div className={styles.modelCards}>{modelCardIds.map((id) => <ModelCard key={id} range={modelRange(id, LISTINGS)} />)}</div>}
-        <div className={styles.grid}>{results.map((l) => <ListingCard key={l.id} card={cardOf(l)} />)}</div>
-        {results.length === 0 && <div className={styles.empty}>با این فیلترها چیزی پیدا نشد. سقف قیمت یا کارکرد رو بالا ببر.</div>}
+        {search.data && search.data.intent.chips.length > 0 && (
+          <ParsedChips chips={search.data.intent.chips} hint={search.data.parsed_by === "rules" ? RULES_HINT : undefined} />
+        )}
+        <ResultsToolbar countFa={search.data ? fa(total) : "…"} subtitle={search.data ? `${fa(cheaperCount)} آگهی ارزان‌تر از بازار` : ""} filtersLabel={activeCount ? `فیلترها (${fa(activeCount)})` : "فیلترها"} onOpenFilters={() => setSheetOpen(true)} sort={params.sort ?? "relevance"} onSort={(sort: SortKey) => navigate({ ...params, sort })} onSave={saveSearch} />
+        {search.error && <ErrorBanner error={search.error} onRetry={search.retry} />}
+        {search.loading && <div className={styles.grid}><CardSkeletons count={6} /></div>}
+        {stats.data && stats.data.length > 0 && (
+          <div className={styles.modelCards}>{stats.data.map((s) => <ModelCard key={s.model} stats={s} axisMin={axisMin} axisMax={axisMax} />)}</div>
+        )}
+        {search.data && total === 0 && <div className={styles.empty}>با این شرایط چیزی پیدا نشد. سقف قیمت یا کارکرد رو بالا ببر یا شهر رو حذف کن.</div>}
+        {exact.length > 0 && <div className={styles.grid}>{exact.map((l) => <ListingCard key={l.id} card={cardOf(l, dataAsOf)} />)}</div>}
+        {nearMisses.length > 0 && (
+          <>
+            <div className={styles.divider}>آگهی‌های مشابه</div>
+            <div className={styles.grid}>{nearMisses.map((l) => <ListingCard key={l.id} card={cardOf(l, dataAsOf)} />)}</div>
+          </>
+        )}
+        {moreError && <ErrorBanner error={moreError} onRetry={loadMore} />}
+        {hasMore && <button type="button" className={styles.more} onClick={loadMore} disabled={loadingMore}>{loadingMore ? "در حال بارگذاری…" : `بیشتر (${fa(total - items.length)} آگهی دیگر)`}</button>}
+        {items.some((l) => l.lat !== null) && (
+          <MapCard title="آگهی‌ها روی نقشه" hint={`${fa(items.length)} آگهی بارگذاری‌شده · قیمت میانه ${formatToman(medianPrice(items))}`} listings={items} />
+        )}
       </div>
     </section>
   );
````

Modify `frontend/src/components/ResultsToolbar.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/ResultsToolbar.tsx b/frontend/src/components/ResultsToolbar.tsx
index 1de1a40..548deb4 100644
--- a/frontend/src/components/ResultsToolbar.tsx
+++ b/frontend/src/components/ResultsToolbar.tsx
@@ -1,16 +1,11 @@
 "use client";
-import type { SortKey } from "@/lib/types";
+import type { SortKey } from "@/lib/api/types";
+import { SORT_NAMES } from "@/lib/labels";
+import { SORTS } from "@/lib/search";
 import { useAppState } from "@/state/AppState";
 import { Icon } from "./Icon";
 import styles from "./ResultsToolbar.module.css";

-const SORTS: { value: SortKey; label: string }[] = [
-  { value: "score", label: "بهترین ارزش خرید" },
-  { value: "price", label: "ارزان‌ترین" },
-  { value: "km", label: "کم‌کارکردترین" },
-  { value: "new", label: "جدیدترین" },
-];
-
 interface Props {
   countFa: string;
   subtitle: string;
@@ -40,7 +35,7 @@ export function ResultsToolbar({ countFa, subtitle, filtersLabel, onOpenFilters,
         </button>
         <span className={styles.sortWrap}>
           <select value={sort} onChange={(event) => onSort(event.target.value as SortKey)} className={styles.select} aria-label="مرتب‌سازی">
-            {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
+            {SORTS.map((key) => <option key={key} value={key}>{SORT_NAMES[key]}</option>)}
           </select>
           <Icon name="chevronDown" stroke="#667085" className={styles.sortChev} />
         </span>
````

- [ ] **Step 2: Run the tests to verify they pass**

Run: `bun test`
Expected: `27 pass, 0 fail`; `tsc` red only in the 14 files above.

- [ ] **Step 3: Commit**

From the repo root (`cd ..`), stage explicit paths only (never `git add -A`):

````bash
git add frontend/src/app/error.tsx frontend/src/app/loading.tsx frontend/src/app/page.module.css frontend/src/app/page.tsx frontend/src/app/results/page.tsx frontend/src/components/FiltersPanel.module.css frontend/src/components/FiltersPanel.tsx frontend/src/components/HomeSearch.tsx frontend/src/components/ListingsMap.tsx frontend/src/components/MapCard.tsx frontend/src/components/ModelCard.tsx frontend/src/components/ParsedChips.module.css frontend/src/components/ParsedChips.tsx frontend/src/components/ResultsScreen.module.css frontend/src/components/ResultsScreen.tsx frontend/src/components/ResultsToolbar.tsx
git commit -m "feat(frontend): render the home page and results from the search API

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git log -1 --format='%(trailers)'   # must print exactly: Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
````

---

### Task 10: Listing page (server, dynamic)

**Files:**
- Create: `frontend/src/app/listing/[id]/loading.tsx`
- Modify: `frontend/src/app/listing/[id]/page.tsx`
- Modify: `frontend/src/components/ListingScreen.tsx`
- Modify: `frontend/src/components/PriceCard.tsx`
- Delete: `frontend/src/components/SellerAssessmentCard.module.css`
- Delete: `frontend/src/components/SellerAssessmentCard.tsx`
- Modify: `frontend/src/components/SummaryCard.tsx`

**Interfaces:**
- Consumes: `apiGet<ListingDetail>`, `apiGet<ListingCard[]>` (`/listings/{id}/similar?limit=3`), `ApiError`, `notFound`, `breakdownRows`, `summaryOf`, `verdictNote`, `specsOf`, `cardOf`, `BreakdownCard`, `MapCard`.
- Produces: `app/listing/[id]/page.tsx` (detail + similar in parallel; 404 **and** 422 (non-UUID id) → `notFound()`; anything else rethrown to `app/error.tsx`), `app/listing/[id]/loading.tsx`; `ListingScreen({ detail, similar })` (Server Component); `PriceCard({ detail, card })` (client: Divar link from `detail.url`, compare/save toggles); `SummaryCard({ summary })`; `SellerAssessmentCard` deleted.

Spec §5 (`/listing/[id]`). `generateStaticParams` is gone — the route renders on request. The gallery falls back to the thumbnail when `image_urls` is empty; the map card renders only with coordinates; the specs grid is per category via `specsOf`. Phone numbers are already masked by the API (Task 1). **`tsc` still red in:** `src/app/compare/page.tsx`, `src/app/estimate/page.tsx`, `src/app/model/[id]/page.tsx`, `src/components/{CompareTable,EstimateForm,EstimateResultCard,IssueBars,ModelScreen,PriceHistogram}.tsx` — 9 files.

- [ ] **Step 1: Implement**

Create `frontend/src/app/listing/[id]/loading.tsx`:

````tsx
import { Skeleton } from "@/components/Skeleton";

export default function Loading() {
  return (
    <section style={{ display: "grid", gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1fr)", gap: 20, padding: "20px 0" }}>
      <Skeleton lines={[380, 80, 120, 160]} />
      <Skeleton lines={[200, 160, 200]} />
    </section>
  );
}
````

Modify `frontend/src/app/listing/[id]/page.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/app/listing/[id]/page.tsx b/frontend/src/app/listing/[id]/page.tsx
index aa19502..31e4475 100644
--- a/frontend/src/app/listing/[id]/page.tsx
+++ b/frontend/src/app/listing/[id]/page.tsx
@@ -1,11 +1,24 @@
 import { notFound } from "next/navigation";
 import { ListingScreen } from "@/components/ListingScreen";
-import { LISTINGS, findListing } from "@/lib/listings";
+import { ApiError, apiGet } from "@/lib/api/client";
+import type { ListingCard, ListingDetail } from "@/lib/api/types";

-export const generateStaticParams = () => LISTINGS.map((l) => ({ id: l.id }));
+const SIMILAR_LIMIT = 3;
+const NOT_FOUND_STATUSES = [404, 422]; // 422 = not even a UUID

+// Rendered on request (no generateStaticParams): detail and similar in parallel.
 export default async function ListingPage({ params }: { params: Promise<{ id: string }> }) {
   const { id } = await params;
-  if (!findListing(id)) notFound();
-  return <ListingScreen listingId={id} />;
+  let detail: ListingDetail;
+  let similar: ListingCard[];
+  try {
+    [detail, similar] = await Promise.all([
+      apiGet<ListingDetail>(`/listings/${id}`),
+      apiGet<ListingCard[]>(`/listings/${id}/similar`, { limit: SIMILAR_LIMIT }),
+    ]);
+  } catch (error) {
+    if (error instanceof ApiError && NOT_FOUND_STATUSES.includes(error.status)) notFound();
+    throw error; // → app/error.tsx
+  }
+  return <ListingScreen detail={detail} similar={similar} />;
 }
````

Modify `frontend/src/components/ListingScreen.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/ListingScreen.tsx b/frontend/src/components/ListingScreen.tsx
index 18f8e82..cd2e34f 100644
--- a/frontend/src/components/ListingScreen.tsx
+++ b/frontend/src/components/ListingScreen.tsx
@@ -1,70 +1,51 @@
-"use client";
-
-import { useMemo } from "react";
-import { fa, num } from "@/lib/format";
-import { LISTINGS, findListing } from "@/lib/listings";
+import type { ListingCard, ListingDetail } from "@/lib/api/types";
+import { formatToman } from "@/lib/format";
 import { breakdownRows, summaryOf, verdictNote } from "@/lib/pricing";
-import type { Listing } from "@/lib/types";
+import { specsOf } from "@/lib/specs";
 import { cardOf } from "@/lib/view";
 import { Breadcrumbs } from "./Breadcrumbs";
 import { BreakdownCard } from "./BreakdownCard";
 import { Gallery } from "./Gallery";
 import { MapCard } from "./MapCard";
 import { PriceCard } from "./PriceCard";
-import { SellerAssessmentCard } from "./SellerAssessmentCard";
 import { SellerText } from "./SellerText";
 import { SimilarListings } from "./SimilarListings";
 import { SpecsGrid } from "./SpecsGrid";
 import { SummaryCard } from "./SummaryCard";
 import styles from "./ListingScreen.module.css";

-const SIMILAR_COUNT = 3;
-const TOMAN_PER_MILLION = 1e6;
-
-function similarTo(listing: Listing): Listing[] {
-  return LISTINGS.filter((x) => x.modelId === listing.modelId && x.id !== listing.id)
-    .sort((a, b) => Math.abs(a.price - listing.price) - Math.abs(b.price - listing.price))
-    .slice(0, SIMILAR_COUNT);
-}
-
-function specsOf(l: Listing): { k: string; v: string }[] {
-  return [
-    ["برند و مدل", l.modelName], ["سال ساخت", fa(l.year)], ["کارکرد", `${num(l.km)} کیلومتر`], ["رنگ", l.color], ["گیربکس", l.gear], ["نوع سوخت", "بنزین"],
-    ["وضعیت بدنه", l.body.name], ["قیمت پایه (فروشنده)", `${num(l.price * TOMAN_PER_MILLION)} تومان`], ["مهلت بیمهٔ شخص ثالث", `${fa(l.ins)} ماه`], ["محل", `${l.city}، ${l.district}`], ["منبع", "دیوار"],
-  ].map(([k, v]) => ({ k, v }));
-}
-
-export function ListingScreen({ listingId }: { listingId: string }) {
-  const listing = useMemo(() => findListing(listingId), [listingId]);
-  const mapListings = useMemo(() => (listing ? [listing] : []), [listing]);
-  if (!listing) throw new Error(`Listing ${listingId} not found`); // page.tsx already 404s unknown ids
+const NO_ESTIMATE = "بدون تخمین";

-  const card = cardOf(listing);
-  const modelHref = `/model/${listing.modelId}`;
-  const cityQuery = `${listing.modelName} ${listing.city}`;
+export function ListingScreen({ detail, similar }: { detail: ListingDetail; similar: ListingCard[] }) {
+  const card = cardOf(detail);
+  const modelHref = detail.model ? `/model/${encodeURIComponent(detail.model)}` : "/results";
+  const modelLabel = detail.model ?? detail.title;
+  const cityQuery = `${modelLabel} ${detail.city}`;
+  const photos = detail.image_urls.length ? detail.image_urls : [card.img];

   return (
     <section className={styles.screen}>
-      <Breadcrumbs items={[{ label: "خانه", href: "/" }, { label: listing.modelName, href: modelHref }, { label: card.title }]} />
+      <Breadcrumbs items={[{ label: "خانه", href: "/" }, { label: modelLabel, href: modelHref }, { label: card.title }]} />
       <div className={styles.grid}>
         <div className={styles.mainCol}>
-          <Gallery key={listing.id} photos={listing.photos} title={card.title} />
-          <SummaryCard summary={summaryOf(listing)} tags={listing.tags} />
-          <SpecsGrid specs={specsOf(listing)} />
+          <Gallery key={detail.id} photos={photos} title={card.title} />
+          <SummaryCard summary={summaryOf(detail)} />
+          <SpecsGrid specs={specsOf(detail)} />
           <SellerText
-            desc={listing.desc}
+            desc={detail.description}
             links={[
-              { text: listing.modelName, href: modelHref },
-              { text: `${listing.modelName} در ${listing.city}`, href: `/results?q=${encodeURIComponent(cityQuery)}` },
+              { text: modelLabel, href: modelHref },
+              { text: `${modelLabel} در ${detail.city}`, href: `/results?q=${encodeURIComponent(cityQuery)}` },
             ]}
           />
-          <MapCard title="محل خودرو" hint={`${listing.city}، ${listing.district} · محدودهٔ تقریبی`} listings={mapListings} single />
+          {detail.lat !== null && (
+            <MapCard title="محل خودرو" hint={`${detail.district ? `${detail.city}، ${detail.district}` : detail.city} · محدودهٔ تقریبی`} listings={[detail]} single />
+          )}
         </div>
         <div className={styles.sideCol}>
-          <PriceCard listing={listing} card={card} />
-          <SellerAssessmentCard assess={listing.assess} />
-          <BreakdownCard verdict={card.verdict} diffText={card.diffText} rows={breakdownRows(listing)} estFa={num(listing.est)} priceFa={card.priceFa} note={verdictNote(listing)} />
-          <SimilarListings title="آگهی‌های مشابه" cards={similarTo(listing).map(cardOf)} />
+          <PriceCard detail={detail} card={card} />
+          <BreakdownCard verdict={card.verdict} diffText={card.diffText} rows={breakdownRows(detail)} estText={detail.est_price === null ? NO_ESTIMATE : formatToman(detail.est_price)} priceText={card.priceText} note={verdictNote(detail)} />
+          <SimilarListings title="آگهی‌های مشابه" cards={similar.map((l) => cardOf(l))} />
         </div>
       </div>
     </section>
````

Modify `frontend/src/components/PriceCard.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/PriceCard.tsx b/frontend/src/components/PriceCard.tsx
index 9e181da..8316b7b 100644
--- a/frontend/src/components/PriceCard.tsx
+++ b/frontend/src/components/PriceCard.tsx
@@ -1,39 +1,39 @@
 "use client";

+import type { ListingDetail } from "@/lib/api/types";
 import { fa, num } from "@/lib/format";
-import type { Listing } from "@/lib/types";
 import type { CardView } from "@/lib/view";
 import { useAppState } from "@/state/AppState";
 import { Icon } from "./Icon";
 import styles from "./PriceCard.module.css";

-export function PriceCard({ listing, card }: { listing: Listing; card: CardView }) {
+export function PriceCard({ detail, card }: { detail: ListingDetail; card: CardView }) {
   const { compare, saved, toggleCompare, toggleSaved } = useAppState();
-  const inCompare = compare.includes(listing.id);
-  const isSaved = saved.includes(listing.id);
+  const inCompare = compare.includes(detail.id);
+  const isSaved = saved.includes(detail.id);
   const quick = [
-    { k: "کارکرد", v: num(listing.km) },
-    { k: "مدل (سال تولید)", v: fa(listing.year) },
-    { k: "رنگ", v: listing.color },
+    { k: "کارکرد", v: detail.km === null ? "—" : num(detail.km) },
+    { k: "مدل (سال تولید)", v: detail.year === null ? "—" : fa(detail.year) },
+    { k: "رنگ", v: detail.color ?? "—" },
   ];

   return (
     <div className={styles.card}>
       <div className={styles.headRow}>
         <h1 className={styles.title}>{card.title}</h1>
-        <span className={styles.posted}>{card.posted}</span>
+        <span className={styles.posted} suppressHydrationWarning>{card.posted}</span>
       </div>
       <div className={styles.meta}>{card.meta}</div>
       <div className={styles.price}>
-        {card.priceFa} <span className={styles.unit}>میلیون تومان</span>
+        {card.priceText}{detail.price !== null && <span className={styles.unit}> تومان</span>}
       </div>
       <div className={styles.actions}>
-        <a href={`https://divar.ir/v/-/${listing.token}`} target="_blank" rel="noopener" className={styles.divar}>
+        <a href={detail.url} target="_blank" rel="noopener" className={styles.divar}>
           مشاهده در دیوار
         </a>
         <button
           type="button"
-          onClick={() => toggleCompare(listing.id)}
+          onClick={() => toggleCompare(detail.id)}
           className={styles.compare}
           style={{
             borderColor: inCompare ? "var(--red)" : "var(--line)",
@@ -43,7 +43,7 @@ export function PriceCard({ listing, card }: { listing: Listing; card: CardView
         >
           {inCompare ? "✓ در مقایسه" : "+ مقایسه"}
         </button>
-        <button type="button" onClick={() => toggleSaved(listing.id)} title="نشان‌کردن" aria-pressed={isSaved} className={styles.bookmark}>
+        <button type="button" onClick={() => toggleSaved(detail.id)} title="نشان‌کردن" aria-pressed={isSaved} className={styles.bookmark}>
           <Icon name="bookmark" size={18} stroke="var(--ink)" fill={isSaved ? "#172033" : "none"} />
         </button>
       </div>
````

Delete `frontend/src/components/SellerAssessmentCard.module.css`: `git rm frontend/src/components/SellerAssessmentCard.module.css`

Delete `frontend/src/components/SellerAssessmentCard.tsx`: `git rm frontend/src/components/SellerAssessmentCard.tsx`

Modify `frontend/src/components/SummaryCard.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/SummaryCard.tsx b/frontend/src/components/SummaryCard.tsx
index 397a97f..fe5d0e3 100644
--- a/frontend/src/components/SummaryCard.tsx
+++ b/frontend/src/components/SummaryCard.tsx
@@ -1,26 +1,15 @@
-import { isNegativeIssue } from "@/lib/catalog";
 import { Icon } from "./Icon";
 import styles from "./SummaryCard.module.css";

-export function SummaryCard({ summary, tags }: { summary: string; tags: string[] }) {
+export function SummaryCard({ summary }: { summary: string }) {
   return (
     <div className={styles.card}>
       <div className={styles.head}>
         <Icon name="sparkles" size={18} stroke="var(--red)" />
         <span className={styles.title}>خلاصهٔ وضعیت خودرو</span>
-        <span className={styles.hint}>از متن آگهی و مشخصات</span>
+        <span className={styles.hint}>از مشخصات و تخمین قیمت</span>
       </div>
       <p className={styles.summary}>{summary}</p>
-      <div className={styles.tags}>
-        {tags.map((tag) => {
-          const neg = isNegativeIssue(tag);
-          return (
-            <span key={tag} className={styles.tag} style={{ background: neg ? "var(--red-soft)" : "var(--green-soft)", color: neg ? "var(--red-ink)" : "var(--green)" }}>
-              {tag}
-            </span>
-          );
-        })}
-      </div>
     </div>
   );
 }
````

- [ ] **Step 2: Run the tests to verify they pass**

Run: `bun test`
Expected: `27 pass, 0 fail`; `tsc` red only in the 9 files above.

- [ ] **Step 3: Commit**

From the repo root (`cd ..`), stage explicit paths only (never `git add -A`):

````bash
git add 'frontend/src/app/listing/[id]/loading.tsx' 'frontend/src/app/listing/[id]/page.tsx' frontend/src/components/ListingScreen.tsx frontend/src/components/PriceCard.tsx frontend/src/components/SellerAssessmentCard.module.css frontend/src/components/SellerAssessmentCard.tsx frontend/src/components/SummaryCard.tsx
git commit -m "feat(frontend): render the listing page from the API

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git log -1 --format='%(trailers)'   # must print exactly: Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
````

---

### Task 11: Model page (server, dynamic) with trim bars

**Files:**
- Delete: `frontend/src/app/model/[id]/page.tsx`
- Create: `frontend/src/app/model/[model]/loading.tsx`
- Create: `frontend/src/app/model/[model]/page.tsx`
- Delete: `frontend/src/components/IssueBars.tsx`
- Modify: `frontend/src/components/ModelScreen.tsx`
- Modify: `frontend/src/components/PriceHistogram.tsx`
- Rename: `frontend/src/components/IssueBars.module.css` → `frontend/src/components/TrimBars.module.css`
- Create: `frontend/src/components/TrimBars.tsx`

**Interfaces:**
- Consumes: `apiGet<ModelStats>` (`/models/{encodeURIComponent(model)}/stats`), `cardOf`, `formatToman`, `useAppState().addAlert`.
- Produces: route `app/model/[model]/` (replaces `app/model/[id]/`; 404 → `notFound()`), `loading.tsx`; `ModelScreen({ stats })` (client; alert threshold = 90 % of `price_median` rounded to 10 M, `ALERT_FRACTION_OF_MEDIAN`); `PriceHistogram({ buckets, median })`; `TrimBars({ trims, total })` (replaces `IssueBars`, keeps its stylesheet as `TrimBars.module.css`); map from `top_deals`.

Spec §5 (`/model/[model]`), decision "Issue bars → per-trim bars". Links to the model page are built with `encodeURIComponent(model)` everywhere (`ModelCard`, breadcrumbs, `ListingScreen`); the page decodes and re-encodes before calling the API. **`tsc` still red in:** `src/app/compare/page.tsx`, `src/app/estimate/page.tsx`, `src/components/{CompareTable,EstimateForm,EstimateResultCard}.tsx` — 5 files.

- [ ] **Step 1: Implement**

Delete `frontend/src/app/model/[id]/page.tsx`: `git rm 'frontend/src/app/model/[id]/page.tsx'`

Create `frontend/src/app/model/[model]/loading.tsx`:

````tsx
import { Skeleton } from "@/components/Skeleton";

export default function Loading() {
  return (
    <section style={{ padding: "20px 0" }}>
      <Skeleton lines={[20, 48, 220, 320]} />
    </section>
  );
}
````

Create `frontend/src/app/model/[model]/page.tsx`:

````tsx
import { notFound } from "next/navigation";
import { ModelScreen } from "@/components/ModelScreen";
import { ApiError, apiGet } from "@/lib/api/client";
import type { ModelStats } from "@/lib/api/types";

// Rendered on request (no generateStaticParams); `model` is the URL-encoded model name.
export default async function ModelPage({ params }: { params: Promise<{ model: string }> }) {
  const { model } = await params;
  let stats: ModelStats;
  try {
    stats = await apiGet<ModelStats>(`/models/${encodeURIComponent(decodeURIComponent(model))}/stats`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error; // → app/error.tsx
  }
  return <ModelScreen stats={stats} />;
}
````

Delete `frontend/src/components/IssueBars.tsx`: `git rm frontend/src/components/IssueBars.tsx`

Modify `frontend/src/components/ModelScreen.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/ModelScreen.tsx b/frontend/src/components/ModelScreen.tsx
index b39ed5e..b50888a 100644
--- a/frontend/src/components/ModelScreen.tsx
+++ b/frontend/src/components/ModelScreen.tsx
@@ -1,62 +1,61 @@
 "use client";

-import { useMemo } from "react";
-import { num } from "@/lib/format";
-import { LISTINGS } from "@/lib/listings";
-import { modelStats } from "@/lib/modelStats";
-import { alertMatches } from "@/lib/search";
+import type { ModelStats } from "@/lib/api/types";
+import { fa, formatToman } from "@/lib/format";
 import { cardOf } from "@/lib/view";
 import { useAppState } from "@/state/AppState";
 import { Breadcrumbs } from "./Breadcrumbs";
 import { Icon } from "./Icon";
-import { IssueBars } from "./IssueBars";
 import { ListingRow } from "./ListingRow";
 import { MapCard } from "./MapCard";
 import { PriceHistogram } from "./PriceHistogram";
+import { TrimBars } from "./TrimBars";
 import styles from "./ModelScreen.module.css";

-export function ModelScreen({ modelId }: { modelId: string }) {
+export const ALERT_FRACTION_OF_MEDIAN = 0.9;
+const ALERT_ROUNDING = 10_000_000;
+
+export function ModelScreen({ stats }: { stats: ModelStats }) {
   const { addAlert } = useAppState();
-  const stats = useMemo(() => modelStats(modelId, LISTINGS), [modelId]);
-  const saveAlert = () =>
-    addAlert({
-      title: stats.model.name,
-      threshold: stats.alertThreshold,
-      matches: alertMatches(stats.listings, stats.alertThreshold),
-    });
+  const threshold = stats.price_median === null ? null : Math.round((stats.price_median * ALERT_FRACTION_OF_MEDIAN) / ALERT_ROUNDING) * ALERT_ROUNDING;
+  const saveAlert = () => threshold && addAlert({ title: stats.model, params: { models: [stats.model], category: stats.category }, threshold });
+  const years = stats.year_min === null || stats.year_max === null ? "نامشخص" : `${fa(stats.year_min)} تا ${fa(stats.year_max)}`;

   return (
     <section className={styles.screen}>
-      <Breadcrumbs items={[{ label: "خانه", href: "/" }, { label: "جست‌وجو", href: "/results" }, { label: stats.model.name }]} />
+      <Breadcrumbs items={[{ label: "خانه", href: "/" }, { label: "جست‌وجو", href: `/results?category=${stats.category}` }, { label: stats.model }]} />
       <div className={styles.head}>
         <div>
-          <h1 className={styles.name}>{stats.model.name}</h1>
+          <h1 className={styles.name}>{stats.model}</h1>
           <div className={styles.sub}>
-            {stats.countFa} آگهی فعال · سال‌های {stats.yearRange} · میانهٔ قیمت <b>{num(stats.median)}</b> میلیون
+            {fa(stats.count)} آگهی فعال · سال‌های {years} · میانهٔ قیمت <b>{stats.price_median === null ? "—" : formatToman(stats.price_median)}</b>
           </div>
         </div>
-        <button className={styles.alert} onClick={saveAlert}>
-          <Icon name="bell" size={16} />
-          هشدار قیمت زیر {num(stats.alertThreshold)} میلیون
-        </button>
+        {threshold !== null && (
+          <button className={styles.alert} onClick={saveAlert}>
+            <Icon name="bell" size={16} />
+            هشدار قیمت زیر {formatToman(threshold)}
+          </button>
+        )}
       </div>
       <div className={styles.topGrid}>
-        <PriceHistogram buckets={stats.buckets} minFa={num(stats.min)} maxFa={num(stats.max)} />
-        <IssueBars issues={stats.issues} />
+        <PriceHistogram buckets={stats.histogram} median={stats.price_median} />
+        <TrimBars trims={stats.trims} total={stats.count} />
       </div>
       <div className={styles.bottomGrid}>
         <div>
           <div className={styles.listHead}>
-            <h2>آگهی‌ها به ترتیب ارزش خرید</h2>
+            <h2>بهترین آگهی‌ها به ترتیب ارزش خرید</h2>
             <span>قیمت نسبت به بازار + کارکرد + بدنه</span>
           </div>
           <div className={styles.rows}>
-            {stats.listings.map((l) => (
-              <ListingRow key={l.id} card={cardOf(l)} />
-            ))}
+            {stats.top_deals.map((l) => <ListingRow key={l.id} card={cardOf(l)} />)}
+            {stats.top_deals.length === 0 && <div className={styles.sub}>برای این مدل هنوز تخمین قیمتی نداریم.</div>}
           </div>
         </div>
-        <MapCard sticky title="آگهی‌ها روی نقشه" hint="رنگ نقطه = قیمت نسبت به بازار · کلیک = آگهی" listings={stats.listings} />
+        {stats.top_deals.some((l) => l.lat !== null) && (
+          <MapCard sticky title="آگهی‌ها روی نقشه" hint="رنگ نقطه = قیمت نسبت به بازار · کلیک = آگهی" listings={stats.top_deals} />
+        )}
       </div>
     </section>
   );
````

Modify `frontend/src/components/PriceHistogram.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/PriceHistogram.tsx b/frontend/src/components/PriceHistogram.tsx
index ba17f63..e1eb7d6 100644
--- a/frontend/src/components/PriceHistogram.tsx
+++ b/frontend/src/components/PriceHistogram.tsx
@@ -1,25 +1,31 @@
-import type { HistogramBucket } from "@/lib/modelStats";
+import type { HistogramBucket } from "@/lib/api/types";
+import { fa, formatToman } from "@/lib/format";
 import styles from "./PriceHistogram.module.css";

-export function PriceHistogram({ buckets, minFa, maxFa }: { buckets: HistogramBucket[]; minFa: string; maxFa: string }) {
+const MAX_BAR_HEIGHT_PCT = 90;
+const MIN_BAR_HEIGHT_PCT = 4;
+
+export function PriceHistogram({ buckets, median }: { buckets: HistogramBucket[]; median: number | null }) {
+  const tallest = Math.max(1, ...buckets.map((b) => b.count));
+  const medianIndex = median === null ? -1 : buckets.findIndex((b, i) => median >= b.low && (median < b.high || i === buckets.length - 1));
   return (
     <div className={styles.card}>
       <div className={styles.head}>
         <span className={styles.title}>پراکندگی قیمت آگهی‌ها</span>
-        <span className={styles.unit}>میلیون تومان</span>
+        <span className={styles.unit}>تومان</span>
       </div>
       <div className={styles.hint}>هر ستون تعداد آگهی در آن بازهٔ قیمتی است؛ ستون پررنگ میانهٔ بازار.</div>
       <div className={styles.bars}>
         {buckets.map((bucket, i) => (
-          <div key={i} className={styles.bucket} title={bucket.tip}>
-            <span className={styles.count}>{bucket.countFa}</span>
-            <div className={styles.bar} style={{ height: `${bucket.heightPct}%`, background: bucket.isMedian ? "var(--red)" : "var(--line)" }} />
+          <div key={i} className={styles.bucket} title={`${formatToman(bucket.low)} تا ${formatToman(bucket.high)}`}>
+            <span className={styles.count}>{bucket.count ? fa(bucket.count) : ""}</span>
+            <div className={styles.bar} style={{ height: `${Math.max(MIN_BAR_HEIGHT_PCT, (bucket.count / tallest) * MAX_BAR_HEIGHT_PCT)}%`, background: i === medianIndex ? "var(--red)" : "var(--line)" }} />
           </div>
         ))}
       </div>
       <div className={styles.range}>
-        <span>{minFa}</span>
-        <span>{maxFa}</span>
+        <span>{buckets.length ? formatToman(buckets[0].low) : ""}</span>
+        <span>{buckets.length ? formatToman(buckets[buckets.length - 1].high) : ""}</span>
       </div>
     </div>
   );
````

Rename `frontend/src/components/IssueBars.module.css` → `frontend/src/components/TrimBars.module.css`: `git mv frontend/src/components/IssueBars.module.css frontend/src/components/TrimBars.module.css`

Create `frontend/src/components/TrimBars.tsx`:

````tsx
import type { TrimStat } from "@/lib/api/types";
import { fa, formatToman } from "@/lib/format";
import styles from "./TrimBars.module.css";

const MAX_TRIMS = 6;

/** Share of the model's listings per trim, with each trim's median price. */
export function TrimBars({ trims, total }: { trims: TrimStat[]; total: number }) {
  return (
    <div className={styles.card}>
      <div className={styles.title}>تیپ‌های این مدل</div>
      <div className={styles.hint}>سهم هر تیپ از آگهی‌ها و میانهٔ قیمت آن</div>
      <div className={styles.list}>
        {trims.slice(0, MAX_TRIMS).map((trim) => {
          const pct = total ? Math.round((trim.count / total) * 100) : 0;
          return (
            <div key={trim.trim} className={styles.row}>
              <span className={styles.name} title={trim.trim}>{trim.trim}</span>
              <div className={styles.track}>
                <div className={styles.fill} style={{ width: `${pct}%`, background: "var(--red)" }} />
              </div>
              <span className={styles.pct}>{fa(pct)}٪ · {trim.price_median === null ? "—" : formatToman(trim.price_median)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
````

- [ ] **Step 2: Run the tests to verify they pass**

Run: `bun test`
Expected: `27 pass, 0 fail`; `tsc` red only in the 5 files above.

- [ ] **Step 3: Commit**

From the repo root (`cd ..`), stage explicit paths only (never `git add -A`):

````bash
git add 'frontend/src/app/model/[id]/page.tsx' 'frontend/src/app/model/[model]/loading.tsx' 'frontend/src/app/model/[model]/page.tsx' frontend/src/components/IssueBars.module.css frontend/src/components/IssueBars.tsx frontend/src/components/ModelScreen.tsx frontend/src/components/PriceHistogram.tsx frontend/src/components/TrimBars.module.css frontend/src/components/TrimBars.tsx
git commit -m "feat(frontend): render the model page from /models/{model}/stats

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git log -1 --format='%(trailers)'   # must print exactly: Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
````

---

### Task 12: Compare and estimate pages — tsc and lint back to zero

**Files:**
- Modify: `frontend/src/app/compare/page.tsx`
- Modify: `frontend/src/app/estimate/page.module.css`
- Modify: `frontend/src/app/estimate/page.tsx`
- Modify: `frontend/src/components/CompareTable.tsx`
- Modify: `frontend/src/components/EstimateForm.module.css`
- Modify: `frontend/src/components/EstimateForm.tsx`
- Modify: `frontend/src/components/EstimateResultCard.tsx`

**Interfaces:**
- Consumes: `apiGet<ListingCard[]>` (`/listings?ids=`), `apiGet<CatalogSuggestion[]>` (`/catalog/suggest`), `apiGet<ModelStats>` (year range), `apiPost<EstimateResponse>` (`/estimates`), `useApi`, `compareRows`, `estimateBreakdownRows`, `diffText`, `verdictStyle`, `BODY_CONDITION_CATEGORIES`.
- Produces: `app/compare/page.tsx` (ids from `useAppState().compare` → one `/listings?ids=` call; loading/error/empty states); `CompareTable({ cards, onRemove })`; `app/estimate/page.tsx` + `EstimateForm({ input, onChange, onSubmit, canSubmit, busy })` (`EstimateInput { category, trim, year, kmThousands, insuranceMonths, bodyCondition, asking }`; trim type-ahead via suggest, year select from the model's stats range, body condition only for motorcycle/heavy, optional asking price in millions) ; `EstimateResultCard({ result, title, year })`.

Spec §5 (`/compare`, `/estimate`), §6.2. A 422 from `/estimates` (`no_comparables`, `invalid_search`, `validation_error`) shows the envelope message inline and the form stays editable; the submit happens in a click handler, not an effect. **This task ends the red window:** `bunx tsc --noEmit` and `bun run lint` must be clean, and `grep -rE "LISTINGS|generateListings|MODELS\b" src` must print nothing.

- [ ] **Step 1: Implement**

Modify `frontend/src/app/compare/page.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/app/compare/page.tsx b/frontend/src/app/compare/page.tsx
index 9d4b38e..323bd9a 100644
--- a/frontend/src/app/compare/page.tsx
+++ b/frontend/src/app/compare/page.tsx
@@ -1,28 +1,33 @@
 "use client";
 import Link from "next/link";
 import { CompareTable } from "@/components/CompareTable";
-import { findListing } from "@/lib/listings";
-import type { Listing } from "@/lib/types";
+import { ErrorBanner } from "@/components/ErrorBanner";
+import { Skeleton } from "@/components/Skeleton";
+import { apiGet } from "@/lib/api/client";
+import type { ListingCard } from "@/lib/api/types";
+import { useApi } from "@/lib/api/useApi";
 import { useAppState } from "@/state/AppState";
 import styles from "./page.module.css";

 export default function ComparePage() {
   const { compare, removeFromCompare } = useAppState();
-  const cars = compare.map(findListing).filter((l): l is Listing => l !== undefined);
+  const cards = useApi(compare.length ? `compare:${compare.join(",")}` : null, (signal) => apiGet<ListingCard[]>("/listings", { ids: compare }, signal));
   return (
     <section className={styles.screen}>
       <h1 className={styles.title}>مقایسه</h1>
       <p className={styles.lead}>تا سه خودرو رو از صفحهٔ آگهی به مقایسه اضافه کن.</p>
-      {cars.length === 0 ? (
+      {compare.length === 0 && (
         <div className={styles.empty}>
           هنوز چیزی برای مقایسه انتخاب نکردی.
           <div>
             <Link href="/results" className={styles.cta}>برو به آگهی‌ها</Link>
           </div>
         </div>
-      ) : (
-        <CompareTable cars={cars} onRemove={removeFromCompare} />
       )}
+      {cards.loading && <Skeleton lines={[120, 40, 40, 40]} />}
+      {cards.error && <ErrorBanner error={cards.error} onRetry={cards.retry} />}
+      {cards.data && cards.data.length > 0 && <CompareTable cards={cards.data} onRemove={removeFromCompare} />}
+      {cards.data && cards.data.length === 0 && <div className={styles.empty}>این آگهی‌ها دیگر فعال نیستند.</div>}
     </section>
   );
 }
````

Modify `frontend/src/app/estimate/page.module.css` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/app/estimate/page.module.css b/frontend/src/app/estimate/page.module.css
index 8a39d88..23eb215 100644
--- a/frontend/src/app/estimate/page.module.css
+++ b/frontend/src/app/estimate/page.module.css
@@ -18,3 +18,4 @@
     gap: 14px;
   }
 }
+.empty { padding: 24px; border: 1px dashed var(--line-strong); border-radius: 12px; color: var(--muted); font-size: 13px; text-align: center; }
````

Modify `frontend/src/app/estimate/page.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/app/estimate/page.tsx b/frontend/src/app/estimate/page.tsx
index 336bdf0..b5441b5 100644
--- a/frontend/src/app/estimate/page.tsx
+++ b/frontend/src/app/estimate/page.tsx
@@ -1,26 +1,61 @@
 "use client";
-import { useMemo, useState } from "react";
+import { useState } from "react";
 import { BreakdownList } from "@/components/BreakdownList";
-import { EstimateForm } from "@/components/EstimateForm";
+import { ErrorBanner } from "@/components/ErrorBanner";
+import { EstimateForm, type EstimateInput } from "@/components/EstimateForm";
 import { EstimateResultCard } from "@/components/EstimateResultCard";
 import { SimilarListings } from "@/components/SimilarListings";
-import { estimate, type EstimateInput } from "@/lib/estimate";
-import { LISTINGS } from "@/lib/listings";
+import { ApiError, apiPost } from "@/lib/api/client";
+import type { EstimateRequest, EstimateResponse } from "@/lib/api/types";
+import { en } from "@/lib/format";
+import { estimateBreakdownRows } from "@/lib/pricing";
 import { cardOf } from "@/lib/view";
 import styles from "./page.module.css";

-const INITIAL: EstimateInput = { modelId: "206", year: 1401, kmThousands: 80, bodyIndex: 0, gear: "دنده‌ای", asking: "" };
+const INITIAL: EstimateInput = { category: "light", trim: null, year: null, kmThousands: 80, insuranceMonths: 6, bodyCondition: null, asking: "" };
+const TOMAN_PER_MILLION = 1_000_000;
+const KM_PER_THOUSAND = 1_000;
+
+function toRequest(input: EstimateInput): EstimateRequest | null {
+  if (!input.trim || input.year === null) return null;
+  const asking = Number.parseFloat(en(input.asking));
+  return {
+    category: input.category, trim: input.trim, year: input.year, km: input.kmThousands * KM_PER_THOUSAND,
+    insurance_months: input.insuranceMonths, body_condition: input.bodyCondition,
+    asking_price: Number.isFinite(asking) && asking > 0 ? Math.round(asking * TOMAN_PER_MILLION) : null,
+  };
+}

 export default function EstimatePage() {
   const [input, setInput] = useState<EstimateInput>(INITIAL);
-  const result = useMemo(() => estimate(input, LISTINGS), [input]);
+  const [result, setResult] = useState<EstimateResponse | null>(null);
+  const [error, setError] = useState<ApiError | null>(null);
+  const [busy, setBusy] = useState(false);
+  const request = toRequest(input);
+
+  async function submit() {
+    if (!request || busy) return;
+    setBusy(true);
+    setError(null);
+    try {
+      setResult(await apiPost<EstimateResponse>("/estimates", request));
+    } catch (failure) {
+      // 422 (no comparables / unknown trim) shows the backend's message inline; the form stays editable.
+      setError(failure instanceof ApiError ? failure : new ApiError(0, "network_error", "network failure"));
+    } finally {
+      setBusy(false);
+    }
+  }
+
   return (
     <section className={styles.grid}>
-      <EstimateForm input={input} result={result} onChange={(patch) => setInput((i) => ({ ...i, ...patch }))} />
+      <EstimateForm input={input} onChange={(patch) => setInput((i) => ({ ...i, ...patch }))} onSubmit={submit} canSubmit={request !== null && !busy} busy={busy} />
       <div className={styles.results}>
-        <EstimateResultCard result={result} />
-        <BreakdownList title="چطور حساب شد؟" rows={result.breakdown} />
-        <SimilarListings title="آگهی‌های مشابه الان در بازار" cards={result.similar.map(cardOf)} />
+        {error && <ErrorBanner error={error} onRetry={submit} />}
+        {result && <EstimateResultCard result={result} title={input.trim ?? ""} year={input.year} />}
+        {result && <BreakdownList title="چطور حساب شد؟" rows={estimateBreakdownRows(result, request)} />}
+        {result && <SimilarListings title="آگهی‌های مشابه الان در بازار" cards={result.similar.map((l) => cardOf(l))} />}
+        {!result && !error && <div className={styles.empty}>مدل، سال و کارکرد رو بده تا با آگهی‌های فعال همان تیپ مقایسه کنیم.</div>}
       </div>
     </section>
   );
````

Modify `frontend/src/components/CompareTable.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/CompareTable.tsx b/frontend/src/components/CompareTable.tsx
index bcf4772..14f4001 100644
--- a/frontend/src/components/CompareTable.tsx
+++ b/frontend/src/components/CompareTable.tsx
@@ -1,28 +1,28 @@
 import type { CSSProperties } from "react";
 import Link from "next/link";
+import type { ListingCard } from "@/lib/api/types";
 import { compareRows } from "@/lib/compare";
-import type { Listing } from "@/lib/types";
 import { cardOf } from "@/lib/view";
 import styles from "./CompareTable.module.css";

-interface Props { cars: Listing[]; onRemove(id: string): void; }
+interface Props { cards: ListingCard[]; onRemove(id: string): void; }

-export function CompareTable({ cars, onRemove }: Props) {
-  const rows = compareRows(cars);
-  const wrapStyle = { "--cols": cars.length } as CSSProperties;
+export function CompareTable({ cards, onRemove }: Props) {
+  const rows = compareRows(cards);
+  const wrapStyle = { "--cols": cards.length } as CSSProperties;
   return (
     <div className={styles.wrap} style={wrapStyle}>
       <div className={styles.table}>
         <div className={styles.headRow}>
           <div className={styles.feature}>ویژگی</div>
-          {cars.map((car) => {
-            const card = cardOf(car);
+          {cards.map((listing) => {
+            const card = cardOf(listing);
             return (
-              <div key={car.id} className={styles.carCell}>
+              <div key={listing.id} className={styles.carCell}>
                 <div role="img" aria-label={card.title} className={styles.photo} style={{ backgroundImage: `url(${card.img})` }} />
                 <Link href={card.href} className={styles.title}>{card.title}</Link>
                 <div className={styles.meta}>{card.meta}</div>
-                <button onClick={() => onRemove(car.id)} className={styles.remove} aria-label="حذف از مقایسه">×</button>
+                <button onClick={() => onRemove(listing.id)} className={styles.remove} aria-label="حذف از مقایسه">×</button>
               </div>
             );
           })}
@@ -31,7 +31,7 @@ export function CompareTable({ cars, onRemove }: Props) {
           <div key={row.label} className={styles.row}>
             <div className={styles.label}>{row.label}</div>
             {row.cells.map((cell, index) => (
-              <div key={cars[index].id} className={styles.cell} style={{ color: cell.color, background: cell.best ? "var(--green-soft)" : "transparent" }}>
+              <div key={cards[index].id} className={styles.cell} style={{ color: cell.color, background: cell.best ? "var(--green-soft)" : "transparent" }}>
                 {cell.text}
               </div>
             ))}
````

Modify `frontend/src/components/EstimateForm.module.css` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/EstimateForm.module.css b/frontend/src/components/EstimateForm.module.css
index 37d2215..9893688 100644
--- a/frontend/src/components/EstimateForm.module.css
+++ b/frontend/src/components/EstimateForm.module.css
@@ -100,3 +100,9 @@
 .askingRow span {
   font-size: 13px;
 }
+.suggestions { list-style: none; margin: 6px 0 0; padding: 0; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); max-height: 240px; overflow: auto; }
+.suggestion { display: flex; justify-content: space-between; width: 100%; padding: 8px 10px; border: 0; background: none; font: inherit; font-size: 13px; color: var(--ink); text-align: start; cursor: pointer; }
+.suggestion:hover { background: var(--fill); }
+.count, .hint { font-size: 11px; color: var(--muted); }
+.submit { margin-top: 4px; padding: 12px; border: 0; border-radius: 12px; background: var(--red); color: #fff; font: inherit; font-weight: 700; cursor: pointer; }
+.submit:disabled { opacity: .5; cursor: default; }
````

Modify `frontend/src/components/EstimateForm.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/EstimateForm.tsx b/frontend/src/components/EstimateForm.tsx
index dff3396..20f7a3d 100644
--- a/frontend/src/components/EstimateForm.tsx
+++ b/frontend/src/components/EstimateForm.tsx
@@ -1,31 +1,71 @@
 "use client";
-import { BODIES, MODELS } from "@/lib/catalog";
-import type { EstimateInput, EstimateResult } from "@/lib/estimate";
+import { useState } from "react";
+import { apiGet } from "@/lib/api/client";
+import type { BodyCondition, CatalogSuggestion, Category, ModelStats } from "@/lib/api/types";
+import { useApi } from "@/lib/api/useApi";
 import { fa } from "@/lib/format";
+import { BODY_CONDITION_CATEGORIES, BODY_NAMES, CATEGORY_NAMES } from "@/lib/labels";
 import styles from "./EstimateForm.module.css";

-interface Props { input: EstimateInput; result: EstimateResult; onChange(patch: Partial<EstimateInput>): void; }
+export interface EstimateInput {
+  category: Category; trim: string | null; year: number | null; kmThousands: number; insuranceMonths: number;
+  bodyCondition: BodyCondition | null; asking: string;
+}
+
+interface Props { input: EstimateInput; onChange(patch: Partial<EstimateInput>): void; onSubmit(): void; canSubmit: boolean; busy: boolean; }
+
+const ESTIMATED_CATEGORIES: Category[] = ["light", "motorcycle"];
+const BODY_CONDITIONS = Object.keys(BODY_NAMES) as BodyCondition[];
+const MAX_INSURANCE_MONTHS = 12;
+const yearsBetween = (stats: ModelStats | null): number[] =>
+  stats && stats.year_min !== null && stats.year_max !== null ? Array.from({ length: stats.year_max - stats.year_min + 1 }, (_, i) => (stats.year_max as number) - i) : [];
+
+export function EstimateForm({ input, onChange, onSubmit, canSubmit, busy }: Props) {
+  const [typed, setTyped] = useState("");
+  const [model, setModel] = useState<string | null>(null);
+  // Type-ahead: every keystroke is a new key, so a stale response can never win.
+  const suggestions = useApi(input.trim ? null : `suggest:${input.category}:${typed}`, (signal) => apiGet<CatalogSuggestion[]>("/catalog/suggest", { q: typed, category: input.category }, signal));
+  // The year select spans the chosen model's real range.
+  const stats = useApi(model ? `stats:${model}` : null, (signal) => apiGet<ModelStats>(`/models/${encodeURIComponent(model as string)}/stats`, {}, signal));
+  const years = yearsBetween(stats.data);
+  const showBody = BODY_CONDITION_CATEGORIES.includes(input.category);
+
+  function pick(suggestion: CatalogSuggestion) {
+    setModel(suggestion.model);
+    setTyped(suggestion.trim);
+    onChange({ trim: suggestion.trim, year: null });
+  }
+  function clearTrim() { setModel(null); onChange({ trim: null, year: null }); }

-export function EstimateForm({ input, result, onChange }: Props) {
   return (
-    <div className={styles.card}>
+    <form className={styles.card} onSubmit={(event) => { event.preventDefault(); onSubmit(); }}>
       <h1 className={styles.title}>این قیمت منصفانه‌ست؟</h1>
-      <p className={styles.lead}>مشخصات ماشین رو بده؛ با آگهی‌های فعال همان مدل مقایسه می‌کنیم.</p>
+      <p className={styles.lead}>مشخصات ماشین رو بده؛ با آگهی‌های فعال همان تیپ مقایسه می‌کنیم.</p>
       <div className={styles.fields}>
         <label className={styles.field}>
-          مدل
-          <select className={styles.select} value={input.modelId} onChange={(event) => onChange({ modelId: event.target.value })}>
-            {MODELS.map((model) => (
-              <option key={model.id} value={model.id}>{model.name}</option>
-            ))}
+          دسته
+          <select className={styles.select} value={input.category} onChange={(event) => { clearTrim(); setTyped(""); onChange({ category: event.target.value as Category, bodyCondition: null }); }}>
+            {ESTIMATED_CATEGORIES.map((category) => <option key={category} value={category}>{CATEGORY_NAMES[category]}</option>)}
           </select>
         </label>
+        <label className={styles.field}>
+          برند و مدل
+          <input type="text" className={styles.asking} dir="rtl" value={typed} placeholder="مثلاً: پژو ۲۰۶" aria-label="برند و مدل"
+            onChange={(event) => { setTyped(event.target.value); if (input.trim) clearTrim(); }} />
+          {!input.trim && suggestions.data && suggestions.data.length > 0 && (
+            <ul className={styles.suggestions} role="listbox">
+              {suggestions.data.map((s) => (
+                <li key={s.trim}><button type="button" className={styles.suggestion} onClick={() => pick(s)}>{s.trim} <span className={styles.count}>{fa(s.count)} آگهی</span></button></li>
+              ))}
+            </ul>
+          )}
+          {!input.trim && suggestions.data && suggestions.data.length === 0 && typed && <span className={styles.hint}>مدلی با این نام نداریم.</span>}
+        </label>
         <label className={styles.field}>
           سال ساخت
-          <select className={styles.select} value={result.year} onChange={(event) => onChange({ year: Number(event.target.value) })}>
-            {result.years.map((year) => (
-              <option key={year} value={year}>{fa(year)}</option>
-            ))}
+          <select className={styles.select} value={input.year ?? ""} disabled={!years.length} onChange={(event) => onChange({ year: event.target.value ? Number(event.target.value) : null })}>
+            <option value="">{stats.loading ? "…" : input.trim ? "انتخاب کن" : "اول مدل رو انتخاب کن"}</option>
+            {years.map((year) => <option key={year} value={year}>{fa(year)}</option>)}
           </select>
         </label>
         <label className={styles.field}>
@@ -33,50 +73,33 @@ export function EstimateForm({ input, result, onChange }: Props) {
             کارکرد
             <b>{fa(input.kmThousands)} هزار کیلومتر</b>
           </span>
-          <input
-            type="range"
-            min={0}
-            max={300}
-            step={5}
-            value={input.kmThousands}
-            onChange={(event) => onChange({ kmThousands: Number(event.target.value) })}
-            className={styles.range}
-          />
+          <input type="range" min={0} max={300} step={5} value={input.kmThousands} onChange={(event) => onChange({ kmThousands: Number(event.target.value) })} className={styles.range} />
         </label>
         <label className={styles.field}>
-          وضعیت بدنه
-          <select className={styles.select} value={input.bodyIndex} onChange={(event) => onChange({ bodyIndex: Number(event.target.value) })}>
-            {BODIES.map((body, index) => (
-              <option key={body.name} value={index}>{body.name}</option>
-            ))}
-          </select>
-        </label>
-        <label className={styles.field}>
-          گیربکس
-          <div className={styles.gears}>
-            {result.model.gears.map((gear) => (
-              <button key={gear} type="button" className={styles.gear} data-on={gear === result.gear} onClick={() => onChange({ gear })}>
-                {gear}
-              </button>
-            ))}
-          </div>
+          <span className={styles.kmHead}>
+            بیمهٔ شخص ثالث
+            <b>{fa(input.insuranceMonths)} ماه</b>
+          </span>
+          <input type="range" min={0} max={MAX_INSURANCE_MONTHS} step={1} value={input.insuranceMonths} onChange={(event) => onChange({ insuranceMonths: Number(event.target.value) })} className={styles.range} />
         </label>
+        {showBody && (
+          <label className={styles.field}>
+            وضعیت بدنه
+            <select className={styles.select} value={input.bodyCondition ?? ""} onChange={(event) => onChange({ bodyCondition: (event.target.value || null) as BodyCondition | null })}>
+              <option value="">نامشخص</option>
+              {BODY_CONDITIONS.map((body) => <option key={body} value={body}>{BODY_NAMES[body]}</option>)}
+            </select>
+          </label>
+        )}
         <label className={styles.field}>
           قیمت پیشنهادی فروشنده (اختیاری)
           <div className={styles.askingRow}>
-            <input
-              type="text"
-              inputMode="numeric"
-              dir="ltr"
-              value={input.asking}
-              onChange={(event) => onChange({ asking: event.target.value })}
-              placeholder="مثلاً ۶۵۰"
-              className={styles.asking}
-            />
+            <input type="text" inputMode="numeric" dir="ltr" value={input.asking} onChange={(event) => onChange({ asking: event.target.value })} placeholder="مثلاً ۶۵۰" className={styles.asking} />
             <span>میلیون</span>
           </div>
         </label>
+        <button type="submit" className={styles.submit} disabled={!canSubmit}>{busy ? "در حال محاسبه…" : "تخمین بزن"}</button>
       </div>
-    </div>
+    </form>
   );
 }
````

Modify `frontend/src/components/EstimateResultCard.tsx` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/frontend/src/components/EstimateResultCard.tsx b/frontend/src/components/EstimateResultCard.tsx
index 4f36cb7..fa6be90 100644
--- a/frontend/src/components/EstimateResultCard.tsx
+++ b/frontend/src/components/EstimateResultCard.tsx
@@ -1,22 +1,23 @@
-import type { EstimateResult } from "@/lib/estimate";
-import { fa, num } from "@/lib/format";
+import type { EstimateResponse } from "@/lib/api/types";
+import { fa, formatToman } from "@/lib/format";
+import { diffText, verdictStyle } from "@/lib/pricing";
 import { VerdictBadge } from "./VerdictBadge";
 import styles from "./EstimateResultCard.module.css";

-export function EstimateResultCard({ result }: { result: EstimateResult }) {
+export function EstimateResultCard({ result, title, year }: { result: EstimateResponse; title: string; year: number | null }) {
   return (
     <div className={styles.card}>
-      <div className={styles.label}>تخمین ترب‌کار برای {result.title}</div>
+      <div className={styles.label}>تخمین ترب‌کار برای {title}{year === null ? "" : ` مدل ${fa(year)}`}</div>
       <div className={styles.est}>
-        {num(result.est)} <span className={styles.unit}>میلیون تومان</span>
+        {formatToman(result.est_price)} <span className={styles.unit}>تومان</span>
       </div>
       <div className={styles.range}>
-        بازهٔ منطقی: {num(result.low)} تا {num(result.high)} میلیون · بر اساس {fa(result.similarCount)} آگهی فعال
+        بازهٔ منطقی: {formatToman(result.low)} تا {formatToman(result.high)} · بر اساس {fa(result.est_sample_size)} آگهی فعال
       </div>
-      {result.asking && (
+      {result.asking_verdict && (
         <div className={styles.asking}>
-          <VerdictBadge verdict={result.asking.verdict} size="lg" />
-          <span className={styles.askingText}>{result.asking.text}</span>
+          <VerdictBadge verdict={verdictStyle(result.asking_verdict)} size="lg" />
+          <span className={styles.askingText}>{diffText(result.asking_diff_pct)}</span>
         </div>
       )}
     </div>
````

- [ ] **Step 2: Run the tests to verify they pass**

Run: `bun test && bunx tsc --noEmit && bun run lint && (grep -rnE "LISTINGS|generateListings|MODELS\b|SellerAssessment|IssueBars|NEXT_PUBLIC_API_URL" src || echo "no synthetic imports")`
Expected: `27 pass, 0 fail`, `tsc` prints nothing, ESLint prints nothing, the grep prints `no synthetic imports`. If a stale `.next/` from an earlier dev run makes `tsc` complain about `.next/types/validator.ts`, delete `frontend/.next` and rerun.

Then build once the way the Docker image does (from `frontend/`): `node node_modules/.bin/next build`
Expected: the route table shows `ƒ /`, `ƒ /listing/[id]`, `ƒ /model/[model]` (dynamic) and `○ /results`, `○ /compare`, `○ /estimate` (static shells); no "Error occurred prerendering page" line.

- [ ] **Step 3: Commit**

From the repo root (`cd ..`), stage explicit paths only (never `git add -A`):

````bash
git add frontend/src/app/compare/page.tsx frontend/src/app/estimate/page.module.css frontend/src/app/estimate/page.tsx frontend/src/components/CompareTable.tsx frontend/src/components/EstimateForm.module.css frontend/src/components/EstimateForm.tsx frontend/src/components/EstimateResultCard.tsx
git commit -m "feat(frontend): wire compare and estimate to the API

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git log -1 --format='%(trailers)'   # must print exactly: Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
````

---

### Task 13: Traefik routers, env, smoke script, docs and final verification

**Files:**
- Modify: `.docker/compose.yml`
- Modify: `.docker/frontend.Dockerfile`
- Create: `.scripts/smoke.sh`
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `example.env`

**Interfaces:**
- Consumes: everything above; the running stack for the smoke test.
- Produces: `.docker/compose.yml` router `api-assistant` (`/api/v1/assistant` and `/api/v1/estimates`, priority 100, middleware `assistant-ratelimit` average 5 / burst 10); `example.env` (`API_INTERNAL_URL`, `ASSISTANT_TIMEOUT_SECONDS`, no `NEXT_PUBLIC_API_URL`); `.docker/frontend.Dockerfile` without the `NEXT_PUBLIC_API_URL` build arg; `.scripts/smoke.sh` (agent-browser acceptance run; `BASE_URL`, `HEADED=1`, `QUERY`, `MODEL` env vars); README and CLAUDE.md updated.

Spec §3.5 (Traefik), §4.1 (env), §6.3 (acceptance), §6.4 (dev workflow), §7. **Unverified while planning:** the new Traefik router on the live stack (labels parse with `docker compose config`; the running stack was not restarted) and the smoke run through Traefik — Step 3 checks both. Make the script executable (`chmod +x .scripts/smoke.sh`). The repo has `graphify-out/`, so refresh the code graph at the end (it stays untracked).

- [ ] **Step 1: Implement**

Modify `.docker/compose.yml` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/.docker/compose.yml b/.docker/compose.yml
index aa42356..aa6c8a9 100644
--- a/.docker/compose.yml
+++ b/.docker/compose.yml
@@ -30,6 +30,14 @@ services:
       - traefik.http.routers.api-search.middlewares=search-ratelimit
       - traefik.http.middlewares.search-ratelimit.ratelimit.average=10
       - traefik.http.middlewares.search-ratelimit.ratelimit.burst=20
+      # LLM-backed and estimator routes: tighter limit, same explicit priority tier.
+      - traefik.http.routers.api-assistant.rule=PathPrefix(`/api/v1/assistant`) || PathPrefix(`/api/v1/estimates`)
+      - traefik.http.routers.api-assistant.priority=100
+      - traefik.http.routers.api-assistant.entrypoints=web
+      - traefik.http.routers.api-assistant.service=backend
+      - traefik.http.routers.api-assistant.middlewares=assistant-ratelimit
+      - traefik.http.middlewares.assistant-ratelimit.ratelimit.average=5
+      - traefik.http.middlewares.assistant-ratelimit.ratelimit.burst=10
       - traefik.http.routers.api.rule=PathPrefix(`/api`) || PathPrefix(`/health`)
       - traefik.http.routers.api.priority=50
       - traefik.http.routers.api.entrypoints=web
````

Modify `.docker/frontend.Dockerfile` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/.docker/frontend.Dockerfile b/.docker/frontend.Dockerfile
index 19af628..80188d5 100644
--- a/.docker/frontend.Dockerfile
+++ b/.docker/frontend.Dockerfile
@@ -12,7 +12,6 @@ FROM node:22-slim AS builder
 WORKDIR /app
 COPY --from=deps /app/node_modules ./node_modules
 COPY frontend/ ./
-ENV NEXT_PUBLIC_API_URL=/api
 RUN node node_modules/.bin/next build

 FROM node:22-slim AS runtime
````

Create `.scripts/smoke.sh`:

````bash
#!/usr/bin/env bash
# Acceptance check for the wired frontend (spec 3 §6.3): drives agent-browser through
# the RUNNING stack. Not part of CI (needs the stack). Usage:
#   ./.scripts/smoke.sh                       # against http://localhost (Traefik)
#   BASE_URL=http://localhost:3010 ./.scripts/smoke.sh
#   HEADED=1 ./.scripts/smoke.sh              # watch it in a window
set -euo pipefail
BASE_URL="${BASE_URL:-http://localhost}"
QUERY="${QUERY:-پژو ۲۰۶ تیپ ۲ تهران}"
MODEL="${MODEL:-پژو 206}"
AB=(agent-browser)
[[ "${HEADED:-0}" == "1" ]] && AB+=(--headed)
encode() { python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$1"; }

step() { printf '\n== %s\n' "$*"; }
page_text() { "${AB[@]}" get text body; }
expect_text() { # expect_text <needle> <label>
  if page_text | grep -q -- "$1"; then echo "ok: $2"; else echo "FAIL: $2 (missing «$1»)"; "${AB[@]}" screenshot smoke-fail.png; exit 1; fi
}
first_href() { "${AB[@]}" get attr "$1" href; }

trap '"${AB[@]}" close >/dev/null 2>&1 || true' EXIT

step "home stats"
"${AB[@]}" open "$BASE_URL/"
"${AB[@]}" wait --load networkidle
expect_text "آگهی فعال" "home shows the live listing count"
expect_text "به‌روزرسانی" "home shows the data snapshot time"

step "natural-language search"
"${AB[@]}" open "$BASE_URL/results?q=$(encode "$QUERY")"
"${AB[@]}" wait "a[href^='/listing/']"
expect_text "از جست‌وجوت فهمیدم" "parsed chips are shown"

step "near-miss labels"
"${AB[@]}" find text "بیشتر" click || true
"${AB[@]}" wait --load networkidle
expect_text "آگهی‌های مشابه" "near-miss divider after the exact matches"

step "listing page + similar"
LISTING="$(first_href "a[href^='/listing/']")"
[[ -n "$LISTING" ]] || { echo "FAIL: no listing link"; exit 1; }
"${AB[@]}" open "$BASE_URL$LISTING"
"${AB[@]}" wait --load networkidle
expect_text "مشاهده در دیوار" "price card links to Divar"
expect_text "مشخصات" "specs grid"
expect_text "آگهی‌های مشابه" "similar listings"
expect_text "متن آگهی فروشنده" "seller text"
if page_text | grep -Eq '(^|[^0-9۰-۹])0?9[0-9]{9}|۰۹[۰-۹]{9}'; then echo "FAIL: a phone number leaked into the page"; exit 1; else echo "ok: no phone numbers on the listing page"; fi

step "compare two listings"
"${AB[@]}" find text "+ مقایسه" click
SECOND="$(first_href "a[href^='/listing/']")"   # the first similar listing
"${AB[@]}" open "$BASE_URL$SECOND"
"${AB[@]}" wait --load networkidle
"${AB[@]}" find text "+ مقایسه" click
"${AB[@]}" open "$BASE_URL/compare"
"${AB[@]}" wait --load networkidle
expect_text "ویژگی" "compare table renders"
expect_text "ارزش خرید" "compare table has the deal-score row"

step "estimate"
"${AB[@]}" open "$BASE_URL/estimate"
"${AB[@]}" find label "برند و مدل" fill "$MODEL"
"${AB[@]}" wait "[role='listbox'] button"
"${AB[@]}" find first "[role='listbox'] button" click
"${AB[@]}" wait --load networkidle
cat <<'EOF' | "${AB[@]}" eval --stdin
const year = [...document.querySelectorAll("select")].find((el) => !el.disabled && el.options.length > 2 && el.value === "");
if (year) { const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set; setter.call(year, year.options[1].value); year.dispatchEvent(new Event("change", { bubbles: true })); }
EOF
"${AB[@]}" find text "تخمین بزن" click
"${AB[@]}" wait --load networkidle
expect_text "بازهٔ منطقی" "estimate result card"
expect_text "چطور حساب شد" "estimate breakdown"

step "assistant question"
"${AB[@]}" find role button click --name "دستیار"
"${AB[@]}" find label "پیام" fill "$QUERY"
"${AB[@]}" press Enter
"${AB[@]}" wait --load networkidle
expect_text "آگهی پیدا کردم" "assistant replied with a real count"

step "422 message"
"${AB[@]}" open "$BASE_URL/results?q=x&year=1200"
"${AB[@]}" wait "[role='alert']"
expect_text "Invalid search filters" "422 envelope message is shown inline"

echo
echo "SMOKE PASSED against $BASE_URL"
````

Modify `CLAUDE.md` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 44e3991..21139a0 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -22,7 +22,7 @@ This is a **monolith fullstack** application kept in a single repository:
   to Docker Hub.

 The backend exposes a versioned REST API (`/api/v1`) that the frontend is designed
-to consume; the frontend still runs on synthetic data until it is wired to the API
+to consume; the frontend renders only what the API returns (no synthetic data)
 (Spec 3). Traefik routes `/api` (and `/health`) to the backend and everything else to
 the frontend, so the whole app is served from one origin.

@@ -156,9 +156,9 @@ LLM_PROVIDER=google
 LLM_MODEL=gemini-3.7-flash
 LLM_API_KEY=
 LLM_BASE_URL=
-# Frontend — the browser reaches the API through Traefik on the same origin,
-# so use a relative base path (no host/port). Avoids CORS entirely.
-NEXT_PUBLIC_API_URL=/api
+# Frontend — Server Components call the backend directly on the Compose network;
+# the browser uses /api/v1 on the same origin through Traefik (no variable needed).
+API_INTERNAL_URL=http://backend:8000
 # Postgres (consumed by the db service in compose)
 POSTGRES_USER=app
 POSTGRES_PASSWORD=app
@@ -167,10 +167,10 @@ POSTGRES_DB=app
 SONAR_TOKEN=
 ```

-Because everything sits behind Traefik, browser requests are **same-origin**: set
-`NEXT_PUBLIC_API_URL=/api`. Server-side calls from Next.js (Server Components,
-route handlers) run inside the network and may instead hit the backend directly at
-`http://backend:8000` — never the public host.
+Because everything sits behind Traefik, browser requests are **same-origin**
+(`/api/v1`, added in `frontend/src/lib/api/base.ts` only). Server-side calls from
+Next.js (Server Components) run inside the network and hit the backend directly at
+`API_INTERNAL_URL` (`http://backend:8000`) — never the public host.

 Backend code reads config **only** through `core/config.py` (a `Settings` class);
 never read `os.environ` elsewhere.
@@ -255,6 +255,7 @@ semgrep ci                   # Run Semgrep with the project ruleset
 ./.scripts/test-db.sh        # Start the throwaway Postgres that `uv run pytest` needs
 ./.scripts/ingest.sh <csv>   # Load a Divar CSV (runs inside the backend container)
 ./.scripts/sonar.sh          # Coverage + local SonarQube scan (needs SONAR_TOKEN)
+./.scripts/smoke.sh          # agent-browser acceptance run against the running stack
 ```

 ---
@@ -424,8 +425,15 @@ class UUIDPrimaryKeyMixin:
   only when interactivity, state, or browser APIs require it.
 - **TypeScript strict mode** — no `any` unless unavoidable and commented.
 - Components are small and single-purpose; co-locate component-specific styles.
-- Centralize backend calls in `src/lib` (a typed API client). Read the base URL from
-  `NEXT_PUBLIC_API_URL`, never hard-coded.
+- All backend calls go through the typed client in `src/lib/api/` (`apiGet`,
+  `apiPost`, `useApi`); `base.ts` is the only place the `/api/v1` prefix and
+  `API_INTERNAL_URL` are known. Every fetch is `cache: "no-store"`.
+- `src/lib/api/types.ts` mirrors `backend/schemas/*.py` by hand — change both together.
+- The UI never invents data: loading skeletons, the backend's 422 message inline, and
+  «سرویس جست‌وجو در دسترس نیست» with retry for everything else. Branch on
+  `ApiError.code`/`status`, never on message text.
+- Server Components that fetch on every request call `await connection()` first —
+  Next 16 would otherwise prerender them (and hit the API) at build time.
 - Keep server-only secrets out of `NEXT_PUBLIC_*` variables.
 - `next.config.ts` must set `output: "standalone"` so the Docker image stays small.
 - Run `bun run lint` before considering frontend work done.
@@ -624,6 +632,14 @@ backend:
     - traefik.http.routers.api-search.middlewares=search-ratelimit
     - traefik.http.middlewares.search-ratelimit.ratelimit.average=10
     - traefik.http.middlewares.search-ratelimit.ratelimit.burst=20
+    # LLM-backed and estimator routes: tighter limit, same explicit priority tier.
+    - traefik.http.routers.api-assistant.rule=PathPrefix(`/api/v1/assistant`) || PathPrefix(`/api/v1/estimates`)
+    - traefik.http.routers.api-assistant.priority=100
+    - traefik.http.routers.api-assistant.entrypoints=web
+    - traefik.http.routers.api-assistant.service=backend
+    - traefik.http.routers.api-assistant.middlewares=assistant-ratelimit
+    - traefik.http.middlewares.assistant-ratelimit.ratelimit.average=5
+    - traefik.http.middlewares.assistant-ratelimit.ratelimit.burst=10
     - traefik.http.routers.api.rule=PathPrefix(`/api`) || PathPrefix(`/health`)
     - traefik.http.routers.api.priority=50
     - traefik.http.routers.api.entrypoints=web
@@ -684,6 +700,14 @@ services:
       - traefik.http.routers.api-search.middlewares=search-ratelimit
       - traefik.http.middlewares.search-ratelimit.ratelimit.average=10
       - traefik.http.middlewares.search-ratelimit.ratelimit.burst=20
+      # LLM-backed and estimator routes: tighter limit, same explicit priority tier.
+      - traefik.http.routers.api-assistant.rule=PathPrefix(`/api/v1/assistant`) || PathPrefix(`/api/v1/estimates`)
+      - traefik.http.routers.api-assistant.priority=100
+      - traefik.http.routers.api-assistant.entrypoints=web
+      - traefik.http.routers.api-assistant.service=backend
+      - traefik.http.routers.api-assistant.middlewares=assistant-ratelimit
+      - traefik.http.middlewares.assistant-ratelimit.ratelimit.average=5
+      - traefik.http.middlewares.assistant-ratelimit.ratelimit.burst=10
       - traefik.http.routers.api.rule=PathPrefix(`/api`) || PathPrefix(`/health`)
       - traefik.http.routers.api.priority=50
       - traefik.http.routers.api.entrypoints=web
@@ -886,4 +910,6 @@ alone is not enough.
 - [ ] No Semgrep or Gitleaks findings.
 - [ ] `./.scripts/sonar.sh` passes the quality gate.
 - [ ] Ranking changes keep the golden-query suite green.
+- [ ] Frontend changes keep `bunx tsc --noEmit` clean and `./.scripts/smoke.sh` passing
+      against the running stack.
 - [ ] No secrets, generated files, or lockfiles edited by hand.
````

Modify `README.md` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/README.md b/README.md
index 6ecd6ea..3b81729 100644
--- a/README.md
+++ b/README.md
@@ -1,16 +1,14 @@
 # ترب‌کار (Torobcar)

 A Persian, RTL car-search app — search, browse, compare, and get a price
-estimate for used cars. The frontend UI still runs on synthetic data generated
-in `src/lib` (it is not yet wired to the API); a real FastAPI search backend
-now exists alongside it and is runnable and tested on its own — see
-**Backend** below.
+estimate for used cars. The Next.js frontend renders real crawled Divar data
+served by the FastAPI search backend (see **Backend** below); nothing on screen
+is synthetic.

 ## Getting started

 The full stack (Traefik + backend + frontend + Postgres + Redis) is the
-supported way to run everything locally, though the frontend does not call
-the backend API yet:
+supported way to run everything locally — the frontend needs the backend:

 ```bash
 cp example.env .env
@@ -20,12 +18,19 @@ cp example.env .env

 The app runs at `http://localhost` (Traefik, port 80).

-To run just the frontend against its own dev server (no backend):
+`bun run dev` alone (no backend) renders every screen in its «سرویس جست‌وجو در
+دسترس نیست» state — there is no mock server. Server Components reach the backend
+at `API_INTERNAL_URL` (`http://backend:8000` in Compose); the browser calls
+`/api/v1` on the same origin through Traefik.
+
+### Acceptance smoke test
+
+With the stack running (and the CSV ingested), drive the real UI end to end with
+[agent-browser](https://github.com/vercel-labs/agent-browser):

 ```bash
-cd frontend
-bun install
-bun run dev
+./.scripts/smoke.sh              # home → search → listing → compare → estimate → chat → 422
+HEADED=1 ./.scripts/smoke.sh     # watch it
 ```

 ## Scripts (run from `frontend/`)
@@ -60,7 +65,11 @@ full architecture and conventions.
 | `GET /listings/{id}` | `ListingDetail` |
 | `GET /listings?ids=` | batch fetch for the compare page (≤ 4 ids) |
 | `GET /listings/{id}/similar?limit=6` | same ranker, intent derived from the listing |
-| `GET /facets?category=` | categories, top brands/models, cities — each with counts; cached under `data_version` |
+| `GET /facets?category=` | categories, top brands/models, cities (scoped by `category`) with counts, `model_count`, `data_as_of`; cached under `data_version` |
+| `GET /models/{model}/stats` | count, year range, price median/min/max, 8-bucket histogram, per-trim counts, top deals |
+| `GET /catalog/suggest?q=&category=` | ≤ 10 typo-tolerant `{brand, model, trim, category, count}` rows; empty `q` = largest trims |
+| `POST /estimates` | `{category, trim, year, km, insurance_months, body_condition, asking_price}` → estimate, IQR band, breakdown, asking verdict, similar; 422 `no_comparables` |
+| `POST /assistant` | `{messages (≤ 10, ≤ 500 chars), compare_ids}` → `{text, listings, answered_by}`; LLM agent with search/compare tools, rules fallback |
 | `GET /health` · `GET /health/ready` | liveness · readiness (Postgres + Redis ping) |

 ### Tests
````

Modify `example.env` (unified diff against the previous task's state — apply by hand or save the block to a file and `git apply` it):

````diff
diff --git a/example.env b/example.env
index 4b18446..164b2c2 100644
--- a/example.env
+++ b/example.env
@@ -16,9 +16,11 @@ LLM_API_KEY=
 LLM_BASE_URL=

 LLM_TIMEOUT_SECONDS=4
+ASSISTANT_TIMEOUT_SECONDS=20

-# Frontend — same origin through Traefik
-NEXT_PUBLIC_API_URL=/api
+# Frontend — the browser reaches the API same-origin through Traefik (no variable
+# needed); Server Components call the backend directly on the Compose network.
+API_INTERNAL_URL=http://backend:8000

 # Postgres (consumed by the db service)
 POSTGRES_USER=app
````

- [ ] **Step 2: Run the tests to verify they pass**

Run: `see Step 3`
Expected: see Step 3

- [ ] **Step 3: Definition of Done — run everything**

Rebuild and restart the stack so the new labels, env and images apply (get the user's go-ahead first — it restarts the running app), then run every gate from the repo root:

````bash
cp -n example.env .env                                   # only if .env does not exist; then set API_INTERNAL_URL if missing
docker compose -f .docker/compose.yml up -d --build      # Traefik + backend + frontend + db + redis
./.scripts/ingest.sh assets/<csv>                        # only if the database is empty
./.scripts/test-db.sh
(cd backend && uv run pytest -q && uv run ruff check . && uv run black --check .)
(cd backend && grep -rnE "sqlalchemy|redis|fastapi|pydantic_ai" ranking/ || echo "ranking/ is pure")
(cd backend && grep -rn "os.environ" --include=*.py . | grep -v "^./tests" || echo "no os.environ outside config")
(cd frontend && bun test && bunx tsc --noEmit && bun run lint)
(cd frontend && grep -rnE "LISTINGS|generateListings|MODELS\b" src || echo "no synthetic imports")
docker compose -f .docker/compose.yml config | grep -c "api-assistant"   # ≥ 5 label lines
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/api/v1/facets   # 200 through Traefik
for i in $(seq 1 12); do curl -s -o /dev/null -w "%{http_code} " -X POST http://localhost/api/v1/assistant -H 'content-type: application/json' -d '{"messages":[{"role":"user","text":"سلام"}],"compare_ids":[]}'; done; echo   # some 429s after the burst of 10 → the rate limit is live
./.scripts/smoke.sh                                      # 9 "ok:" lines and SMOKE PASSED
pre-commit run --all-files
gitleaks detect --source . --no-banner
````

Expected: `225 passed`; `27 pass`; both greps print their "ok" line; the facets call is `200`; the burst loop shows `429` after the first ten; the smoke script ends with `SMOKE PASSED against http://localhost`; no pre-commit or secret findings. If `curl` is blocked on the host, run the two HTTP checks from inside the network: `docker compose -f .docker/compose.yml exec -T backend python -c "import urllib.request;print(urllib.request.urlopen('http://traefik/api/v1/facets').status)"`.

Report anything you could not run (for example the LLM path without a key) instead of claiming it. Then refresh the code graph: run the `graphify` skill / CLI in update mode for the repo root (`graphify-out/` stays untracked).

- [ ] **Step 3: Commit**

From the repo root (`cd ..`), stage explicit paths only (never `git add -A`):

````bash
git add .docker/compose.yml .docker/frontend.Dockerfile .scripts/smoke.sh CLAUDE.md README.md example.env
git commit -m "feat(infra): rate-limit the assistant and estimate routes, add the smoke script and docs

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git log -1 --format='%(trailers)'   # must print exactly: Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
````

---
