# Torobcar Backend — Search Core (Spec 1 of 3)

**Date:** 2026-09-18 · **Branch:** `feat/backend-search-core` · **Status:** awaiting review

## 1. Goal and scope

Build the backend that turns a free-form Persian search into a ranked list of the
closest-matching vehicle ads from `assets/divar-vehicles-sep-17-20_32.csv`.

The core problem is **ranking**: given what the user asked for, order listings so exact
matches come first and near-misses (a year older, slightly over budget, a neighbouring
city) follow, labelled — instead of the current frontend behaviour where any missed
criterion makes a listing vanish.

**In this spec**

- Compose stack: Traefik (replaces NGINX), Postgres 18 + pgvector image, Redis.
- Schema + Alembic migrations; idempotent CSV ingest of all 14,652 rows.
- Comparables-based price estimate and deal score, precomputed at ingest.
- Soft-ranking search: SQL candidate retrieval → pure-Python ranker → Redis-cached pages.
- NL → typed `SearchIntent` via Pydantic AI, with a deterministic rules fallback.
- REST API: search, listing detail, batch listings, similar ads, facets, health.
- Self-hosted SonarQube quality gate (duplication, maintainability, security).

**Later specs**

- **Spec 2:** offline LLM enrichment of descriptions (body condition, accident, paint,
  tags), one-time LLM normalisation of the 1,262 catalog strings, pgvector embeddings
  blended into the match score, `body_styles` / `semantic_text` intent fields.
- **Spec 3:** chat assistant endpoint, `POST /estimates`, typeahead, and switching the
  frontend from client-side mocks to this API.

**Explicitly not built:** TLS/ACME, Redis persistence or auth, task queue, metrics stack,
ad expiry / price history, image mirroring, repost de-duplication, result diversity,
learning-to-rank, text-to-SQL.

## 2. Decisions taken during brainstorming

| Question | Decision |
|---|---|
| Data scope | Everything in the CSV: cars, heavy, motorcycles, rental, classic |
| Match model | Soft ranking with near-misses; only category + brand family are hard filters |
| LLM role | Query parsing now; enrichment + embeddings in Spec 2; assistant in Spec 3 |
| NLQ form | NL → typed `SearchIntent`. The LLM never writes SQL |
| Ranking architecture | SQL picks ≤ 5,000 candidates; Python ranks; Redis caches ranked IDs |
| Price estimate | Leave-one-out median of comparables with a fallback chain; regression is the upgrade path |
| Edge proxy | Traefik v3, label-based routing; no proxy image or config file |
| Code quality | Self-hosted SonarQube Community Build, run locally via script |

## 3. What the data looks like

14,652 unique ads (`token` is unique), fetched within one ~5-hour window.

| Segment (`webengage_cat_3` / `cat_2`) | Rows | Price column | Year column | Brand/model | Notes |
|---|---|---|---|---|---|
| `light` (passenger cars) | 4,720 | `قیمت پایه` | `مدل (سال تولید)` | 100% | km, colour, fuel 100%; gearbox 96%; insurance months 84%; **body condition 0%** |
| `heavy` | 4,958 | `قیمت` | `سال ساخت` | **0%** | has `نوع وسیلهٔ نقلیه`; km 68%; body 36% |
| motorcycles (`cat_3` empty) | 4,922 | `قیمت` | `مدل (سال تولید)` | 100% | km 100%; body 82% |
| `rental` | 43 | — (rent amount in `price_raw`) | `سال ساخت خودرو` | 53% | |
| `classic` | 9 | `قیمت` | `مدل (سال ساخت)` | 0% | |

Findings that drive normalisation rules:

| Finding | Rule |
|---|---|
| `webengage_price` is float32-rounded (`2150000128`); 1,920 rows differ from the text price | Parse the Persian text price; never read `webengage_price` |
| Placeholder prices < 10M toman: 206 cars, 204 motorcycles, 1,274 heavy | `price = NULL` below `MIN_PLAUSIBLE_PRICE_TOMAN = 10_000_000`; ad stays searchable, excluded from comparables |
| km ≥ 1,000,000: 17 cars, 54 motorcycles, 150 heavy | `km = NULL`. `km = 0` is kept (481 genuinely new cars) |
| `قبل از ۱۳۶۶` (32 rows) | `year = 1365` |
| `posted_raw` = relative time + location («۳ ساعت پیش در کرج، اسدآباد، …»); `district` column is empty | `posted_at = fetched_at − offset`; district = second location segment |
| 800 distinct cities; lat/lng present on 99.2% of rows | City centroid = median of its listings' coordinates; no gazetteer |
| 1,666 car `(trim, year)` groups, only 280 with ≥ 5 ads (52% of cars) | Estimate needs a fallback chain (§6.3) |

