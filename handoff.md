# Handoff — Torobcar

_Last updated: 2026-09-19_

## 1. Goal

Build Torobcar, a Persian (RTL) used-car search and price-intelligence app over crawled Divar listings
(`assets/divar-vehicles-sep-17-20_32.csv`). The core problem is **ranking and search**: find the listings
closest to what the user asked for, including near-misses.

- **Spec 1 (done):** backend search core.
  - Stack: FastAPI, Postgres 18 with `pg_trgm`, Redis cache, Traefik as the only public port.
  - Natural-language search: Pydantic AI turns free text into a typed `SearchIntent` (Gemini in dev, any
    OpenAI-compatible API in prod; the rules parser takes over when there is no API key).
  - Candidate rows come from SQL; a Python ranker orders them with soft ranking and near-miss labels.
  - SonarQube Community Build runs locally.
- **Spec 3 (done):** wire the Next.js frontend to the API so it shows only real crawled data.
  - Server Components fetch first; client "islands" handle interactivity.
  - All categories are treated equally.
  - The UI never shows synthetic data.

## 2. Current state

- **Code is on GitHub:** https://github.com/pejmanS21/torob-car (**private**). Pushed branches: `main`,
  `feat/frontend`, `feat/backend-search-core`.
- **Where the work lives:** all Spec 1 and Spec 3 work is on `feat/backend-search-core` at HEAD `ef11cb6`.
  `feat/frontend-api-wiring` was fast-forward merged into it and deleted.
- **No pull request is open yet.** The target is undecided: `feat/frontend` or `main`.
- **Tests:**
  - backend 229 passed;
  - frontend 28 passed;
  - `bunx tsc --noEmit`, `bun run lint`, `ruff` and `black` are clean;
  - gitleaks: no leaks across 65 commits.
- **Reviews:** the final whole-branch review found 0 Critical, 3 Important and 8 Minor issues. All 3
  Important issues and 7 Minor issues are fixed in `ef11cb6`, and a scoped re-review confirmed the fixes.
- **Running stack:**
  - It still runs the Task 13 build, which does **not** include the `ef11cb6` fixes.
  - It holds 14,652 ingested ads.
  - The app is at http://localhost.
- **Specs and plans:**
  - `docs/superpowers/specs/2026-09-18-torobcar-frontend-api-wiring-design.md`
  - `docs/superpowers/plans/2026-09-18-torobcar-frontend-api-wiring.md`
- **Code graph:** refreshed with `graphify update .` (1,838 nodes).

## 3. Active files

**Backend (`backend/`)**

| Area | Files |
|------|-------|
| Endpoints | `api/v1/endpoints/{search,listings,facets,models,catalog,estimates,assistant}.py` |
| Services | `services/{listing_views,model_stats_service,catalog_service,estimate_service,assistant_service}.py` |
| Repositories | `repositories/*` (`count_by_city`, `load_model_rows`, `find_model`, `suggest`, `find_trim`, `get_by_ids`) |
| Ranking | `ranking/{weights,model_stats,estimator}.py` — the verdict thresholds live **only** in `weights.py` |
| LLM | `llm/assistant_agent.py` — agent is injected via `dependencies/providers.py` (`AssistantAgentDep`) |
| Core | `core/phone.py` (phone masking); `core/config.py` (`assistant_timeout_seconds=20`) |

**Frontend (`frontend/src/`)**

| Area | Files |
|------|-------|
| API layer | `lib/api/{types,base,client,useApi}.ts` — `types.ts` mirrors `backend/schemas/*.py` by hand |
| Libs | `lib/{compare,pricing,view,search,format,labels,specs,theme}.ts` |
| Routes | `app/{page,results/page,listing/[id]/page,model/[model]/page,compare,estimate}` |
| Components | `components/{ResultsScreen,FiltersPanel,ModelCard,ListingScreen,CompareTable,ChatPanel,EstimateForm,…}.tsx` |
| State | `state/AppState.tsx` (localStorage key `torobcar:v2`) |

**Infra and docs**

- `.docker/compose.yml`: Traefik labels, including the `api-assistant` rate limit (5/s, burst 10).
- `.docker/frontend.Dockerfile`: the build runs on node, not bun.
- `.scripts/smoke.sh`, `example.env`, `README.md`, `CLAUDE.md`.

## 4. Changes made

**Spec 3 backend**

- Phone numbers in descriptions are masked (`core/phone.py`).
- `ListingCard` gained lat/lng, gearbox, fuel, body condition and insurance months.
- Facets gained `data_as_of` and `model_count`.
- New endpoints:
  - model stats, using inclusive quantiles for the histogram;
  - catalog suggest/trim;
  - `/estimates`, which shares estimator code with ingest;
  - `/assistant`, a Pydantic AI agent with tools and a fallback when the LLM fails.

