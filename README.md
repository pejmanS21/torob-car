# ترب‌کار (Torobcar)

A Persian, RTL car-search frontend prototype — search, browse, compare, and
get a price estimate for used cars.

## Getting started

```bash
cd frontend
bun install
bun run dev
```

The app runs at `http://localhost:3000`.

## Scripts (run from `frontend/`)

```bash
bun test              # run the unit test suite (src/lib)
bun run lint          # ESLint
bunx tsc --noEmit     # TypeScript type check
bun run build         # production build
bun run start         # serve the production build
```

## Notes

- All data (listings, prices, models) is synthetic, generated in `src/lib`
  for demo purposes — there is no backend or live API.
- `prototype/Torobcar.dc.html` is the visual design reference the UI was
  ported from; it is not part of the shipped app.
- The avatar rendered in the chat panel uses `@bible-strong/avatar-web`,
  which is licensed AGPL-3.0-only.