The CSV is gitignored (`assets/*.csv`). Descriptions contain sellers' phone numbers, so
it must stay out of git, and the committed test fixture blanks `description`.

## 4. Infrastructure

### 4.1 Compose (`.docker/compose.yml`)

Only `traefik` publishes a host port.

| Service | Image | Notes |
|---|---|---|
| `traefik` | `traefik:v3` | `80:80`. Docker provider, `exposedByDefault=false`, docker socket mounted read-only. Dashboard on `8080` in `compose.dev.yml` only |
| `backend` | `.docker/backend.Dockerfile` | labels: rule `PathPrefix(/api) \|\| Path(/health) \|\| PathPrefix(/health/)` → port 8000; `rateLimit` middleware (average 10 rps, burst 20, per source IP) on the `/api/v1/search` router |
| `frontend` | `.docker/frontend.Dockerfile` | label: `PathPrefix(/)`, priority 1 → port 3000 |
| `db` | `pgvector/pgvector:pg18` | volume at `/var/lib/postgresql`; `pg_trgm` enabled by the first migration; `vector` is enabled in Spec 2 |
| `redis` | `redis:8-alpine` | `--save "" --maxmemory 256mb --maxmemory-policy allkeys-lru`; cache only |

Removed: `nginx.Dockerfile`, `nginx/default.conf`, the nginx service, and the nginx entry
in the `docker-publish.yml` matrix (two images ship instead of three). Traefik proxies
WebSocket/HMR upgrades without extra configuration.

`compose.dev.yml` keeps the backend/frontend hot-reload overrides and adds the Traefik
dashboard port.

### 4.2 Environment (`example.env` additions)

```dotenv
REDIS_URL=redis://redis:6379/0
SEARCH_CACHE_TTL_SECONDS=600
LLM_PROVIDER=google            # google | openai_compatible
LLM_MODEL=gemini-flash-latest  # confirm the exact model id at plan time
LLM_API_KEY=
LLM_BASE_URL=                  # only for openai_compatible (e.g. https://openrouter.ai/api/v1)
LLM_TIMEOUT_SECONDS=4
SONAR_HOST_URL=http://localhost:9000
SONAR_TOKEN=
```

Real keys live only in `.env` (gitignored; gitleaks guards the rest).

### 4.3 `CLAUDE.md` updates

§1–3, §11, §12, §14: NGINX → Traefik; db image; Redis; Pydantic AI; SonarQube; the three
new backend packages. The "only the edge publishes a port" rule is unchanged. Root
`CLAUDE.md` is currently untracked — it gets committed with this work.

## 5. Backend layout

Follows `CLAUDE.md` §2/§6 (endpoints → services → repositories → models; Pydantic
schemas at the boundary; DI via `Depends`). Three packages are added for things that do
not fit the existing folders:

```
backend/
  core/config.py      Settings (pydantic-settings) — the only reader of the environment
  core/cache.py       Cache: thin async Redis wrapper — get_json / set_json / incr
  core/text.py        normalize_persian() — the single text normaliser
  ranking/            PURE PYTHON, NO I/O
    weights.py          frozen RankingWeights dataclass + named constants
    closeness.py        one function per criterion
    ranker.py           ListingRanker: score, label, sort
    labels.py           Persian near-miss labels
    estimator.py        PriceEstimator: comparables median + adjustments + deal score
  ingest/             CSV → NormalizedListing → upsert → estimate pass (CLI)
    column_maps.py      per-category column map
    normalizers.py      price, km, year, posted_at, district, brand split
    pipeline.py         orchestration + report
    __main__.py         `uv run python -m ingest <csv>`
  llm/
    model_factory.py    provider switch
    intent_agent.py     Agent(output_type=SearchIntent)
    rules_parser.py     deterministic fallback
    eval.py             opt-in live accuracy script
  models/ schemas/ repositories/ services/ api/v1/endpoints/ dependencies/ tests/
```

