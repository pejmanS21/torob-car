# Torobcar — Frontend on the Real API (Spec 3)

**Date:** 2026-09-18 · **Branch:** `feat/frontend-api-wiring` (off `feat/backend-search-core`) · **Status:** awaiting review

## 1. Goal and scope

Replace every piece of synthetic data in the Next.js frontend with the real crawled
Divar data served by the search-core backend (Spec 1), and add the backend endpoints
the remaining screens need.

**In this spec**

- Backend: model stats, catalog suggest, estimates and assistant endpoints; small
  additions to `ListingCard` and `Facets`; category-scoped facet counts.
- Frontend: a typed API client; every route and component moved off `LISTINGS`,
  `MODELS` and client-side computation; category-aware rendering.
- Loading, error and empty states for every screen; fixture-based tests; an
  agent-browser smoke script as the acceptance check.

**Out of scope:** issue tags and seller assessment (Spec 2 enrichment), user accounts and
server-side alerts, per-listing SEO metadata, exposing FastAPI `/docs` through Traefik.

## 2. Decisions taken during brainstorming

| Question | Decision |
|---|---|
| Scope | Everything in one pass: all screens incl. model stats, estimate, chat, alerts |
| Vehicle categories | All categories equal — no default category; the query or filter sheet narrows it |
| Data wiring | Server-first + client islands: Server Components fetch `http://backend:8000`; interactive screens call same-origin `/api/v1` |
| Issue bars | Replaced by per-trim bars until Spec 2 provides issue tags |
| Assistant | Stateless: the client sends recent history and compare ids each call |
| Results state | The URL is the single source of truth; every filter change goes through the backend |

## 3. Backend additions

All new endpoints follow the existing layering (endpoint → service → repository), the
error envelope, and `ranking/` purity. Money is integer toman.

### 3.1 `GET /api/v1/models/{model}/stats`

`model` is the normalised model name (e.g. `پژو 206`), URL-encoded. 404
(`model_not_found`) when the catalog has no such model.

```jsonc
{ "model": "پژو 206", "brand": "پژو", "category": "light",
  "count": 368, "year_min": 1382, "year_max": 1404,
  "price_median": 1100000000, "price_min": 480000000, "price_max": 1650000000,
  "histogram": [{ "low": 480000000, "high": 626000000, "count": 12 }],   // 8 buckets
  "trims": [{ "trim": "پژو 206 تیپ ۲", "count": 177, "price_median": 1150000000 }],
  "top_deals": [/* ListingCard, up to 6 */] }
```

- Prices exclude NULL and `price_suspect` listings.
- Histogram: 8 equal-width buckets between the 5th and 95th percentile; out-of-range
  prices fall into the edge buckets. Bucket counts sum to the priced count.
- `trims`: every trim of the model, sorted by count desc.
- `top_deals`: highest `deal_score` first.

### 3.2 `GET /api/v1/catalog/suggest?q=&category=`

Up to 10 `{ brand, model, trim, category, count }` rows, reusing
`CatalogRepository.search` (pg_trgm `word_similarity`, typo-tolerant). `q` ≤ 100
characters; empty `q` returns the 10 largest models of the category.

### 3.3 `POST /api/v1/estimates`

```jsonc
// request
{ "category": "light", "trim": "پژو 206 تیپ ۲", "year": 1398, "km": 90000,
  "insurance_months": 6, "body_condition": null, "asking_price": 850000000 }
// response
{ "est_price": 1120000000, "low": 1050000000, "high": 1190000000,
  "est_basis": "trim_year", "est_sample_size": 5,
  "breakdown": { "base": 1165000000, "km_adjustment": -25000000, "insurance_adjustment": 0 },
  "asking_verdict": "cheap", "asking_diff_pct": -24.1,
  "similar": [/* ListingCard, up to 4 */] }
```

- The math is the ingest estimator's, extracted into pure functions in
  `ranking/estimator.py` so the bulk pass and a single estimate share one code path.
- `low`/`high` = the 25th/75th percentile of the comparables, scaled by the same
  km and insurance factors.
- No comparables → 422 `no_comparables`, with the basis chain tried in `details`.
- `similar` = the search pipeline with the trim, year ± 1 and the category.

### 3.4 `POST /api/v1/assistant`

```jsonc
// request
{ "messages": [{ "role": "user", "text": "دنا پلاس زیر یک میلیارد کرج" }],  // last ≤ 10
  "compare_ids": [] }
// response
{ "text": "…", "listings": [/* ListingCard */], "answered_by": "llm" }     // or "rules"
```

- LLM path: a Pydantic AI agent (same model factory as the intent agent) with tools
  `search_listings(intent: SearchIntent)` (the existing `SearchService.rank`) and
  `compare_listings(ids)`. Output type `AssistantReply(text, listing_ids)`; the service
  hydrates the cards. The LLM never writes SQL.