**Spec 3 frontend**

- Added the typed API client and `useApi`, which uses AbortController.
- All screens are rewired to the API.
- Mock data modules were deleted (`listings.ts`, `catalog.ts`, `estimate.ts`, `modelStats.ts`, `assistant.ts`).
- Added `loading.tsx` and `error.tsx` files.
- A 404/422 on the listing or model page renders `notFound()`.
- The route `model/[id]` was renamed to `model/[model]`.
- Server pages call `await connection()` so Next doesn't fetch from the API at build time.

**Infra**

- The browser calls `/api/v1` on the same origin; the server uses `API_INTERNAL_URL`.
- `NEXT_PUBLIC_API_URL` was removed.
- The assistant and estimate routes are rate-limited.
- Added the agent-browser smoke script `.scripts/smoke.sh`.

**Final-review fixes (`ef11cb6`)**

- The mobile filter sheet's open state moved up to `results/page.tsx`, so it no longer closes on every tap.
- The listing detail page reports the listing's own lat/lng, never the city centre. Cards still fall back to the city.
- `compare.ts` uses the card's `verdict` instead of hard-coded −5/+6 thresholds, with a new test.
- IDs in API paths are encoded with `encodeURIComponent`.
- The price bar is skipped when a model has no price range.
- A search retry now resets pagination.
- `smoke-fail.png` was added to `.gitignore`.
- An unused `MILLION` constant was removed.
- The assistant's `compare_listings` tool is capped at `MAX_COMPARE_IDS`.

## 5. Failed attempts

- **`bun run build` in Docker** segfaults (Next 16 + Turbopack under Bun's Node shim, linux/arm64).
  - The fix: the builder and runtime stages use `node:22-slim` and run `node node_modules/.bin/next build`.
  - Retry bun when a new Bun release fixes the crash.
- **Smoke script clicked «بیشتر» only once.** On real data the similar-ads divider needs more pages, so it failed.
  - The fix: a bounded loop of at most 5 clicks.
- **Assistant agent was built inside the service**, not injected through `Depends`.
  - The test override did nothing, and a real `LLM_API_KEY` would have broken the test suite.
  - The fix: injection through `providers.py`.
- **Exclusive quantiles** extrapolated the histogram edges for rare models. The fix: `method="inclusive"`.
- **`Promise.all` on the listing page** meant a failure in the similar-ads call took down the whole page.
  - The fix: fetch detail first, then similar; a similar-ads failure only hides that section.
- **Pages were prerendered at build time.** The listing and model pages lacked `await connection()` and
  hit the API during the build. The fix: add the call.
- **A fix introduced a lint error.** It broke the `prefer-const` rule, and the re-reviewer missed it;
  the controller's own lint run caught it.
- **A reviewer claimed the proxy is NGINX.** Rejected: `.docker/` has no NGINX files, and the stack uses Traefik.
- **Environment limits:**
  - Reading `.env` and `curl` to localhost are denied. Use agent-browser, or `docker compose exec -T backend python -c …`.
  - One Haiku implementer used the wrong commit trailer; it was fixed with an amend.

## 6. Next step

1. **Open a pull request** for `feat/backend-search-core`. Target `feat/frontend` or `main` (you decide):
   `gh pr create --base <target> --head feat/backend-search-core`.
2. **Rebuild the stack** to pick up `ef11cb6`, then run the smoke check:
   `docker compose -f .docker/compose.yml up -d --build && ./.scripts/smoke.sh`
3. **Run the first SonarQube scan.** Log in to the local SonarQube, create a token and put it in
   `.env` as `SONAR_TOKEN`, then run `./.scripts/sonar.sh`.
4. **Add an `LLM_API_KEY`** (Gemini) and check the assistant against a real model. So far it has only run
   against a test model (`FunctionModel`). Then run `uv run python -m llm.eval`.
5. **Bump `CURRENT_YEAR = 1405`** in `frontend/src/components/FiltersPanel.tsx` before Nowruz 1406.
6. **Optional minor fixes:**
   - debounce the type-ahead and add ARIA combobox roles;
   - use `Promise.allSettled` in `AlertsDropdown`;
   - prune stale compare ids;
   - show a toast when `saveSearch` does nothing.
7. **Optional repo settings:** make the repo public if you want, and set `DOCKERHUB_USERNAME` and
   `DOCKERHUB_TOKEN` as repository secrets so `docker-publish.yml` can push images.