`ranking/` has no I/O on purpose: the sorting algorithm is unit-testable with plain
dataclasses, no database and no Redis.

## 6. Data model and ingest

### 6.1 Tables (UUIDv8 primary keys via `UUIDPrimaryKeyMixin`)

```
vehicle_catalog  id · category · brand · model · trim · trim_normalized · listing_count
                 UNIQUE (category, trim)            trim = the raw «برند و مدل» string
cities           id · name UNIQUE · lat · lng · listing_count
listings         id · token UNIQUE · url · category · catalog_id FK NULL · city_id FK
                 title · title_normalized · description
                 year · km · price BIGINT (toman) · gearbox · fuel · color
                 body_condition · insurance_months · vehicle_type · is_dealer
                 district · lat · lng · posted_at · fetched_at
                 image_urls TEXT[] · thumbnail_urls TEXT[]
                 attributes JSONB
                 est_price · est_basis · est_sample_size · km_factor · insurance_factor
                 diff_pct · deal_score
```

- Anything the ranker or a filter reads is a typed column; every other CSV field goes to
  `attributes` (engine cc, starter, clutch, ownership, exchange, rent amount, …).
- `Category`, `Gearbox`, `Fuel`, `BodyCondition`, `EstimateBasis`, `SortKey`, `Verdict`,
  `LlmProvider` are enums in `enums.py`. An unknown CSV value fails ingest loudly.
- Indexes: unique `token`; btree `(category, catalog_id)`; GIN `gin_trgm_ops` on
  `listings.title_normalized` and `vehicle_catalog.trim_normalized`. Nothing else at
  14.6k rows. *Ceiling:* add price/year btrees past ~500k rows.
- No columns are reserved for Spec 2; adding `enrichment` / `embedding` later is one
  short migration.

### 6.2 Normalisation

`normalize_persian()` — `ي→ی`, `ك→ک`, Persian/Arabic digits → ASCII, strip RLM
(`‏`), ZWNJ → space, collapse whitespace, lowercase Latin. Used identically at
ingest and at query time.

Brand/model/trim split — the CSV has only Divar's leaf string (`پژو 206 تیپ ۲`):
`brand` = first token, `model` = first two tokens, `trim` = full string, with a small
`MULTI_TOKEN_BRANDS` override map (e.g. the first token `اس` currently swallows 193
rows). *Ceiling:* irregular model families; *upgrade:* Spec 2's one-time LLM
normalisation of the 1,262 strings.

Heavy vehicles have no brand/model: `catalog_id = NULL`, `vehicle_type` set, matched by
title trigram only.

### 6.3 Price estimate and deal score (`ranking/estimator.py`)

Computed for priced `light` and motorcycle rows; `est_basis = none` for heavy, rental,
classic and anything without comparables. Catch-all trims (`سایر`, and any trim
containing `سایر` — 567 rows across 14 trims) are never used as a comparables group: they lump
unrelated vehicles together, so their median means nothing.

Vehicle age uses the Jalali year of the newest `fetched_at`, from a three-line
`jalali_year(date)` helper in `core/text.py` (Gregorian year − 621 on or after 21 March,
− 622 before). No calendar dependency. The intent agent's prompt uses the same helper.

1. **Base price** — leave-one-out median (a listing never validates its own price) over
   the first group with n ≥ 5:
   `(trim, year)` → `(trim, year ± 1)` → `(model, year)` → `(model, year ± 2)` → none.
2. **Mileage factor** — expected km = median km of the same category and age, learned
   from the data (the frontend's hardcoded 18,000 km/year would be wrong for
   motorcycles, whose median total is 11,000 km).
   `km_factor = 1 − clamp((km − expected) / expected, −0.5, 1) × 0.08`.
3. **Insurance factor** — `1 + (months − 6) × 0.002` where `insurance_months` exists.
4. `est_price = base × km_factor × insurance_factor`;
   `diff_pct = (price − est_price) / est_price × 100`.
5. `deal_score = clamp(round(72 − 2.4·diff_pct + 120·(km_factor − 1) + body_term), 5, 99)`
   where `body_term = 90·(body_factor − 0.92)` only when `body_condition` is present
   (motorcycles today; cars after Spec 2).