- Rules path (no key, timeout, or provider error): parse the last user message with the
  intent parser, run the search, and reply with count, median price, below-market count
  and the top 3 — the same shape as today's `scriptedReply`. A "which is better"
  question with ≥ 2 compare ids answers with the highest deal score among them.
- Messages ≤ 500 characters each; history capped at 10.

### 3.5 Changes to existing endpoints

- `ListingCard` gains `lat`, `lng`, `gearbox`, `fuel`, `body_condition`,
  `insurance_months`.
- `Facets` gains `data_as_of` (newest `fetched_at`); `cities` and `categories` respect
  `?category=`.
- Traefik: `/api/v1/assistant` and `/api/v1/estimates` get rate-limited routers
  (average 5, burst 10) with explicit priorities above the general `/api` router.
- **Phone numbers are masked in `ListingDetail.description`.** Real Divar descriptions
  contain sellers' phone numbers; the API replaces Iranian mobile/landline patterns
  (Persian, Arabic-Indic or ASCII digits, with or without separators) with
  «شماره در آگهی دیوار», and the listing page links to the original ad via `token`.
  Masking happens in the service layer when building `ListingDetail`; stored data is
  unchanged.

## 4. Frontend data layer

### 4.1 `src/lib/api/`

```
types.ts   hand-written mirrors of the backend schemas (ListingCard, ListingDetail,
           PriceBreakdown, SearchResponse, IntentRead, Facets, ModelStats,
           CatalogSuggestion, EstimateRequest/Response, AssistantRequest/Response,
           ApiErrorBody). No codegen dependency.
client.ts  apiGet<T>(path, params) / apiPost<T>(path, body) → parsed JSON, or throws
           ApiError { status, code, message, details } built from the error envelope.
base.ts    server: process.env.API_INTERNAL_URL (http://backend:8000); browser: "" (same
           origin via Traefik). The /api/v1 prefix is added here only.
useApi.ts  client hook: useApi(key, fetcher) → { data, error, loading, retry }, using
           AbortController so a superseded request never overwrites a newer one.
```

- Every fetch uses `cache: "no-store"`; Redis already caches rankings server-side.
- `NEXT_PUBLIC_API_URL` is removed from `example.env`; `API_INTERNAL_URL` is added
  (server-only).

### 4.2 Deleted (the backend owns it)

`lib/listings.ts` (generator, `LISTINGS`, `findListing`, `listingsOfModel`); the
synthetic catalog in `lib/catalog.ts` (`MODELS`, `CITIES`, `BODIES`, `ISSUES`, `SNIPS`,
`POSTED`, `IMAGES`, `NOW_YEAR`); `lib/estimate.ts`; `lib/modelStats.ts`;
`lib/assistant.ts`; from `lib/search.ts`: `parseQuery`, `filterListings`,
`sortListings`, `matchesParsed`, `chipsOf`, `alertMatches`; from `lib/pricing.ts`:
`priceModel` and the tag logic in `summaryOf`. Colour constants move to `lib/theme.ts`.

### 4.3 Kept and rewritten against API types

- `view.ts` — `cardOf(card: ListingCard): CardView`, so all card components are
  unchanged. Title `trim ?? title`; meta line = year · km · city/district · gearbox (cars)
  or engine cc from `attributes` (motorcycles); verdict from the API `verdict` enum.
- `pricing.ts` — `verdictStyle(verdict)`, `diffText(diff_pct)`, `scoreColor`,
  `breakdownRows(detail)` (base, km, insurance rows only; basis in words, e.g.
  «میانهٔ ۵ آگهی همین تیپ و سال»), `summaryOf(detail)` from real fields only.
- `compare.ts` — `compareRows(cards)`: price, verdict/diff, deal score, year, km,
  gearbox, body, insurance, city; "best" cell per row as today. No tag row.
- `specs.ts` (new) — `specsOf(detail)`: per-category rows from typed fields plus
  `attributes` (engine cc, ownership, exchange, technical inspection); empty rows hidden.
- `format.ts` — unchanged, plus `formatToman(amount)` (same millions/billions wording as
  the backend labels) and `relativeTime(postedAt, dataAsOf)`.
- `search.ts` — filter-sheet state only: `SearchOverrides`, `activeFilterCount`,
  `paramsToQuery` / `queryToParams`.

### 4.4 AppState

- localStorage key becomes `torobcar:v2`; the old key (synthetic ids) is ignored.
- `compare` (≤ 3) and `saved` stay id arrays.
- `alerts: { title, params: SearchParams, threshold }[]`; match counts are fetched live
  (`/search?…&price_max=threshold&page_size=1` → `total`) when the dropdown opens.
