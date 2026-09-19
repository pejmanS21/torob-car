# ترب‌کار (Torobcar)

A Persian, RTL car-search app — search, browse, compare, and get a price
estimate for used cars. The Next.js frontend renders real crawled Divar data
served by the FastAPI search backend (see **Backend** below); nothing on screen
is synthetic.

## Getting started

The full stack (Traefik + backend + frontend + Postgres + Redis) is the
supported way to run everything locally — the frontend needs the backend:

```bash
cp example.env .env
./.scripts/setup.sh   # deps for both apps, .env, pre-commit hooks
./.scripts/dev.sh      # docker compose up, hot reload
```

The app runs at `http://localhost` (Traefik, port 80).

`bun run dev` alone (no backend) renders every screen in its «سرویس جست‌وجو در
دسترس نیست» state — there is no mock server. Server Components reach the backend
at `API_INTERNAL_URL` (`http://backend:8000` in Compose); the browser calls
`/api/v1` on the same origin through Traefik.

### Acceptance smoke test

With the stack running (and the CSV ingested), drive the real UI end to end with
[agent-browser](https://github.com/vercel-labs/agent-browser):

```bash
./.scripts/smoke.sh              # home → search → listing → compare → estimate → chat → 422
HEADED=1 ./.scripts/smoke.sh     # watch it
```

## Scripts (run from `frontend/`)

```bash
bun test              # run the unit test suite (src/lib)
bun run lint          # ESLint
bunx tsc --noEmit     # TypeScript type check
bun run build         # production build
bun run start         # serve the production build
```

## Backend

`backend/` is a FastAPI + PostgreSQL (pgvector) + Redis search service. It parses
free-text Persian queries into a typed `SearchIntent` (Pydantic AI, with a
deterministic rules-based fallback), ranks listings against that intent, and
estimates a fair price per listing from comparable sales. See `CLAUDE.md` for
full architecture and conventions.

```bash
./.scripts/setup.sh                          # install backend + frontend deps
./.scripts/dev.sh                             # bring up the full stack
./.scripts/ingest.sh assets/<csv>             # load a crawl CSV (divar, bama, karnameh, hamrah-mechanic)
```

### API (`/api/v1`)

| Endpoint | Purpose |
|---|---|
| `GET /search` | `q`, plus explicit filter params `category, models, cities, year, price_max, km_max, gearbox, only_below, sort, page, page_size` (≤ 50). Explicit params override what was parsed from `q`. `models` takes `model` values as returned by `/facets` (resolved at model level); `year` sets both `year_min` and `year_max` |
| `GET /listings/{id}` | `ListingDetail` |
| `GET /listings?ids=` | batch fetch for the compare page (≤ 4 ids) |
| `GET /listings/{id}/similar?limit=6` | same ranker, intent derived from the listing |
| `GET /facets?category=` | categories, top brands/models, cities (scoped by `category`) with counts, `model_count`, `data_as_of`; cached under `data_version` |
| `GET /models/{model}/stats` | count, year range, price median/min/max, 8-bucket histogram, per-trim counts, top deals |
| `GET /catalog/suggest?q=&category=` | ≤ 10 typo-tolerant `{brand, model, trim, category, count}` rows; empty `q` = largest trims |
| `POST /estimates` | `{category, trim, year, km, insurance_months, body_condition, asking_price}` → estimate, IQR band, breakdown, asking verdict, similar; 422 `no_comparables` |
| `POST /assistant` | `{messages (≤ 10, ≤ 500 chars), compare_ids}` → `{text, listings, answered_by}`; LLM agent with search/compare tools, rules fallback |
| `GET /health` · `GET /health/ready` | liveness · readiness (Postgres + Redis ping) |

### Tests

```bash
./.scripts/test-db.sh          # start the throwaway Postgres tests need
cd backend && uv run pytest
```

### LLM

Search works with no LLM key set — it falls back to a deterministic rules
parser (`parsed_by: "rules"` in the response). Set `LLM_API_KEY` in `.env` to
use Gemini (development default) or any OpenAI-compatible API in production.

## Notes

- `prototype/Torobcar.dc.html` is the visual design reference the UI was
  ported from; it is not part of the shipped app.
- The avatar rendered in the chat panel uses `@bible-strong/avatar-web`,
  which is licensed AGPL-3.0-only.