Constants come from the frontend's `pricing.ts` / `listings.ts` so both sides agree.

### 6.4 Ingest pipeline — `uv run python -m ingest <csv>`

1. Stream the CSV (`csv` stdlib, raised field size limit). Row → category column map →
   `NormalizedListing` (Pydantic; the CSV is a trust boundary).
2. Upsert `cities` and `vehicle_catalog`; bulk upsert `listings` with
   `INSERT … ON CONFLICT (token) DO UPDATE`, batches of 1,000.
3. Recompute city centroids and `listing_count`s.
4. Estimate pass over all rows; bulk update.
5. `INCR search:data_version` in Redis — invalidates every search and facet cache key.
6. Print a report: read / upserted / rejected (with reasons), fields nulled by rule,
   estimate-basis coverage. A row missing `token`, `title` or a recognisable category is
   rejected. Exit non-zero if rejects exceed 1%.

Re-running with a newer scrape is safe. Freshness is measured against the newest
`fetched_at` in the table, not wall-clock time.

## 7. Search and ranking

### 7.1 `SearchIntent`

```python
class VehicleMention(BaseModel):          # free text — the resolver maps it to the catalog
    brand: str | None = None
    model: str | None = None
    trim: str | None = None

class SearchIntent(BaseModel):
    category: Category | None = None
    vehicles: list[VehicleMention] = []
    year_min: int | None = None           # «مدل ۹۸» → both 1398 · «۹۵ به بالا» → min only
    year_max: int | None = None
    price_min: int | None = None          # toman
    price_max: int | None = None
    km_max: int | None = None
    cities: list[str] = []
    gearbox: Gearbox | None = None
    fuel: Fuel | None = None
    colors: list[str] = []
    only_below_market: bool = False
    text: str | None = None               # unparsed remainder → title trigram match
    sort: SortKey = SortKey.RELEVANCE     # relevance | deal | price | km | newest
```

A `model_validator` rejects `price_min > price_max`, `year_min > year_max`, years outside
1340…current+1, and non-positive numbers. Both the LLM/rules parser and the filter sheet
produce this one type, so there is one ranking path.

### 7.2 Stage 1 — resolve (`CatalogResolver`)

Each mention is matched against `vehicle_catalog` with pg_trgm `word_similarity`
(`word_similarity`, because «۲۰۶» is a substring of `پژو 206 تیپ ۲`). The resolver
returns the matched catalog rows **and the level the user specified** — brand, model or
trim. A mention with no hit ≥ `MIN_CATALOG_SIMILARITY` (0.6) is appended to `text`;
this is how heavy vehicles, `سایر` rows and typos are handled.

### 7.3 Stage 2 — candidates (`ListingRepository.find_candidates`)

One query, scoring columns only (plain rows, not ORM objects):

- Hard filters: `category`; resolved **brand** set; `only_below_market`
  (`diff_pct ≤ −5`).
- Guard rails placed exactly where closeness reaches 0. Each bound is applied only when
  the intent states it, and NULL values always pass (they score neutral in §7.4):
  `price ≥ price_min × 0.75`, `price ≤ price_max × 1.25`, `km ≤ km_max × 1.5`,
  `year ≥ year_min − 5`, `year ≤ year_max + 5`.
- Text branch: `word_similarity(:text, title_normalized) ≥ 0.3`, similarity returned as a
  column.
- `ORDER BY deal_score DESC NULLS LAST, id LIMIT 5000` — a deterministic cap.
  *Ceiling:* 5,000 candidates; *upgrade:* tighter guard rails or SQL-side scoring.

### 7.4 Stage 3 — rank (`ranking/ranker.py`)

```
match = Σ wᵢ·cᵢ / Σ wᵢ        over the criteria the user actually stated
rank  = 0.55·match + 0.30·deal + 0.15·fresh
```

