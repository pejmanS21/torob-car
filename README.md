# ترب‌کار (Torobcar)

A Persian, RTL car-search app — search, browse, compare, and get a price
estimate for used cars. The frontend UI still runs on synthetic data generated
in `src/lib` (it is not yet wired to the API); a real FastAPI search backend
now exists alongside it and is runnable and tested on its own — see
**Backend** below.

## Getting started

The full stack (Traefik + backend + frontend + Postgres + Redis) is the
supported way to run everything locally, though the frontend does not call
the backend API yet:

```bash
cp example.env .env
./.scripts/setup.sh   # deps for both apps, .env, pre-commit hooks
./.scripts/dev.sh      # docker compose up, hot reload
```

The app runs at `http://localhost` (Traefik, port 80).

To run just the frontend against its own dev server (no backend):

```bash
cd frontend
bun install
bun run dev
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
./.scripts/ingest.sh assets/<csv>             # load a Divar CSV into the database
```

### API (`/api/v1`)

| Endpoint | Purpose |
|---|---|
| `GET /search` | `q`, plus explicit filter params `category, models, cities, year, price_max, km_max, gearbox, only_below, sort, page, page_size` (≤ 50). Explicit params override what was parsed from `q`. `models` takes `model` values as returned by `/facets` (resolved at model level); `year` sets both `year_min` and `year_max` |
| `GET /listings/{id}` | `ListingDetail` |
| `GET /listings?ids=` | batch fetch for the compare page (≤ 4 ids) |
| `GET /listings/{id}/similar?limit=6` | same ranker, intent derived from the listing |
| `GET /facets?category=` | categories, top brands/models, cities — each with counts; cached under `data_version` |
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
