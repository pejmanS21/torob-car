# Torobcar Frontend — Design

Date: 2026-09-18
Status: approved in brainstorming, pending written-spec review

## Goal

Implement the Claude Design prototype `prototype/Torobcar.dc.html` (desktop) and
its mobile rendering (`prototype/Torobcar Mobile.dc.html`) as a real Next.js
frontend under `frontend/`. Frontend only, sample data only, installable as a PWA.

The prototype is the visual source of truth: colors, spacing, radii, copy, and
behavior are ported from it unless this document says otherwise.

## Decisions

| Topic | Decision |
| --- | --- |
| Data | Port the prototype's seeded synthetic generator (4 models, 3 cities). The Divar CSV in `assets/` is not used. |
| Assistant | Scripted replies only (port of `scriptedReply`). No LLM call, no API client. |
| PWA | Installable (manifest, icons, theme color, safe-area insets). No service worker, no offline. |
| Routing | Real App Router routes, not hash routing. |
| Styling | CSS Modules + tokens in `globals.css`. No Tailwind, no UI kit. |
| Font | Vazirmatn via `next/font/google` (as in the prototype). IRANYekan is licensed and not used. |
| Mobile | One responsive app; mobile layout below 768px. The iOS-frame embed mode is dropped. |

## Stack

- Next.js (App Router), TypeScript strict, Bun, `output: "standalone"` in `next.config.ts`.
- `<html lang="fa" dir="rtl">`.
- Runtime dependencies beyond Next/React: `leaflet`, `@bible-strong/avatar-web` (pinned to `0.1.0`). Dev: `@types/leaflet`.
- Tests: `bun test`. Lint: `bun run lint` (ESLint, Next config).

## Routes

| Route | Screen |
| --- | --- |
| `/` | Home: hero, natural-language search box, 4 example chips, stats line |
| `/results?q=` | Results: filters, parsed chips, toolbar, model cards, listing grid, empty state |
| `/model/[id]` | Model: header + alert button, price histogram, frequent notes, ranked rows, map |
| `/listing/[id]` | Listing: gallery, summary, specs, seller text, map, side column (price/actions, seller assessment, verdict breakdown, similar) |
| `/compare` | Compare table for up to 3 listings, empty state |
| `/estimate` | Estimate form + result card, breakdown, similar listings |

Unknown `model`/`listing` ids call `notFound()`.

The header search bar is shown on every route except `/`. Submitting any search
navigates to `/results?q=<text>`. The "جست‌وجو" nav tab is active on `/results`,
`/model/*`, and `/listing/*`.

## Logic — `frontend/src/lib/` (pure, no React)

Ported from the prototype script with types added; behavior unchanged except where noted.

- `format.ts` — `fa`, `en`, `num` (Persian digit conversion and grouping).
- `catalog.ts` — `MODELS`, `BODIES`, `CITIES`, `ISSUES`, `SNIPS`, `COLORS`, `POSTED`, `IMAGES`, `NOW_YEAR`, verdict colors.
- `listings.ts` — seeded LCG `rng`, `generateListings()`, exported `LISTINGS` (generated once at module load) and `findListing(id)`.
  - **Change from prototype:** `token` is drawn from the seeded RNG instead of `Math.random()`, so server and client output are identical (no hydration mismatch).
- `pricing.ts` — `priceModel`, `verdictOf` (≤ −5% cheaper, ≥ +6% above, else fair), `diffText`, `scoreColor`, `breakdownRows`, `summaryOf`.
- `search.ts` — `parseQuery`, `chipsOf`, `filterListings(listings, filters)`, `sortListings(list, sort)`, `filtersFromQuery(parsed)`, default filter constants (max price 1400, max km 250).
- `assistant.ts` — `scriptedReply(text, listings, compareIds)` returning `{ text, cardIds? }`.
- `types.ts` — `Listing`, `CarModel`, `Filters`, `ParsedQuery`, `Verdict`, `SortKey`, `ChatMessage`, `PriceAlert`.

## State — `frontend/src/state/AppState.tsx`

One client context provider mounted in the root layout:

- `compare: string[]` (max 3), `saved: string[]`, `alerts: PriceAlert[]`, `loggedIn: boolean`
- `chatOpen`, `chatMessages`, `chatBusy`
- `toast: string` with a `showToast(text)` helper (auto-clears after 2.2s)

`compare`, `saved`, `alerts`, and `loggedIn` persist to `localStorage`, read after
mount to keep SSR output stable. Results filters and the estimate form are local
state of their pages; results filters are seeded from `?q=` via `parseQuery`.

Adding an alert while logged out opens the bell dropdown and shows the
"log in first" toast, as in the prototype. Login is a toggle (fake user "علی").