| Criterion | Weight | Closeness `cᵢ` |
|---|---|---|
| vehicle | 3.0 | relative to the level the user specified. Brand given: every listing of that brand 1.0. Model given: that model (any trim) 1.0 · same brand, other model 0.3. Trim given: that trim 1.0 · same model, other trim 0.8 · same brand, other model 0.3. Best score over all mentions |
| price | 2.5 | 1.0 inside the range; linear to 0 at ±25% |
| year | 2.0 | 1.0 inside the range; `1 − Δ/5` |
| city | 1.5 | same city 1.0; else `min(0.9, 1 − haversine_km / 300)`, best over requested cities; a listing without coordinates uses its city centroid |
| km | 1.5 | 1.0 if ≤ max; linear to 0 at +50% |
| gearbox · fuel | 1.0 each | 1.0 / 0.0 |
| text | 1.0 | trigram similarity value |
| color | 0.5 | 1.0 / 0.0 |

- `deal = deal_score / 100`; neutral 0.5 when there is no estimate.
- `fresh = exp(−age_days / 14)`, age measured from `posted_at` to the newest `fetched_at`.
  An unparseable `posted_raw` phrase gives `posted_at = NULL` (counted in the ingest
  report) and a neutral `fresh = 0.5`.
- **Unknown is neutral:** a listing with NULL price/km/gearbox scores 0.5 on that
  criterion and gets a label («قیمت توافقی»).
- `MIN_MATCH_SCORE = 0.4` — results below it are dropped.
- No criteria stated (browse): `rank = 0.67·deal + 0.33·fresh`.
- `is_exact` = every stated criterion scored 1.0.
- Tie-break: `rank DESC, posted_at DESC, id`.
- **Explicit sorts** (price, km, newest, deal) apply inside tiers: key =
  `(is_exact DESC, chosen key)`.
- **Near-miss labels** are built server-side, top two per result:
  «۲۰ میلیون بالاتر از بودجه», «یک سال قدیمی‌تر», «۴۰ کیلومتر دورتر · کرج»,
  «گیربکس دنده‌ای».

All weights and thresholds live in a frozen `RankingWeights` dataclass
(`ranking/weights.py`), not in environment settings.

### 7.5 Stage 4 — cache and paginate

- Key `search:{data_version}:{sha256(canonical intent JSON)}` → top 500 results as
  `[id, rank, match, is_exact, labels]`, TTL `SEARCH_CACHE_TTL_SECONDS`.
- A page = slice → `WHERE id = ANY(:ids)` → restore order. Later pages never re-rank.
- Redis unavailable → log a warning, rank uncached. Search never fails because the cache
  is down.
- *Ceiling:* 500 results per query; paging past it returns `InvalidSearchError`.

### 7.6 Similar ads

`SimilarListingsService` builds a `SearchIntent` from the listing (its trim, year, price
± 15%, city), excludes the listing itself, and calls the same pipeline.

## 8. LLM layer

### 8.1 Model factory

```python
match settings.llm_provider:
    case LlmProvider.GOOGLE:              # development — Gemini API key
        return GoogleModel(settings.llm_model,
                           provider=GoogleProvider(api_key=settings.llm_api_key))
    case LlmProvider.OPENAI_COMPATIBLE:   # production — OpenRouter or any OpenAI-like API
        return OpenAIChatModel(settings.llm_model,
                               provider=OpenAIProvider(base_url=settings.llm_base_url,
                                                       api_key=settings.llm_api_key))
```

Dependency: `pydantic-ai-slim[google,openai]`.

### 8.2 Intent agent

`Agent(model, output_type=SearchIntent, instructions=…)`, no tools. Instructions cover
Persian market conventions («زیر ۸۰۰» = 800 million toman; bare «۱.۲» = billions), the
current Jalali year, the enum vocabularies and ~8 worked examples. The catalog is not in
the prompt. Validation errors on `SearchIntent` are fed back to the model by Pydantic AI
and retried.

### 8.3 `QueryParser` flow

1. `normalize_persian(q)`; empty → empty intent (browse).
2. Redis `intent:{PROMPT_VERSION}:{sha256(q)}` hit → return (TTL 24 h; independent of
   `data_version`).
3. Run the agent with `LLM_TIMEOUT_SECONDS`.
4. Timeout, provider error or retries exhausted → `rules_parser` (a Python port of the
   frontend's `parseQuery` regexes for price, km, year, gearbox, city; the remainder
   becomes one `VehicleMention`). Logged at WARNING. Fallback results are not cached.
5. Response carries `parsed_by: "llm" | "rules"`.

A never-seen query waits ~0.5–2 s for the LLM; the frontend's skeleton loader covers it.
Repeated queries cost nothing.