- `sendChat` posts to `/assistant`; `ChatMessage` carries `listings: ListingCard[]`.

## 5. Screens

| Route | Kind | Data |
|---|---|---|
| `/` | server | `/facets`: total ads, model count, «به‌روزرسانی: …» from `data_as_of`, per-category counts linking to `/results?category=…`; example chips are real queries that return results |
| `/results` | client island | URL-driven `/search`; chips from `intent.chips` (+ a «تفسیر: قواعد» hint when `parsed_by=rules`); filter sheet from `/facets?category=` (category selector, top models and cities with counts, gearbox only for cars or no category); sorts map to `relevance/deal/price/km/newest`; exact matches, then an «آگهی‌های مشابه» divider before near-misses with their labels; "بیشتر" appends the next page; map pins from loaded cards; one `/models/{model}/stats` range card per resolved model, its bar drawn on an axis spanning the lowest `price_min` to the highest `price_max` among the shown models; "save & alert" stores params + threshold |
| `/listing/[id]` | server, dynamic | detail + `/similar` in parallel; 404 → `notFound()`; real gallery; price card with the Divar link (`token`), compare/save toggles; per-category specs grid; breakdown card; summary from real fields; seller text; `SellerAssessmentCard` removed |
| `/model/[model]` | server, dynamic | `/models/{model}/stats`: header numbers, histogram, trim bars (replace `IssueBars`), top-deals list; alert threshold = 90 % of the median |
| `/compare` | client | ids → `/listings?ids=`; compare table |
| `/estimate` | client | model type-ahead via `/catalog/suggest`; year select from the model's stats range; km; insurance months; body condition only for motorcycle/heavy; optional asking price → `POST /estimates`; result card, breakdown, similar |
| chat panel | client (layout) | `POST /assistant` with history + compare ids; text + inline `MiniListing` cards; avatar states unchanged |
| alerts dropdown | client | live match count per alert on open |

`generateStaticParams` is removed from the listing and model routes; both render on
request.

## 6. Loading, errors, testing, dev workflow

### 6.1 Loading
Route `loading.tsx` skeletons for the server-rendered routes; inline skeletons, spinner
or the avatar "thinking" state for islands. Superseded searches are aborted.

### 6.2 Errors
- 404 on detail/model → `notFound()` (existing Persian not-found page).
- 422 `invalid_search` / `no_comparables` → the envelope message inline; the form stays
  editable.
- 503 or network failure → route `error.tsx` «سرویس جست‌وجو در دسترس نیست» with retry;
  in islands an inline banner with retry.
- The UI never falls back to made-up data. Screens branch on `ApiError.code`, never on
  message text. Chat failures render as an assistant bubble.

### 6.3 Testing
- **Backend (pytest, fixture DB):** stats (bucket counts sum to the priced count; suspect
  prices excluded; 404), suggest (typo tolerance, category filter, 10-row cap),
  estimates (same numbers as the ingest estimator for the same input; 422 without
  comparables), phone masking (Persian/ASCII digits, separators, landline and mobile
  forms; ordinary numbers like prices and km untouched), assistant (rules path with no key; LLM path via `FunctionModel` calling
  the search tool; `ALLOW_MODEL_REQUESTS=False`), facets (`data_as_of`, category-scoped
  cities), card fields. Golden queries stay green.
- **Frontend (`bun test`):** JSON fixtures captured from the running API into
  `src/lib/api/__fixtures__/` (descriptions truncated, no personal data); tests for
  `cardOf`, `breakdownRows`, `compareRows`, `specsOf`, `relativeTime`, `formatToman`,
  and the API client with a stubbed `fetch` (envelope → `ApiError`, server vs browser
  base URL). Synthetic-generator, `scriptedReply`, `filterListings` and client
  `estimate` tests are removed with their subjects. `bun run lint` and
  `bunx tsc --noEmit` clean.
- **Acceptance:** `.scripts/smoke.sh` drives agent-browser (headed on demand) through
  the running stack: home stats → NL search → near-miss labels → a listing → similar →
  compare two → an estimate → a chat question → a 422 message. Not in CI (no stack).

### 6.4 Dev workflow
The frontend needs the backend: develop with `./.scripts/dev.sh` (Traefik, one origin,
hot reload for both apps). `bun run dev` alone renders every screen in its
"service unavailable" state; documented in the README. No mock server.

## 7. Done means

- No import of synthetic data remains: `grep -rE "LISTINGS|generateListings|MODELS\b"
  frontend/src` finds nothing.
- Every route renders real data on the running stack; the smoke script passes.
- Backend: `uv run pytest`, ruff, black clean; frontend: `bun test`, `bun run lint`,
  `bunx tsc --noEmit` clean; both images build.
- Only Traefik publishes a host port; new routers are rate-limited.