Chat: sending a message appends the user message, sets busy, waits a short fixed
delay (so the "thinking" animation is visible), then appends the scripted reply.
Avatar animation: `thinking` while busy, `happy` for 2.5s after a reply, else `idle`.

## Components — `frontend/src/components/`

Each with a co-located `.module.css`.

- Shell: `Header` (logo, desktop nav, header search, assistant button, bell + alerts dropdown, login), `MobileSearchBar`, `MobileTabBar`, `Footer`, `Toast`.
- Assistant: `ChatPanel`, `Avatar` (client wrapper around `createAvatar`; props `size`, `body`, `anim`; SVG fallback from `avatar-host.js` on load failure; destroys on unmount).
- Listings: `ListingCard` (grid), `ListingRow` (model page), `MiniListing` (similar/chat/estimate), `VerdictBadge`, `ScoreBar`.
- Results: `FiltersPanel` (sidebar on desktop, bottom sheet + backdrop on mobile), `ParsedChips`, `ResultsToolbar`, `ModelCard`.
- Model: `PriceHistogram`, `IssueBars`.
- Listing: `Gallery`, `SummaryCard`, `SpecsGrid`, `SellerAssessment`, `BreakdownCard`.
- Compare: `CompareTable`.
- Estimate: `EstimateForm`, `EstimateResult`.
- Map: `ListingsMap` (Leaflet, OSM tiles, circle markers colored by verdict, tooltip, click → listing; single-listing mode draws a 900m radius circle at zoom 13). Imported with `next/dynamic` and `ssr: false`.

Pages that need interactivity are client components; the root layout and
`not-found` stay server components.

## Responsive and PWA

- The prototype's `[data-tk-root=mobile]` rules become `@media (max-width: 767px)`:
  56px header, desktop nav / header search / assistant button / footer hidden,
  sticky mobile search bar, single-column grids, 2×2 results toolbar, filters as a
  bottom sheet (max-height 85vh, "show N listings" footer button), full-width chat
  panel, 5-item bottom tab bar (home, search, assistant, compare, estimate), map
  cards static with 260px height.
- Safe areas use `env(safe-area-inset-top/bottom)` instead of the prototype's
  `--tk-top`/`--tk-bot` iOS-frame variables. Body scroll is locked while the filter
  sheet is open.
- `app/manifest.ts`: name/short_name «ترب‌کار», `display: "standalone"`, `dir: "rtl"`,
  `lang: "fa"`, `theme_color: "#d9232e"`, `background_color: "#f6f7f9"`, icons 192 and 512.
- Icons generated once from `prototype/assets/logo.png` into `frontend/public/icons/`
  plus `apple-touch-icon`. `viewport` export sets `themeColor` and `viewportFit: "cover"`.

## Assets

- `prototype/assets/logo.png` → `frontend/public/logo.png`.
- `prototype/assets/strobi.avatar.json` → `frontend/public/strobi.avatar.json` (body color overridden to `#68b828` at runtime, as in the prototype).
- Listing photos remain Divar CDN URLs, rendered as CSS background images / plain `<img>`; `next/image` is not used, so no remote-pattern config.
- Leaflet CSS imported from the `leaflet` package, not unpkg.

## Error handling

- Unknown model/listing id → `notFound()` with a Persian not-found page linking home.
- Avatar module or JSON fails to load → SVG fallback, warning logged.
- No results / empty compare → the prototype's dashed empty states.
- `localStorage` unavailable or malformed → start from defaults.

## Testing

`bun test` over `src/lib` only:

- `parseQuery`: the 4 home example queries; Persian digits; Arabic ي/ك normalization; «میلیارد» vs «میلیون»; gear and year extraction.
- `priceModel`: `est` equals `base × bodyF × kmF × insF × gearF`; each part equals `base × (factor − 1)`; km factor clamps at both ends; automatic premium (1.06) only for models with two gearboxes.
- `verdictOf` thresholds at −5 / +6.
- `generateListings` is deterministic across calls and ids are unique.
- `filterListings` / `sortListings` for each filter and sort key.
- `scriptedReply`: no-criteria prompt, no-match, match with 3 cards, compare question with ≥2 compared cars.

No component tests. Done means `bun test`, `bun run lint`, and `bun run build`
pass, and every route has been checked in a browser at desktop width and 390px
against the prototype.

## Out of scope

Backend, Docker, NGINX, CI workflows, real authentication, LLM-backed chat,
the Divar CSV, service worker / offline, dark mode.

## Notes

- `@bible-strong/avatar-web` is AGPL-3.0. Acceptable for this prototype; needs a
  license review before any public release.
- `prototype/` stays in the repo as the visual reference and is not imported by the app.