### 8.4 Abuse

Typed, validated output; no tools; `text` only reaches a parameterised
`word_similarity()`. Cost abuse is bounded by `q` ≤ 300 characters and the Traefik rate
limit on `/api/v1/search`.

## 9. API (`/api/v1`)

| Endpoint | Purpose |
|---|---|
| `GET /search` | `q`, plus explicit filter params `category, models, cities, year, price_max, km_max, gearbox, only_below, sort, page, page_size` (≤ 50). Explicit params override what was parsed from `q`. `models` takes `model` values as returned by `/facets` (resolved at model level); `year` sets both `year_min` and `year_max` |
| `GET /listings/{id}` | `ListingDetail` |
| `GET /listings?ids=` | batch fetch for the compare page (≤ 4 ids) |
| `GET /listings/{id}/similar?limit=6` | same ranker, intent derived from the listing |
| `GET /facets?category=` | categories, top brands/models, cities — each with counts; cached under `data_version` |
| `GET /health` · `GET /health/ready` | liveness · readiness (Postgres + Redis ping) |

```jsonc
// SearchResponse
{ "intent": { /* resolved SearchIntent */ "chips": ["پژو ۲۰۶", "مدل ۱۳۹۸", "زیر ۸۰۰ میلیون", "تهران"] },
  "parsed_by": "llm", "total": 143, "exact_count": 12, "page": 1, "page_size": 20,
  "items": [{ "id": "…", "token": "gamGI7iu", "title": "…", "category": "light",
              "brand": "پژو", "model": "پژو 206", "trim": "پژو 206 تیپ ۲",
              "year": 1398, "km": 62000, "price": 780000000,
              "city": "تهران", "district": "…", "thumbnail_url": "…", "posted_at": "…",
              "est_price": 815000000, "diff_pct": -4.3, "deal_score": 78, "verdict": "fair",
              "match_score": 0.93, "is_exact": false,
              "near_miss_labels": ["یک سال قدیمی‌تر"] }] }
```

- Prices are integer toman (max ≈ 10¹¹, inside JS safe-integer range).
- `verdict`: `cheap` (`diff_pct ≤ −5`) · `expensive` (`≥ 6`) · `fair` · `unknown` (no
  estimate) — the frontend's thresholds.
- `ListingDetail` = card fields + `description`, `image_urls`, `lat`, `lng`, `gearbox`,
  `fuel`, `color`, `insurance_months`, `attributes`, and
  `price_breakdown { base, km_adjustment, insurance_adjustment, est_basis, est_sample_size }`
  — what the frontend's `breakdownRows()` computes client-side today.

## 10. Errors and logging

`errors.py`: `AppError(status_code, code, message, context)` →
`ListingNotFoundError` 404 · `InvalidSearchError` 422 · `ServiceUnavailableError` 503
(mapped from SQLAlchemy `OperationalError`) · `IngestError` (CLI). Handlers in `main.py`
emit one envelope, `{"error": {"code", "message", "details"}}`; FastAPI's
`RequestValidationError` is reshaped into it. Unhandled exceptions → generic 500, logged
in full with a request ID. An LLM failure is never a client-facing error.

One structured JSON log line per search: query hash, `parsed_by`, cache hit/miss,
candidate count, `parse_ms`, `candidates_ms`, `rank_ms`.

## 11. Testing

| Layer | How |
|---|---|
| `ranking/` | Pure unit tests per closeness function + property tests: improving one criterion never lowers `rank`; an exact match scores ≥ the same listing degraded on any criterion |
| `ingest/` normalisers | One test per rule in §3, tiny inline CSV strings |
| `llm/` | Pydantic AI `TestModel` / `FunctionModel`; `ALLOW_MODEL_REQUESTS = False` globally. `rules_parser` driven by a shared query → expected-intent table |
| repositories | Real Postgres (pg_trgm cannot be faked with SQLite): `pgvector/pgvector:pg18` service container in CI, compose `db` locally via `TEST_DATABASE_URL`; each test in a rolled-back transaction |
| services | Repositories mocked (`CLAUDE.md` §8); cache replaced by a dict-backed stub of `Cache` |
| API + golden queries | `httpx.AsyncClient` over `ASGITransport` against a ~600-row fixture DB |

**Golden-query suite** — ~20 real Persian queries asserting properties, never IDs: every
top-10 result is a 206; nothing exceeds budget × 1.25; exact matches precede near-misses;
a Karaj listing outranks a Mashhad one for a Tehran search; a NULL-price ad never outranks
an exact priced match. This is the regression net for every weight change.

**Live LLM eval** — `uv run python -m llm.eval` runs the labelled table against the real
provider and prints field-level accuracy. Opt-in, never in CI.

**Fixture** — `backend/tests/fixtures/listings_sample.csv`: ~600 rows stratified across
categories, only the columns tests need, `description` blanked (phone numbers).

## 12. Code quality — SonarQube (self-hosted Community Build)

**Why a local script and not GitHub Actions:** the server runs on the developer machine,
which GitHub-hosted runners cannot reach, and Community Build analyses one branch only
(no PR or branch analysis). Semgrep and Gitleaks stay in `security.yml` as the CI-side
security gate; SonarQube adds duplication, maintainability, reliability, coverage and its
own security rules on top.

**`.docker/compose.sonar.yml`** — a separate Compose project (`name: torobcar-sonar`),
started only when scanning:

| Service | Image | Notes |
|---|---|---|
| `sonarqube` | `sonarqube:community` (pin an exact tag at plan time) | publishes `127.0.0.1:9000:9000` — loopback only; volumes for data, extensions, logs |
| `sonar-db` | `postgres:17-alpine` (confirm SonarQube's supported Postgres range at plan time) | internal only |

This is a developer tool outside the application stack, so its loopback-bound port is a
documented exception to the "only Traefik publishes a port" rule.

**`sonar-project.properties`** (repo root):

```properties
sonar.projectKey=torobcar
sonar.sources=backend,frontend/src
sonar.tests=backend/tests,frontend/src
sonar.test.inclusions=backend/tests/**,frontend/src/**/*.test.ts,frontend/src/**/*.test.tsx
sonar.exclusions=backend/db/migrations/versions/**,backend/tests/fixtures/**,**/.next/**,**/node_modules/**
sonar.cpd.exclusions=backend/tests/**,frontend/src/**/*.test.ts
sonar.python.version=3.14
sonar.python.coverage.reportPaths=backend/coverage.xml
sonar.javascript.lcov.reportPaths=frontend/coverage/lcov.info
sonar.qualitygate.wait=true
```

`prototype/`, `brag-output/`, `graphify-out/`, `assets/` are outside `sonar.sources` and
are never scanned.

**`.scripts/sonar.sh`**

1. `uv run pytest --cov=. --cov-report=xml` in `backend/` (adds dev dependency
   `pytest-cov`).
2. `bun test --coverage --coverage-reporter=lcov` in `frontend/`.
3. Run `sonarsource/sonar-scanner-cli` in Docker with `SONAR_HOST_URL` / `SONAR_TOKEN`
   from `.env`. With `sonar.qualitygate.wait=true` the script exits non-zero when the gate
   fails.

**Quality gate** — the built-in "Sonar way" gate on new code: no new issues, all new
security hotspots reviewed, new-code coverage ≥ 80%, new-code duplication ≤ 3%. The
existing frontend is scanned too; its pre-existing findings appear under overall code and
are triaged separately — they do not block this work.

`CLAUDE.md` §14 gains: "`./.scripts/sonar.sh` passes the quality gate".

## 13. CI changes

- `ci.yml` backend job: add a `pgvector/pgvector:pg18` service container and
  `TEST_DATABASE_URL`; run pytest with coverage.
- `docker-publish.yml`: matrix drops nginx (backend + frontend only).
- `security.yml`: unchanged.

## 14. Dependencies and risks

Runtime: `fastapi[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`,
`pydantic-settings`, `redis`, `pydantic-ai-slim[google,openai]`.
Dev: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `black`.

| Risk | Mitigation |
|---|---|
| Python 3.14 wheels for `asyncpg` / Pydantic AI extras | First plan task is `uv sync` on 3.14; fall back to 3.13 only with the user's agreement |
| Heuristic brand/model split mis-groups some families | Override map + golden queries now; LLM normalisation in Spec 2 |
| Thin comparables → noisy estimates | `est_basis` + `est_sample_size` exposed; `verdict = unknown` when none; regression is the upgrade path |
| LLM latency on first-seen queries | 4 s timeout, rules fallback, 24 h intent cache |
| SonarQube needs ~3 GB RAM | Separate Compose project, started only for scans |

## 15. Amendments found while planning (2026-09-18)

Writing the plan meant running the design against the real CSV and a real
Postgres 18. These findings override the sections they name.

| # | Overrides | Change | Evidence |
|---|---|---|---|
| A1 | §6.3 | Deal-score slope is **1.0**, not 2.4 | Real `diff_pct` IQR is −10%…+12%; 2.4 pins 25% of scores at the 5/99 clamp, 1.0 pins under 5% |
| A2 | §6.1, §6.3, §7.3, §9 | New column **`listings.price_suspect`**: `diff_pct < −40` or `> +100`. Suspect listings keep their listed price in the API, but the ranker sees `price = NULL` (neutral, «قیمت توافقی»), they get no `diff_pct` / `deal_score`, and `verdict = unknown` | 6.6% of cars and 22% of motorcycles; e.g. an MVM X55 listed at 10,000,000 toman against a 4-billion estimate. Unguarded, these rank as the best deals and match every budget |
| A3 | §7.4 | Two tiers order results **ahead of `rank`**: (1) exact matches precede near-misses for every sort, including relevance; (2) listings of the requested model precede listings that only share its brand. `rank` orders listings inside a tier | On the real data, great-deal Peugeot 405s outranked real 206s for a «۲۰۶» query, and a great-deal near-miss outranked a poor-deal exact match |
| A4 | §6.4 | Upsert batches of **500**, not 1,000 | asyncpg's 32,767 bind-parameter limit; a listing row has ~35 columns |
| A5 | §3 | `قبل از Y` → `Y − 1` for **every** year (766 rows), and Gregorian years (> 1420) convert with `− 621` | Heavy vehicles use the same phrase with other years |
| A6 | §6.1 | `cities.name_normalized` added; `vehicle_catalog.brand` / `.model` stored normalised | City lookup and level inference compare normalised tokens |
| A7 | §7.2 | The resolver tries each mention twice: with and **without the brand** | `word_similarity('سایپا پراید', 'پراید 131 se')` = 0.5 < 0.6, while `'پراید'` alone = 1.0 |
| A8 | §9 | `GET /search` takes **one** query-parameter model (`SearchParams`) | FastAPI cannot mix a query model with individual `Query()` parameters (422) |
| A9 | §11 | Tests use `.docker/compose.test.yml` (loopback `127.0.0.1:54329`, tmpfs) | The app's `db` service publishes no host port |
| A10 | §6.4 | Ingest runs inside the backend container (`.scripts/ingest.sh`) | `db` and `redis` are unreachable from the host |
| A11 | §10 | Search log line carries `parsed_by`, `cache_hit`, `total`, `duration_ms` only | Ranking takes 7 ms on the real data; stage timings are added when a latency problem needs locating |
| A12 | §4.3 | Pre-commit file is `.pre-commit-config.yaml` | pre-commit's default name; resolves the `CLAUDE.md` §10 caveat |

Confirmed unchanged: `pg_trgm` handles Persian in `pgvector/pgvector:pg18` («۲۰۶» vs
`پژو 206 تیپ 2` = 1.0, a typo'd trim = 0.77, unrelated = 0); every dependency installs
on Python 3.14.6; the full ingest takes 5.7 s for 14,652 rows with 0 rejects and is
idempotent; estimates cover 83% of cars and 60% of motorcycles.

## 16. Done means

- `docker compose -f .docker/compose.yml up --build` serves the app at `http://localhost`
  through Traefik; no other service publishes a port.
- `uv run python -m ingest assets/divar-vehicles-sep-17-20_32.csv` loads 14,652 rows
  with < 1% rejects and prints the report; a second run changes nothing.
- `GET /api/v1/search?q=۲۰۶ مدل ۹۸ زیر ۸۰۰ میلیون تهران` returns exact matches first,
  then labelled near-misses; works with the LLM key unset (`parsed_by: "rules"`).
- `uv run pytest`, `ruff`, `black --check`, `pre-commit run --all-files`, Semgrep and
  Gitleaks are clean; `./.scripts/sonar.sh` passes the quality gate.
