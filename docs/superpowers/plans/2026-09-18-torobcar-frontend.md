# Torobcar Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Claude Design prototype `prototype/Torobcar.dc.html` as an installable, responsive, RTL Next.js app under `frontend/`, running entirely on seeded synthetic data.

**Architecture:** All prototype logic is ported into pure, typed, unit-tested modules in `frontend/src/lib/`. One client context (`AppState`) holds cross-route state (compare, saved, alerts, login, chat, toast). Each prototype screen becomes an App Router route rendered by small presentational components styled with CSS Modules.

**Tech Stack:** Next.js (App Router, latest) · React 19 · TypeScript strict · Bun (package manager + `bun test`) · CSS Modules · Leaflet · `@bible-strong/avatar-web@0.1.0`.

**Spec:** `docs/superpowers/specs/2026-09-18-torobcar-frontend-design.md` — read it before starting. Visual source of truth: `prototype/Torobcar.dc.html` (line numbers below refer to this file).

## Global Constraints

- All commands run from `frontend/` with **bun** (`bun add`, `bun run`, `bun test`, `bunx`). Never npm/yarn/pnpm. Commit the lockfile bun generates; never edit it by hand.
- TypeScript strict, no `any`. Small single-purpose functions, intention-revealing names, no magic values.
- `next.config.ts` sets `output: "standalone"`.
- `<html lang="fa" dir="rtl">`; font Vazirmatn via `next/font/google`, weights 400/500/600/700/800.
- Styling: CSS Modules + tokens in `globals.css`. No Tailwind, no UI kit. Mobile layout = `@media (max-width: 767px)`.
- Runtime deps beyond Next/React: only `leaflet` and `@bible-strong/avatar-web@0.1.0` (exact). Dev: `@types/leaflet`, `@types/bun`.
- Listing photos are Divar CDN URLs rendered as CSS `background-image`; do not use `next/image`.
- No service worker, no API client, no LLM call, no use of `assets/*.csv`.
- All user-facing copy is Persian, copied verbatim from the prototype. Numbers shown to users go through `fa()`/`num()`.
- Conventional commits, each ending with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- A task is done only when `bun test`, `bun run lint`, and `bunx tsc --noEmit` pass.

## Porting Convention (applies to every UI task)

Presentational markup is a mechanical port of the prototype lines cited in the task:

1. `<sc-if value="{{ x }}">` → `{x && (...)}`; `<sc-for list="{{ xs }}" as="x">` → `xs.map(...)` with a stable `key`.
2. Each element's inline `style="..."` becomes a class in the component's `.module.css` with **identical declarations**. `style-hover="..."` → `.cls:hover { ... }`; `style-focus` → `:focus-within`.
3. Values that are `{{ bindings }}` inside a style (verdict color, bar width, selected border/bg) stay as a React inline `style` prop; everything static goes to CSS.
4. Hard-coded colors that match a token in `globals.css` use the `var(--…)` token.
5. `<a href="#/x" onClick>` → `<Link href="/x">`. `#/results?q=` → `/results?q=`. `#/model/ID` → `/model/ID`. `#/listing/ID` → `/listing/ID`.
6. Mobile rules: every `[data-tk-root=mobile] [data-tk=NAME]{…}` rule in prototype lines 28–81 moves into the owning component's module inside `@media (max-width: 767px)`, dropping `!important` where specificity allows. Ignore all `[data-tk-embed=true]` rules and the `--tk-top/--tk-hdr/--tk-bot/--tk-tab` variables (use `env(safe-area-inset-*)`, header height 56px, tab bar 64px).

Worked example — Task 8 gives `ListingCard.tsx` + `ListingCard.module.css` in full; follow that shape everywhere.

## File Structure

```
frontend/
├── next.config.ts                 output: "standalone"
├── public/ logo.png, strobi.avatar.json, icons/{icon-192,icon-512,apple-touch-icon}.png
└── src/
    ├── app/
    │   ├── layout.tsx             html/rtl/font, AppStateProvider, shell
    │   ├── globals.css            tokens + resets + keyframes
    │   ├── manifest.ts            PWA manifest
    │   ├── not-found.tsx          Persian 404
    │   ├── page.tsx               Home
    │   ├── results/page.tsx       Suspense + useSearchParams → ResultsScreen
    │   ├── model/[id]/page.tsx    server: validate id → ModelScreen
    │   ├── listing/[id]/page.tsx  server: validate id → ListingScreen
    │   ├── compare/page.tsx
    │   └── estimate/page.tsx
    ├── lib/                       pure logic, no React (+ *.test.ts beside each)
    │   ├── types.ts format.ts catalog.ts pricing.ts listings.ts
    │   ├── search.ts view.ts assistant.ts modelStats.ts compare.ts estimate.ts
    ├── state/AppState.tsx         context + localStorage persistence
    ├── types/avatar-web.d.ts      only if the package ships no types
    └── components/                one folder-less file pair per component: X.tsx + X.module.css
```

---

### Task 1: Scaffold the app, tokens, and root layout

**Files:**
- Create: `frontend/` (via create-next-app), `.gitignore` (repo root)
- Modify: `frontend/next.config.ts`, `frontend/src/app/layout.tsx`, `frontend/src/app/globals.css`, `frontend/src/app/page.tsx`
- Delete: `frontend/src/app/page.module.css`, default SVGs in `frontend/public/`
- Copy: `prototype/assets/logo.png` → `frontend/public/logo.png`; `prototype/assets/strobi.avatar.json` → `frontend/public/strobi.avatar.json`

**Interfaces:**
- Produces: CSS tokens `--red --red-dark --red-soft --red-ink --ink --ink-2 --muted --faint --line --line-soft --bg --surface --fill --green --green-soft --amber --amber-soft --orange --orange-soft`; keyframes `tk-pop`, `tk-dots`, `tk-sheet`; `bun run lint|build`, `bun test`.

- [ ] **Step 1: Scaffold** (from repo root)

```bash
bunx create-next-app@latest frontend --ts --eslint --app --src-dir --no-tailwind --import-alias "@/*" --use-bun --disable-git --yes
cd frontend && bun add leaflet @bible-strong/avatar-web@0.1.0 && bun add -d @types/leaflet @types/bun
```

If create-next-app wrote `frontend/AGENTS.md` / `frontend/CLAUDE.md`, delete them (repo root `CLAUDE.md` governs).

- [ ] **Step 2: Root `.gitignore`**

```gitignore
.DS_Store
.env
node_modules/
.next/
frontend/out/
*.tsbuildinfo
assets/*.csv
```

- [ ] **Step 3: `frontend/next.config.ts`**

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = { output: "standalone" };

export default nextConfig;
```

- [ ] **Step 4: `frontend/src/app/globals.css`** (replace entirely)

```css
:root {
  --red: #d9232e; --red-dark: #b81d26; --red-soft: #fdecec; --red-ink: #b81d26;
  --ink: #172033; --ink-2: #344054; --muted: #667085; --faint: #98a2b3;
  --line: #e5e8ee; --line-soft: #f1f3f6; --line-strong: #d0d5dd;
  --bg: #f6f7f9; --surface: #fff; --fill: #f1f3f6; --photo: #eef0f3;
  --green: #15803d; --green-soft: #ecfdf3; --amber: #b45309; --amber-soft: #fffbeb;
  --orange: #c2410c; --orange-soft: #fff7ed;
  --header-h: 64px; --tabbar-h: 64px; --page-w: 1200px;
}
@media (max-width: 767px) { :root { --header-h: 56px; } }
html, body { margin: 0; background: var(--bg); color: var(--ink); direction: rtl; }
body { font-family: var(--font-vazirmatn), system-ui, sans-serif; }
* { box-sizing: border-box; }
a { color: var(--ink); text-decoration: none; }
a:hover { color: var(--red); }
button, input, select { font-family: inherit; }
button { cursor: pointer; }
input:focus, select:focus { outline: 2px solid #d9232e33; }
.leaflet-container { font-family: inherit; }
@keyframes tk-pop { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
@keyframes tk-dots { 0%, 80%, 100% { opacity: .2; } 40% { opacity: 1; } }
@keyframes tk-sheet { from { transform: translateY(40px); opacity: 0; } to { transform: none; opacity: 1; } }
```

- [ ] **Step 5: `frontend/src/app/layout.tsx`**

```tsx
import type { Metadata, Viewport } from "next";
import { Vazirmatn } from "next/font/google";
import "./globals.css";

const vazirmatn = Vazirmatn({
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-vazirmatn",
});

export const metadata: Metadata = {
  title: "ترب‌کار",
  description: "ماشین می‌خوای؟ فقط بگو چی.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#d9232e",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl" className={vazirmatn.variable}>
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 6: Placeholder home** — `frontend/src/app/page.tsx`:

```tsx
export default function HomePage() {
  return <main>ترب‌کار</main>;
}
```

Delete `src/app/page.module.css` and the default `public/*.svg`. Copy the two assets listed above.

- [ ] **Step 7: Verify**

Run: `bun run lint && bunx tsc --noEmit && bun run build`
Expected: all succeed; build output lists route `/`.

- [ ] **Step 8: Commit**

```bash
git add .gitignore frontend && git commit -m "feat(frontend): scaffold Next.js app with RTL layout and design tokens"
```

---

### Task 2: Core lib — types, format, catalog, pricing

**Files:**
- Create: `frontend/src/lib/types.ts`, `format.ts`, `catalog.ts`, `pricing.ts`
- Test: `frontend/src/lib/format.test.ts`, `frontend/src/lib/pricing.test.ts`

**Interfaces:**
- Produces: everything exported below; later tasks import these exact names.

- [ ] **Step 1: Write failing tests**

`src/lib/format.test.ts`:

```ts
import { expect, test } from "bun:test";
import { en, fa, num } from "./format";

test("fa converts latin digits to persian", () => {
  expect(fa(1403)).toBe("۱۴۰۳");
  expect(fa("l20")).toBe("l۲۰");
});
test("en converts persian and arabic digits to latin", () => {
  expect(en("۲۰۶")).toBe("206");
  expect(en("٩٠٠")).toBe("900");
});
test("num rounds, groups thousands, and uses persian digits", () => {
  expect(num(62000)).toBe("۶۲,۰۰۰");
  expect(num(669.6)).toBe("۶۷۰");
});
```

`src/lib/pricing.test.ts`:

```ts
import { expect, test } from "bun:test";
import { BODIES, MODELS } from "./catalog";
import { diffText, priceModel, scoreColor, verdictOf } from "./pricing";

const peugeot206 = MODELS.find((m) => m.id === "206")!;
const dena = MODELS.find((m) => m.id === "dena")!;
const EXPECTED_KM_FOR_1401 = 62000; // age 3 × 18000 + 8000

test("neutral inputs return the base price", () => {
  const r = priceModel(peugeot206, 1401, EXPECTED_KM_FOR_1401, BODIES[0], "دنده‌ای", 6);
  expect(r.base).toBe(670);
  expect(r.expKm).toBe(EXPECTED_KM_FOR_1401);
  expect(r.est).toBeCloseTo(670, 6);
});
test("est is the product of all factors and parts are base × (factor − 1)", () => {
  const r = priceModel(dena, 1401, 100000, BODIES[2], "اتوماتیک", 12);
  expect(r.est).toBeCloseTo(r.base * BODIES[2].f * r.kmF * r.insF * r.gearF, 6);
  expect(r.parts.body).toBeCloseTo(r.base * (BODIES[2].f - 1), 6);
  expect(r.parts.km).toBeCloseTo(r.base * (r.kmF - 1), 6);
});
test("km factor clamps at +4% and −8%", () => {
  expect(priceModel(peugeot206, 1401, 0, BODIES[0], "دنده‌ای", 6).kmF).toBeCloseTo(1.04, 6);
  expect(priceModel(peugeot206, 1401, 900000, BODIES[0], "دنده‌ای", 6).kmF).toBeCloseTo(0.92, 6);
});
test("automatic premium applies only to models with two gearboxes", () => {
  expect(priceModel(dena, 1401, EXPECTED_KM_FOR_1401, BODIES[0], "اتوماتیک", 6).gearF).toBe(1.06);
  const j4 = MODELS.find((m) => m.id === "j4")!;
  expect(priceModel(j4, 1401, EXPECTED_KM_FOR_1401, BODIES[0], "اتوماتیک", 6).gearF).toBe(1);
});
test("unknown model year throws", () => {
  expect(() => priceModel(peugeot206, 1380, 1000, BODIES[0], "دنده‌ای", 6)).toThrow(RangeError);
});
test("verdict thresholds are −5 and +6", () => {
  expect(verdictOf(-5).label).toBe("ارزان‌تر از بازار");
  expect(verdictOf(-4.9).label).toBe("قیمت منصفانه");
  expect(verdictOf(5.9).label).toBe("قیمت منصفانه");
  expect(verdictOf(6).label).toBe("بالاتر از بازار");
});
test("diffText and scoreColor", () => {
  expect(diffText(7.4)).toBe("۷٪ بالاتر از تخمین");
  expect(diffText(-12)).toBe("۱۲٪ ارزان‌تر از تخمین");
  expect(diffText(0.2)).toBe("برابر تخمین بازار");
  expect(scoreColor(70)).toBe("#15803d");
  expect(scoreColor(45)).toBe("#b45309");
  expect(scoreColor(44)).toBe("#d9232e");
});
```

- [ ] **Step 2: Run** `bun test src/lib` — Expected: FAIL (modules not found).

- [ ] **Step 3: `src/lib/types.ts`**

```ts
export type Gear = "دنده‌ای" | "اتوماتیک";
export type GearFilter = Gear | "همه";
export type SortKey = "score" | "price" | "km" | "new";

export interface CarModel { id: string; name: string; aliases: string[]; base: Record<number, number>; gears: Gear[]; }
export interface BodyCondition { name: string; f: number; }
export interface City { name: string; lat: number; lng: number; districts: string[]; }
export interface Issue { name: string; neg: boolean; }

export interface PriceParts { km: number; body: number; ins: number; gear: number; }
export interface PriceModelResult { base: number; expKm: number; kmF: number; insF: number; gearF: number; est: number; parts: PriceParts; }

export interface SellerAssessment { engine: string; chassis: string; bodyA: string; gearbox: string; }

export interface Listing {
  id: string; modelId: string; modelName: string; year: number; km: number; body: BodyCondition;
  city: string; district: string; gear: Gear; ins: number; color: string;
  price: number; est: number; diffPct: number; score: number; tags: string[]; desc: string;
  pm: PriceModelResult; extra: number; img: string; posted: string; postedIdx: number;
  photos: string[]; assess: SellerAssessment; lat: number; lng: number; token: string;
}

export interface Verdict { label: string; color: string; bg: string; icon: string; }
export interface BreakdownRow { label: string; note: string; val: string; color: string; }

export interface ParsedQuery { models: string[]; city: string | null; maxPrice: number | null; maxKm: number | null; gear: Gear | null; year: number | null; onlyBelow: boolean; }
export interface Filters { models: string[]; cities: string[]; maxPrice: number; maxKm: number; gear: GearFilter; onlyBelow: boolean; year: number | null; }

export interface ChatMessage { role: "user" | "assistant"; text: string; cardIds?: string[]; }
export interface PriceAlert { title: string; threshold: number; matches: number; }
```

- [ ] **Step 4: `src/lib/format.ts`**

```ts
const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";

export const fa = (value: string | number): string =>
  String(value).replace(/\d/g, (d) => FA_DIGITS[Number(d)]);

export const en = (value: string | number): string =>
  String(value)
    .replace(/[۰-۹]/g, (d) => String(FA_DIGITS.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(AR_DIGITS.indexOf(d)));

export const num = (n: number): string => fa(Math.round(n).toLocaleString("en-US"));
```

- [ ] **Step 5: `src/lib/catalog.ts`** — copy constants verbatim from prototype lines 610–639 with types:

```ts
import type { BodyCondition, CarModel, City, Issue } from "./types";

export const RED = "#d9232e";
export const GREEN = "#15803d";
export const AMBER = "#b45309";
export const ORANGE = "#c2410c";
export const NOW_YEAR = 1404;

const DIVAR_PHOTO_BASE = "https://s100.divarcdn.com/static/photo/neda/webp_post";
const PHOTO_PATHS = [ /* the 11 path strings from prototype line 612, unchanged, in order */ ];
export const IMAGES: string[] = PHOTO_PATHS.map((p) => `${DIVAR_PHOTO_BASE}/${p}.webp`);

export const MODELS: CarModel[] = [
  { id: "206", name: "پژو ۲۰۶", aliases: ["206", "۲۰۶"], base: { 1403: 790, 1402: 730, 1401: 670, 1400: 610, 1399: 560, 1398: 510, 1397: 470, 1396: 435 }, gears: ["دنده‌ای"] },
  { id: "dena", name: "دنا پلاس", aliases: ["دنا"], base: { 1403: 1180, 1402: 1090, 1401: 1000, 1400: 920, 1399: 850, 1398: 790 }, gears: ["دنده‌ای", "اتوماتیک"] },
  { id: "tara", name: "تارا", aliases: ["تارا"], base: { 1403: 1260, 1402: 1170, 1401: 1090, 1400: 1010 }, gears: ["دنده‌ای", "اتوماتیک"] },
  { id: "j4", name: "جک J4", aliases: ["جک", "j4", "جی۴"], base: { 1402: 930, 1401: 860, 1400: 800, 1399: 740, 1398: 690 }, gears: ["اتوماتیک"] },
];
export const BODIES: BodyCondition[] = [
  { name: "سالم و بی‌خط و خش", f: 1 }, { name: "خط و خش جزیی", f: 0.98 }, { name: "رنگ‌شدگی، در ۱ ناحیه", f: 0.94 },
  { name: "رنگ‌شدگی، در ۲ ناحیه", f: 0.9 }, { name: "دوررنگ", f: 0.82 }, { name: "تصادفی", f: 0.72 },
];
export const CITIES: City[] = [
  { name: "تهران", lat: 35.72, lng: 51.4, districts: ["پونک", "سعادت‌آباد", "نارمک", "تهرانپارس", "پیروزی", "جنت‌آباد"] },
  { name: "کرج", lat: 35.83, lng: 50.97, districts: ["گوهردشت", "مهرشهر", "عظیمیه", "فردیس"] },
  { name: "اصفهان", lat: 32.66, lng: 51.67, districts: ["خانه اصفهان", "ملک‌شهر", "سپاهان‌شهر", "مرداویج"] },
];
export const COLORS = ["سفید", "مشکی", "نوک‌مدادی", "سفید", "خاکستری", "سفید", "آبی"];
export const POSTED = ["۲ ساعت پیش", "۵ ساعت پیش", "دیروز", "دیروز", "۲ روز پیش", "۳ روز پیش", "هفتهٔ پیش"];
export const ISSUES: Issue[] = [
  { name: "رنگ‌شدگی", neg: true }, { name: "تعویض موتور", neg: true }, { name: "تصادف جزئی", neg: true }, { name: "لاستیک نو", neg: false },
  { name: "معاینه فنی دارد", neg: false }, { name: "فنی سالم", neg: false }, { name: "سند تک‌برگ", neg: false }, { name: "بیمه کامل", neg: false }, { name: "قابلیت معاوضه", neg: false },
];
export const SNIPS: Record<string, string> = { /* the 9 entries from prototype lines 635–638, unchanged */ };

export const findModel = (id: string): CarModel | undefined => MODELS.find((m) => m.id === id);
export const isNegativeIssue = (name: string): boolean => ISSUES.some((i) => i.name === name && i.neg);
```

(The two `/* … */` markers mean "paste those exact literal lines from the prototype" — they are data, not logic.)

- [ ] **Step 6: `src/lib/pricing.ts`**

```ts
import { AMBER, GREEN, NOW_YEAR, RED, isNegativeIssue } from "./catalog";
import { fa, num } from "./format";
import type { BodyCondition, BreakdownRow, CarModel, Gear, Listing, PriceModelResult, Verdict } from "./types";

const KM_PER_YEAR = 18000;
const KM_BASELINE = 8000;
const KM_WEIGHT = 0.08;
const INSURANCE_NEUTRAL_MONTHS = 6;
const INSURANCE_WEIGHT_PER_MONTH = 0.002;
const AUTOMATIC_PREMIUM = 1.06;
export const CHEAP_THRESHOLD_PCT = -5;
export const EXPENSIVE_THRESHOLD_PCT = 6;
const NEUTRAL_COLOR = "#667085";
const INK = "#172033";

export function priceModel(model: CarModel, year: number, km: number, body: BodyCondition, gear: Gear, insMonths: number): PriceModelResult {
  const base = model.base[year];
  if (base === undefined) throw new RangeError(`No base price for ${model.id} year ${year}`);
  const age = Math.max(0.5, NOW_YEAR - year);
  const expKm = age * KM_PER_YEAR + KM_BASELINE;
  const kmF = 1 - Math.max(-0.5, Math.min(1, (km - expKm) / expKm)) * KM_WEIGHT;
  const insF = 1 + (insMonths - INSURANCE_NEUTRAL_MONTHS) * INSURANCE_WEIGHT_PER_MONTH;
  const gearF = gear === "اتوماتیک" && model.gears.length > 1 ? AUTOMATIC_PREMIUM : 1;
  const est = base * body.f * kmF * insF * gearF;
  return { base, expKm, kmF, insF, gearF, est, parts: { km: base * (kmF - 1), body: base * (body.f - 1), ins: base * (insF - 1), gear: base * (gearF - 1) } };
}

export function verdictOf(diffPct: number): Verdict {
  if (diffPct <= CHEAP_THRESHOLD_PCT) return { label: "ارزان‌تر از بازار", color: GREEN, bg: "#ecfdf3", icon: "M16 17h6v-6M22 17l-8.5-8.5-5 5L2 7" };
  if (diffPct >= EXPENSIVE_THRESHOLD_PCT) return { label: "بالاتر از بازار", color: RED, bg: "#fdecec", icon: "M16 7h6v6M22 7l-8.5 8.5-5-5L2 17" };
  return { label: "قیمت منصفانه", color: AMBER, bg: "#fffbeb", icon: "M20 6 9 17l-5-5" };
}

export const diffText = (d: number): string =>
  d > 0.5 ? `${fa(Math.abs(d).toFixed(0))}٪ بالاتر از تخمین`
  : d < -0.5 ? `${fa(Math.abs(d).toFixed(0))}٪ ارزان‌تر از تخمین`
  : "برابر تخمین بازار";

export const scoreColor = (score: number): string => (score >= 70 ? GREEN : score >= 45 ? AMBER : RED);

export const signedMillions = (d: number): string => (d >= 0 ? "+" : "−") + num(Math.abs(d));
export const deltaColor = (d: number): string => (Math.abs(d) < 1 ? NEUTRAL_COLOR : d > 0 ? GREEN : RED);

export function breakdownRows(l: Listing): BreakdownRow[] {
  const p = l.pm;
  const rows: BreakdownRow[] = [
    { label: "قیمت پایهٔ مدل و سال", note: `میانهٔ آگهی‌های ${l.modelName} مدل ${fa(l.year)}`, val: `${num(p.base)} میلیون`, color: INK },
    { label: "کارکرد", note: `${num(l.km)} کیلومتر در برابر انتظار ${num(p.expKm)}`, val: signedMillions(p.parts.km), color: deltaColor(p.parts.km) },
    { label: "وضعیت بدنه", note: l.body.name, val: signedMillions(p.parts.body), color: deltaColor(p.parts.body) },
    { label: "بیمهٔ شخص ثالث", note: `${fa(l.ins)} ماه باقی‌مانده`, val: signedMillions(p.parts.ins), color: deltaColor(p.parts.ins) },
  ];
  if (p.gearF !== 1) rows.push({ label: "گیربکس اتوماتیک", note: "نسبت به نسخهٔ دنده‌ای", val: signedMillions(p.parts.gear), color: GREEN });
  if (l.extra) rows.push({ label: "تعویض موتور", note: "استخراج‌شده از متن آگهی", val: signedMillions(p.base * l.extra), color: RED });
  return rows;
}

export function summaryOf(l: Listing): string {
  const v = verdictOf(l.diffPct);
  const neg = l.tags.filter(isNegativeIssue);
  const pos = l.tags.filter((t) => !isNegativeIssue(t));
  const kmWord = l.pm.kmF > 1.02 ? "کم‌کارکرد" : l.pm.kmF < 0.97 ? "پرکارکرد" : "با کارکرد معمول";
  const priceWord = v.label === "قیمت منصفانه" ? "در محدودهٔ بازار" : v.label.replace("بازار", "تخمین بازار");
  const advice = l.diffPct <= CHEAP_THRESHOLD_PCT ? "ارزش بازدید سریع دارد، ولی دلیل قیمت پایین را حضوری بپرس."
    : l.diffPct >= EXPENSIVE_THRESHOLD_PCT ? "جای مذاکره دارد." : "اگر بازدید رضایت‌بخش بود قیمت منطقی است.";
  return `${l.modelName} مدل ${fa(l.year)}، ${kmWord} نسبت به سنش. بدنه «${l.body.name}»${neg.length ? ` و فروشنده به ${neg.join(" و ")} اشاره کرده` : ""}. ${pos.length ? `نکات مثبت: ${pos.join("، ")}. ` : ""}قیمت ${priceWord} است؛ ${advice}`;
}

export function verdictNote(l: Listing): string {
  if (l.diffPct <= CHEAP_THRESHOLD_PCT) return `این آگهی حدود ${num(l.est - l.price)} میلیون زیر تخمین ماست. قبل از پرداخت، دلیل قیمت پایین (سند، رنگ، تصادف) رو حضوری چک کن.`;
  if (l.diffPct >= EXPENSIVE_THRESHOLD_PCT) return `حدود ${num(l.price - l.est)} میلیون بالاتر از تخمین. با اشاره به آگهی‌های مشابه، جای مذاکره داری.`;
  return "قیمت در بازهٔ منطقی آگهی‌های مشابه است.";
}
```

- [ ] **Step 7: Run** `bun test src/lib` — Expected: PASS (10 tests). Then `bunx tsc --noEmit`.

- [ ] **Step 8: Commit** — `git add frontend/src/lib && git commit -m "feat(frontend): add catalog, formatting, and price model"`

---

### Task 3: Seeded listings generator

**Files:**
- Create: `frontend/src/lib/listings.ts`
- Test: `frontend/src/lib/listings.test.ts`

**Interfaces:**
- Consumes: `priceModel`, catalog constants, `fa`, `num`, `Listing`.
- Produces: `generateListings(): Listing[]`, `LISTINGS: Listing[]`, `findListing(id: string): Listing | undefined`, `listingsOfModel(modelId: string): Listing[]`.

The RNG call order below reproduces the prototype's data exactly (prototype lines 641–688). Do not reorder `random()` calls. Only change: `token` comes from a second seeded RNG instead of `Math.random()` so SSR and client agree.

- [ ] **Step 1: Failing test** — `src/lib/listings.test.ts`:

```ts
import { expect, test } from "bun:test";
import { MODELS } from "./catalog";
import { LISTINGS, findListing, generateListings, listingsOfModel } from "./listings";

test("generation is deterministic", () => {
  expect(generateListings()).toEqual(generateListings());
});
test("every model gets 12–15 listings with unique ids", () => {
  for (const m of MODELS) {
    const n = listingsOfModel(m.id).length;
    expect(n).toBeGreaterThanOrEqual(12);
    expect(n).toBeLessThanOrEqual(15);
  }
  expect(new Set(LISTINGS.map((l) => l.id)).size).toBe(LISTINGS.length);
});
test("listings are internally consistent", () => {
  for (const l of LISTINGS) {
    expect(l.price % 5).toBe(0);
    expect(l.score).toBeGreaterThanOrEqual(5);
    expect(l.score).toBeLessThanOrEqual(99);
    expect(l.diffPct).toBeCloseTo(((l.price - l.est) / l.est) * 100, 6);
    expect(l.photos.length).toBeGreaterThanOrEqual(3);
    expect(l.token).toMatch(/^g[0-9a-z]{7}$/);
    expect(MODELS.find((m) => m.id === l.modelId)!.gears).toContain(l.gear);
  }
});
test("findListing resolves known ids and rejects unknown", () => {
  expect(findListing("l20")?.id).toBe("l20");
  expect(findListing("nope")).toBeUndefined();
});
```

- [ ] **Step 2: Run** `bun test src/lib/listings.test.ts` — Expected: FAIL.

- [ ] **Step 3: Implement** `src/lib/listings.ts`:

```ts
import { BODIES, CITIES, COLORS, IMAGES, ISSUES, MODELS, NOW_YEAR, POSTED, SNIPS } from "./catalog";
import { fa, num } from "./format";
import { priceModel } from "./pricing";
import type { CarModel, Listing } from "./types";

const LISTINGS_SEED = 20240917;
const TOKEN_SEED = 7919;
const ENGINE_SWAP_TAG = "تعویض موتور";
const ENGINE_SWAP_DISCOUNT = -0.08;

type Random = () => number;

function createRandom(seed: number): Random {
  let state = seed;
  return () => (state = (state * 1664525 + 1013904223) % 4294967296) / 4294967296;
}

function createToken(random: Random): string {
  return "g" + Math.floor(random() * 36 ** 7).toString(36).padStart(7, "0");
}

function generateListing(model: CarModel, index: number, serial: number, random: Random, tokenRandom: Random): Listing {
  const years = Object.keys(model.base).map(Number);
  const year = years[Math.floor(random() * years.length)];
  const age = Math.max(0.5, NOW_YEAR - year);
  const km = Math.round((age * 16000 * (0.4 + random() * 1.4) + random() * 15000) / 1000) * 1000;
  const body = BODIES[Math.min(5, Math.floor(Math.pow(random(), 1.6) * 6))];
  const city = CITIES[Math.floor(Math.pow(random(), 1.4) * 3)];
  const gear = model.gears[Math.floor(random() * model.gears.length)];
  const ins = Math.floor(random() * 13);
  const pm = priceModel(model, year, km, body, gear, ins);

  const tags: string[] = [];
  if (body.f <= 0.94) tags.push("رنگ‌شدگی");
  if (body.f <= 0.72) tags.push("تصادف جزئی");
  if (random() < 0.12) tags.push(ENGINE_SWAP_TAG);
  ISSUES.filter((i) => !i.neg).forEach((i) => { if (random() < 0.32 && !tags.includes(i.name)) tags.push(i.name); });

  const engineSwapped = tags.includes(ENGINE_SWAP_TAG);
  const extra = engineSwapped ? ENGINE_SWAP_DISCOUNT : 0;
  const noise = -0.13 + random() * 0.28 + extra;
  const price = Math.round((pm.est * (1 + noise)) / 5) * 5;
  const est = Math.round(pm.est * (1 + extra));
  const diffPct = ((price - est) / est) * 100;
  const score = Math.max(5, Math.min(99, Math.round(72 - diffPct * 2.4 + (body.f - 0.92) * 90 + (pm.kmF - 1) * 120)));
  const color = COLORS[Math.floor(random() * COLORS.length)];
  const desc = [
    `${model.name} مدل ${fa(year)}، ${gear}، رنگ ${color}.`,
    `کارکرد ${num(km)} کیلومتر واقعی.`,
    body === BODIES[0] ? "بدنه کاملاً بی‌رنگ و فابریک." : `وضعیت بدنه: ${body.name}.`,
    ...tags.map((t) => SNIPS[t]),
    ins ? `بیمه ${fa(ins)} ماه.` : "بیمه تمام شده.",
    "بازدید فقط حضوری، لطفاً پیام ندید تماس بگیرید.",
  ].join("\n");

  // Order of random() calls from here on matches the prototype's object literal.
  const imageOffset = serial + 1 + index;
  const district = city.districts[Math.floor(random() * city.districts.length)];
  const posted = POSTED[Math.floor(random() * POSTED.length)];
  const photos = Array.from({ length: 3 + Math.floor(random() * 3) }, (_, k) => IMAGES[(imageOffset + k * 3) % IMAGES.length]);
  const engine = engineSwapped ? "تعویض شده" : random() < 0.1 ? "نیاز به تعمیر" : "سالم";
  const gearbox = random() < 0.08 ? "نیاز به تعمیر" : "سالم و پلمپ";
  const lat = city.lat + (random() - 0.5) * 0.12;
  const lng = city.lng + (random() - 0.5) * 0.14;

  return {
    id: `l${serial}`, modelId: model.id, modelName: model.name, year, km, body, city: city.name, district, gear, ins, color,
    price, est, diffPct, score, tags, desc, pm, extra, img: IMAGES[imageOffset % IMAGES.length], posted, postedIdx: POSTED.indexOf(posted),
    photos, assess: { engine, chassis: body.f <= 0.72 ? "ضربه‌خورده" : "سالم و پلمپ", bodyA: body.name, gearbox }, lat, lng, token: createToken(tokenRandom),
  };
}

export function generateListings(): Listing[] {
  const random = createRandom(LISTINGS_SEED);
  const tokenRandom = createRandom(TOKEN_SEED);
  const listings: Listing[] = [];
  let serial = 1;
  for (const model of MODELS) {
    const count = 12 + Math.floor(random() * 4);
    for (let index = 0; index < count; index++) listings.push(generateListing(model, index, serial++, random, tokenRandom));
  }
  return listings;
}

export const LISTINGS: Listing[] = generateListings();
export const findListing = (id: string): Listing | undefined => LISTINGS.find((l) => l.id === id);
export const listingsOfModel = (modelId: string): Listing[] => LISTINGS.filter((l) => l.modelId === modelId);
```

The draw order after `desc` (`district` → `posted` → `photos` → `engine` → `gearbox` → `lat` → `lng`) is the evaluation order of the prototype's object literal; keeping it yields the same listings as the prototype (e.g. `l20` is the same car).

- [ ] **Step 4: Run** `bun test src/lib` — Expected: PASS.

- [ ] **Step 5: Commit** — `git commit -am "feat(frontend): add deterministic synthetic listings generator"` (after `git add`).

---

### Task 4: Search — query parsing, filters, sorting

**Files:**
- Create: `frontend/src/lib/search.ts`
- Test: `frontend/src/lib/search.test.ts`

**Interfaces:**
- Consumes: `MODELS`, `CITIES`, `findModel`, `en`, `fa`, `num`, `CHEAP_THRESHOLD_PCT`, types.
- Produces:
  - `DEFAULT_MAX_PRICE = 1400`, `DEFAULT_MAX_KM = 250`, `DEFAULT_FILTERS: Filters`
  - `parseQuery(q: string): ParsedQuery`
  - `hasCriteria(p: ParsedQuery): boolean`
  - `chipsOf(p: ParsedQuery): string[]`
  - `filtersFromQuery(p: ParsedQuery): Filters`
  - `matchesParsed(l: Listing, p: ParsedQuery): boolean`
  - `filterListings(list: Listing[], f: Filters): Listing[]`
  - `sortListings(list: Listing[], sort: SortKey): Listing[]`
  - `activeFilterCount(f: Filters): number`

- [ ] **Step 1: Failing test** — `src/lib/search.test.ts`:

```ts
import { expect, test } from "bun:test";
import { LISTINGS } from "./listings";
import { DEFAULT_FILTERS, activeFilterCount, chipsOf, filterListings, filtersFromQuery, parseQuery, sortListings } from "./search";

test("home example: 206 low-mileage Tehran", () => {
  const p = parseQuery("پژو ۲۰۶ کم‌کارکرد تهران");
  expect(p).toMatchObject({ models: ["206"], city: "تهران", maxKm: 90, maxPrice: null, gear: null });
});
test("home example: Dena automatic under one billion (words)", () => {
  const p = parseQuery("دنا پلاس اتومات زیر یک میلیارد");
  expect(p).toMatchObject({ models: ["dena"], maxPrice: 1000, gear: "اتوماتیک" });
});
test("home example: Tara cheaper than market", () => {
  expect(parseQuery("تارا ارزان‌تر از بازار")).toMatchObject({ models: ["tara"], onlyBelow: true, maxPrice: null });
});
test("home example: JAC under 900 million", () => {
  expect(parseQuery("جک J4 زیر ۹۰۰ میلیون")).toMatchObject({ models: ["j4"], maxPrice: 900 });
});
test("placeholder query: price is not mistaken for mileage", () => {
  expect(parseQuery("پژو ۲۰۶ کم‌کارکرد زیر ۷۰۰ میلیون، تهران")).toMatchObject({ maxPrice: 700, maxKm: 90 });
});
test("decimal billions, explicit km, year, arabic letters", () => {
  expect(parseQuery("زیر 1.2 میلیارد").maxPrice).toBe(1200);
  expect(parseQuery("دنا کارکرد زیر ۵۰ هزار کیلومتر").maxKm).toBe(50);
  expect(parseQuery("تارا مدل ۱۴۰۲ دنده").year).toBe(1402);
  expect(parseQuery("تارا مدل ۱۴۰۲ دنده").gear).toBe("دنده‌ای");
  expect(parseQuery("كرج").city).toBe("کرج");
});
test("chips and filters derive from the parsed query", () => {
  const p = parseQuery("دنا پلاس اتومات زیر یک میلیارد کرج");
  expect(chipsOf(p)).toEqual(["دنا پلاس", "زیر ۱,۰۰۰ میلیون", "کرج", "اتوماتیک"]);
  expect(filtersFromQuery(p)).toEqual({ ...DEFAULT_FILTERS, models: ["dena"], cities: ["کرج"], maxPrice: 1000, gear: "اتوماتیک" });
});
test("each filter narrows results", () => {
  expect(filterListings(LISTINGS, DEFAULT_FILTERS)).toHaveLength(LISTINGS.length);
  expect(filterListings(LISTINGS, { ...DEFAULT_FILTERS, models: ["tara"] }).every((l) => l.modelId === "tara")).toBe(true);
  expect(filterListings(LISTINGS, { ...DEFAULT_FILTERS, cities: ["کرج"] }).every((l) => l.city === "کرج")).toBe(true);
  expect(filterListings(LISTINGS, { ...DEFAULT_FILTERS, maxPrice: 700 }).every((l) => l.price <= 700)).toBe(true);
  expect(filterListings(LISTINGS, { ...DEFAULT_FILTERS, maxKm: 50 }).every((l) => l.km <= 50000)).toBe(true);
  expect(filterListings(LISTINGS, { ...DEFAULT_FILTERS, gear: "اتوماتیک" }).every((l) => l.gear === "اتوماتیک")).toBe(true);
  expect(filterListings(LISTINGS, { ...DEFAULT_FILTERS, onlyBelow: true }).every((l) => l.diffPct <= -5)).toBe(true);
  expect(filterListings(LISTINGS, { ...DEFAULT_FILTERS, year: 1401 }).every((l) => l.year === 1401)).toBe(true);
});
test("sorting does not mutate and orders correctly", () => {
  const copy = [...LISTINGS];
  const byPrice = sortListings(LISTINGS, "price");
  expect(LISTINGS).toEqual(copy);
  expect(byPrice[0].price).toBe(Math.min(...LISTINGS.map((l) => l.price)));
  expect(sortListings(LISTINGS, "km")[0].km).toBe(Math.min(...LISTINGS.map((l) => l.km)));
  expect(sortListings(LISTINGS, "score")[0].score).toBe(Math.max(...LISTINGS.map((l) => l.score)));
  expect(sortListings(LISTINGS, "new")[0].postedIdx).toBe(Math.min(...LISTINGS.map((l) => l.postedIdx)));
});
test("activeFilterCount counts non-default filters", () => {
  expect(activeFilterCount(DEFAULT_FILTERS)).toBe(0);
  expect(activeFilterCount({ ...DEFAULT_FILTERS, models: ["206", "tara"], maxKm: 100, onlyBelow: true })).toBe(4);
});
```

- [ ] **Step 2: Run** — Expected: FAIL.

- [ ] **Step 3: Implement** `src/lib/search.ts`:

```ts
import { CITIES, MODELS, findModel } from "./catalog";
import { en, fa, num } from "./format";
import { CHEAP_THRESHOLD_PCT } from "./pricing";
import type { Filters, Listing, ParsedQuery, SortKey } from "./types";

export const DEFAULT_MAX_PRICE = 1400;
export const DEFAULT_MAX_KM = 250;
const LOW_MILEAGE_KM = 90;
const BILLION_TO_MILLION = 1000;
const IMPLICIT_BILLION_BELOW = 5; // "زیر ۱.۲" means billions

export const DEFAULT_FILTERS: Filters = { models: [], cities: [], maxPrice: DEFAULT_MAX_PRICE, maxKm: DEFAULT_MAX_KM, gear: "همه", onlyBelow: false, year: null };

const normalize = (q: string): string => en(q).toLowerCase().replace(/ي/g, "ی").replace(/ك/g, "ک");

function parseMaxPrice(text: string): number | null {
  const match = text.match(/(?:زیر|کمتر از|تا|حداکثر)\s*(\d+(?:\.\d+)?)\s*(میلیارد|میلیون)?/);
  if (match) {
    const value = parseFloat(match[1]);
    const inBillions = match[2] === "میلیارد" || value < IMPLICIT_BILLION_BELOW;
    return Math.round(value * (inBillions ? BILLION_TO_MILLION : 1));
  }
  return /یک میلیارد/.test(text) ? BILLION_TO_MILLION : null;
}

function parseMaxKm(text: string): number | null {
  const explicit = text.match(/(?:کارکرد\s*)?(?:زیر|کمتر از)\s*(\d+)\s*(?:هزار)?\s*(?:کیلومتر|تا کارکرد|کارکرد)/);
  if (explicit) return parseInt(explicit[1], 10);
  return /کم[\s‌]?کارکرد|کم کار/.test(text) ? LOW_MILEAGE_KM : null;
}

export function parseQuery(q: string): ParsedQuery {
  const text = normalize(q);
  const year = text.match(/(?:مدل|سال)\s*(1[34]\d\d)/);
  return {
    models: MODELS.filter((m) => [m.name, ...m.aliases].some((a) => text.includes(normalize(a)))).map((m) => m.id),
    city: CITIES.find((c) => text.includes(c.name))?.name ?? null,
    maxPrice: parseMaxPrice(text),
    maxKm: parseMaxKm(text),
    gear: /اتومات/.test(text) ? "اتوماتیک" : /دنده/.test(text) ? "دنده‌ای" : null,
    year: year ? parseInt(year[1], 10) : null,
    onlyBelow: /ارزان|زیر قیمت|به‌?صرفه|به صرفه/.test(text),
  };
}

export const hasCriteria = (p: ParsedQuery): boolean => p.models.length > 0 || p.maxPrice !== null || p.city !== null || p.maxKm !== null;

export function chipsOf(p: ParsedQuery): string[] {
  const chips = p.models.map((id) => findModel(id)!.name);
  if (p.year) chips.push(`مدل ${fa(p.year)}`);
  if (p.maxPrice) chips.push(`زیر ${num(p.maxPrice)} میلیون`);
  if (p.maxKm) chips.push(`کارکرد زیر ${fa(p.maxKm)} هزار`);
  if (p.city) chips.push(p.city);
  if (p.gear) chips.push(p.gear);
  if (p.onlyBelow) chips.push("فقط ارزان‌تر از بازار");
  return chips;
}

export const filtersFromQuery = (p: ParsedQuery): Filters => ({
  models: p.models, cities: p.city ? [p.city] : [], maxPrice: p.maxPrice ?? DEFAULT_MAX_PRICE, maxKm: p.maxKm ?? DEFAULT_MAX_KM,
  gear: p.gear ?? "همه", onlyBelow: p.onlyBelow, year: p.year,
});

export const matchesParsed = (l: Listing, p: ParsedQuery): boolean =>
  (!p.models.length || p.models.includes(l.modelId)) && (!p.city || l.city === p.city) && (!p.maxPrice || l.price <= p.maxPrice) &&
  (!p.maxKm || l.km <= p.maxKm * 1000) && (!p.gear || l.gear === p.gear) && (!p.year || l.year === p.year);

export const filterListings = (list: Listing[], f: Filters): Listing[] =>
  list.filter((l) =>
    (!f.models.length || f.models.includes(l.modelId)) && (!f.cities.length || f.cities.includes(l.city)) &&
    l.price <= f.maxPrice && l.km <= f.maxKm * 1000 && (f.gear === "همه" || l.gear === f.gear) &&
    (!f.onlyBelow || l.diffPct <= CHEAP_THRESHOLD_PCT) && (!f.year || l.year === f.year));

const COMPARATORS: Record<SortKey, (a: Listing, b: Listing) => number> = {
  price: (a, b) => a.price - b.price, km: (a, b) => a.km - b.km, new: (a, b) => a.postedIdx - b.postedIdx, score: (a, b) => b.score - a.score,
};
export const sortListings = (list: Listing[], sort: SortKey): Listing[] => [...list].sort(COMPARATORS[sort]);

export const activeFilterCount = (f: Filters): number =>
  f.models.length + f.cities.length + Number(f.maxPrice < DEFAULT_MAX_PRICE) + Number(f.maxKm < DEFAULT_MAX_KM) + Number(f.gear !== "همه") + Number(f.onlyBelow);
```

- [ ] **Step 4: Run** `bun test src/lib` — Expected: PASS. If the mixed price+mileage test fails, the explicit-km regex is matching a price; it must require a following `کیلومتر|کارکرد` token — do not loosen it.

- [ ] **Step 5: Commit** — `feat(frontend): add natural-language query parsing, filters, and sorting`

---

### Task 5: Screen view-models — cards, assistant, model stats, compare, estimate

**Files:**
- Create: `frontend/src/lib/view.ts`, `assistant.ts`, `modelStats.ts`, `compare.ts`, `estimate.ts`
- Test: `frontend/src/lib/assistant.test.ts`, `frontend/src/lib/screens.test.ts`

**Interfaces (Produces):**

```ts
// view.ts
export interface CardView { id: string; href: string; img: string; title: string; posted: string; meta: string; priceFa: string; verdict: Verdict; diffText: string; score: number; scoreFa: string; scoreColor: string; body: string; insFa: string; }
export function cardOf(l: Listing): CardView;
// assistant.ts
export interface AssistantReply { text: string; cardIds?: string[]; }
export function scriptedReply(text: string, listings: Listing[], compareIds: string[]): AssistantReply;
// modelStats.ts
export interface HistogramBucket { countFa: string; heightPct: number; isMedian: boolean; tip: string; }
export interface IssueBar { name: string; widthPct: number; pctText: string; neg: boolean; }
export interface ModelStats { model: CarModel; listings: Listing[]; countFa: string; yearRange: string; median: number; min: number; max: number; alertThreshold: number; buckets: HistogramBucket[]; issues: IssueBar[]; }
export function modelStats(modelId: string, all: Listing[]): ModelStats; // throws RangeError on unknown model
export interface ModelRange { id: string; name: string; countFa: string; minFa: string; maxFa: string; barStartPct: number; barWidthPct: number; }
export function modelRange(modelId: string, all: Listing[]): ModelRange;
// compare.ts
export interface CompareCell { text: string; color: string; best: boolean; }
export interface CompareRow { label: string; cells: CompareCell[]; }
export function compareRows(cars: Listing[]): CompareRow[];
// estimate.ts
export interface EstimateInput { modelId: string; year: number; kmThousands: number; bodyIndex: number; gear: Gear; asking: string; }
export interface EstimateResult { model: CarModel; year: number; years: number[]; gear: Gear; title: string; est: number; low: number; high: number; similar: Listing[]; similarCount: number; breakdown: BreakdownRow[]; asking: { value: number; verdict: Verdict; text: string } | null; }
export function estimate(input: EstimateInput, all: Listing[]): EstimateResult;
```

- [ ] **Step 1: Failing tests**

`src/lib/assistant.test.ts`:

```ts
import { expect, test } from "bun:test";
import { scriptedReply } from "./assistant";
import { LISTINGS } from "./listings";

test("no criteria → explains coverage", () => {
  const r = scriptedReply("سلام", LISTINGS, []);
  expect(r.text).toContain("پژو ۲۰۶، دنا پلاس، تارا و جک J4");
  expect(r.cardIds).toBeUndefined();
});
test("budget question without criteria → asks for budget", () => {
  expect(scriptedReply("قیمت چقدره؟", LISTINGS, []).text).toContain("بودجه‌ت رو بگو");
});
test("impossible criteria → no-match message", () => {
  expect(scriptedReply("تارا زیر ۱۰۰ میلیون", LISTINGS, []).text).toContain("آگهی فعالی نداریم");
});
test("matching criteria → count, median and top-3 cards by score", () => {
  const r = scriptedReply("دنا پلاس", LISTINGS, []);
  const dena = LISTINGS.filter((l) => l.modelId === "dena").sort((a, b) => b.score - a.score);
  expect(r.text).toContain("آگهی پیدا کردم");
  expect(r.cardIds).toEqual(dena.slice(0, 3).map((l) => l.id));
});
test("compare question with two compared cars → picks the best score", () => {
  const [a, b] = LISTINGS;
  const best = a.score >= b.score ? a : b;
  const r = scriptedReply("کدوم به‌صرفه‌تره؟", LISTINGS, [a.id, b.id]);
  expect(r.cardIds).toEqual([best.id]);
});
```

`src/lib/screens.test.ts`:

```ts
import { expect, test } from "bun:test";
import { compareRows } from "./compare";
import { estimate } from "./estimate";
import { LISTINGS } from "./listings";
import { modelRange, modelStats } from "./modelStats";
import { cardOf } from "./view";

test("cardOf builds href, title and meta", () => {
  const l = LISTINGS[0];
  const c = cardOf(l);
  expect(c.href).toBe(`/listing/${l.id}`);
  expect(c.title).toContain(l.modelName);
  expect(c.meta).toContain(l.city);
});
test("modelStats: 8 buckets cover every listing, exactly one median bucket, sorted by score", () => {
  const s = modelStats("dena", LISTINGS);
  expect(s.buckets).toHaveLength(8);
  expect(s.buckets.filter((b) => b.isMedian)).toHaveLength(1);
  expect(s.min).toBeLessThanOrEqual(s.median);
  expect(s.median).toBeLessThanOrEqual(s.max);
  expect(s.listings[0].score).toBe(Math.max(...s.listings.map((l) => l.score)));
  expect(s.alertThreshold % 10).toBe(0);
  expect(() => modelStats("nope", LISTINGS)).toThrow(RangeError);
});
test("modelRange bar stays within 0–100%", () => {
  const r = modelRange("206", LISTINGS);
  expect(r.barStartPct).toBeGreaterThanOrEqual(0);
  expect(r.barStartPct + r.barWidthPct).toBeLessThanOrEqual(100);
});
test("compareRows: 10 rows, lowest price marked best, single car marks nothing", () => {
  const cars = LISTINGS.slice(0, 3);
  const rows = compareRows(cars);
  expect(rows).toHaveLength(10);
  const cheapest = cars.indexOf([...cars].sort((a, b) => a.price - b.price)[0]);
  expect(rows[0].cells[cheapest].best).toBe(true);
  expect(compareRows([cars[0]]).flatMap((r) => r.cells).some((c) => c.best)).toBe(false);
  expect(compareRows([])).toEqual([]);
});
test("estimate: falls back to a valid year and gear, evaluates asking price", () => {
  const r = estimate({ modelId: "j4", year: 1403, kmThousands: 80, bodyIndex: 0, gear: "دنده‌ای", asking: "۲۰۰۰" }, LISTINGS);
  expect(r.year).toBe(1402);
  expect(r.gear).toBe("اتوماتیک");
  expect(r.low).toBeLessThan(r.est);
  expect(r.asking?.verdict.label).toBe("بالاتر از بازار");
  expect(estimate({ modelId: "j4", year: 1402, kmThousands: 80, bodyIndex: 0, gear: "اتوماتیک", asking: "" }, LISTINGS).asking).toBeNull();
});
```

- [ ] **Step 2: Run** — Expected: FAIL.

- [ ] **Step 3: `src/lib/view.ts`**

```ts
import { fa, num } from "./format";
import { diffText, scoreColor, verdictOf } from "./pricing";
import type { Listing, Verdict } from "./types";

export interface CardView { id: string; href: string; img: string; title: string; posted: string; meta: string; priceFa: string; verdict: Verdict; diffText: string; score: number; scoreFa: string; scoreColor: string; body: string; insFa: string; }

export const cardOf = (l: Listing): CardView => ({
  id: l.id, href: `/listing/${l.id}`, img: l.img, title: `${l.modelName} مدل ${fa(l.year)}`, posted: l.posted,
  meta: `${num(l.km)} کیلومتر · ${l.city}، ${l.district} · ${l.gear}`, priceFa: num(l.price), verdict: verdictOf(l.diffPct),
  diffText: diffText(l.diffPct), score: l.score, scoreFa: fa(l.score), scoreColor: scoreColor(l.score), body: l.body.name, insFa: fa(l.ins),
});
```

- [ ] **Step 4: `src/lib/assistant.ts`**

```ts
import { en, fa, num } from "./format";
import { CHEAP_THRESHOLD_PCT, diffText } from "./pricing";
import { chipsOf, hasCriteria, matchesParsed, parseQuery, sortListings } from "./search";
import type { Listing } from "./types";

export interface AssistantReply { text: string; cardIds?: string[]; }

const SUGGESTED_CARDS = 3;
const MIN_CARS_TO_COMPARE = 2;
const COMPARE_QUESTION = /کدوم|کدام|بهتر|به‌?صرفه|به صرفه/;
const BUDGET_QUESTION = /بودجه|چقدر|قیمت/;

function bestOfCompared(compared: Listing[]): AssistantReply {
  const best = sortListings(compared, "score")[0];
  return { text: `بین ${fa(compared.length)} ماشینی که توی مقایسه داری، ${best.modelName} مدل ${fa(best.year)} (${best.city}) بهترین ارزش خرید رو داره: ${diffText(best.diffPct)}، ${num(best.km)} کیلومتر و بدنه «${best.body.name}».`, cardIds: [best.id] };
}

export function scriptedReply(text: string, listings: Listing[], compareIds: string[]): AssistantReply {
  const parsed = parseQuery(text);
  const normalized = en(text);
  const compared = listings.filter((l) => compareIds.includes(l.id));
  if (COMPARE_QUESTION.test(normalized) && compared.length >= MIN_CARS_TO_COMPARE) return bestOfCompared(compared);
  if (!hasCriteria(parsed)) {
    return BUDGET_QUESTION.test(normalized)
      ? { text: "بودجه‌ت رو بگو (مثلاً «زیر ۸۰۰ میلیون») و اگه شهر یا مدل خاصی مدنظرته اضافه کن؛ بهترین گزینه‌ها رو نشونت می‌دم." }
      : { text: "من روی آگهی‌های پژو ۲۰۶، دنا پلاس، تارا و جک J4 در تهران، کرج و اصفهان کار می‌کنم. یه چیزی مثل «دنا اتومات زیر یک میلیارد کرج» بگو." };
  }
  const matches = listings.filter((l) => matchesParsed(l, parsed));
  if (!matches.length) return { text: "با این شرایط آگهی فعالی نداریم. سقف قیمت رو بالاتر ببر یا شهر رو حذف کن." };
  const below = matches.filter((l) => l.diffPct <= CHEAP_THRESHOLD_PCT).length;
  const median = sortListings(matches, "price")[Math.floor(matches.length / 2)].price;
  return {
    text: `${fa(matches.length)} آگهی پیدا کردم (${chipsOf(parsed).join("، ")}). میانهٔ قیمت‌شون ${num(median)} میلیونه و ${fa(below)} تاش زیر قیمت بازاره. سه‌تای اول از نظر ارزش خرید:`,
    cardIds: sortListings(matches, "score").slice(0, SUGGESTED_CARDS).map((l) => l.id),
  };
}
```

- [ ] **Step 5: `src/lib/modelStats.ts`**

```ts
import { ISSUES, findModel } from "./catalog";
import { fa, num } from "./format";
import { sortListings } from "./search";
import type { CarModel, Listing } from "./types";

const BUCKET_COUNT = 8;
const MAX_BAR_HEIGHT_PCT = 90;
const MIN_BAR_HEIGHT_PCT = 4;
const MAX_ISSUES = 6;
const ALERT_FRACTION_OF_MEDIAN = 0.9;
const ALERT_ROUNDING = 10;
const RANGE_AXIS_MIN = 400;
const RANGE_AXIS_MAX = 1350;

export interface HistogramBucket { countFa: string; heightPct: number; isMedian: boolean; tip: string; }
export interface IssueBar { name: string; widthPct: number; pctText: string; neg: boolean; }
export interface ModelStats { model: CarModel; listings: Listing[]; countFa: string; yearRange: string; median: number; min: number; max: number; alertThreshold: number; buckets: HistogramBucket[]; issues: IssueBar[]; }
export interface ModelRange { id: string; name: string; countFa: string; minFa: string; maxFa: string; barStartPct: number; barWidthPct: number; }

function requireModel(modelId: string): CarModel {
  const model = findModel(modelId);
  if (!model) throw new RangeError(`Unknown model: ${modelId}`);
  return model;
}

function priceBuckets(prices: number[], median: number): HistogramBucket[] {
  const min = prices[0];
  const width = (prices[prices.length - 1] - min) / BUCKET_COUNT || 1;
  const bucketOf = (price: number) => Math.min(BUCKET_COUNT - 1, Math.floor((price - min) / width));
  const counts = Array<number>(BUCKET_COUNT).fill(0);
  prices.forEach((p) => counts[bucketOf(p)]++);
  const tallest = Math.max(...counts);
  return counts.map((count, i) => ({
    countFa: count ? fa(count) : "", heightPct: Math.max(MIN_BAR_HEIGHT_PCT, (count / tallest) * MAX_BAR_HEIGHT_PCT),
    isMedian: i === bucketOf(median), tip: `${num(min + i * width)} تا ${num(min + (i + 1) * width)} میلیون`,
  }));
}

function issueBars(listings: Listing[]): IssueBar[] {
  return ISSUES.map((issue) => ({ issue, n: listings.filter((l) => l.tags.includes(issue.name)).length }))
    .filter((x) => x.n > 0).sort((a, b) => b.n - a.n).slice(0, MAX_ISSUES)
    .map(({ issue, n }) => { const pct = Math.round((n / listings.length) * 100); return { name: issue.name, widthPct: pct, pctText: `${fa(pct)}٪ آگهی‌ها`, neg: issue.neg }; });
}

export function modelStats(modelId: string, all: Listing[]): ModelStats {
  const model = requireModel(modelId);
  const listings = sortListings(all.filter((l) => l.modelId === modelId), "score");
  const prices = listings.map((l) => l.price).sort((a, b) => a - b);
  const years = listings.map((l) => l.year);
  const median = prices[Math.floor(prices.length / 2)];
  return {
    model, listings, countFa: fa(listings.length), yearRange: `${fa(Math.min(...years))} تا ${fa(Math.max(...years))}`,
    median, min: prices[0], max: prices[prices.length - 1],
    alertThreshold: Math.round((median * ALERT_FRACTION_OF_MEDIAN) / ALERT_ROUNDING) * ALERT_ROUNDING,
    buckets: priceBuckets(prices, median), issues: issueBars(listings),
  };
}

export function modelRange(modelId: string, all: Listing[]): ModelRange {
  const model = requireModel(modelId);
  const prices = all.filter((l) => l.modelId === modelId).map((l) => l.price);
  const min = Math.min(...prices), max = Math.max(...prices);
  const span = RANGE_AXIS_MAX - RANGE_AXIS_MIN;
  const clampPct = (v: number) => Math.max(0, Math.min(100, v));
  const start = clampPct(((min - RANGE_AXIS_MIN) / span) * 100);
  return { id: model.id, name: model.name, countFa: fa(prices.length), minFa: num(min), maxFa: num(max), barStartPct: start, barWidthPct: Math.min(100 - start, ((max - min) / span) * 100) };
}
```

- [ ] **Step 6: `src/lib/compare.ts`**

```ts
import { fa, num } from "./format";
import { diffText, scoreColor, verdictOf } from "./pricing";
import type { Listing } from "./types";

export interface CompareCell { text: string; color: string; best: boolean; }
export interface CompareRow { label: string; cells: CompareCell[]; }

const INK = "#172033";
type Better = (a: number, b: number) => boolean;
const lower: Better = (a, b) => a < b;
const higher: Better = (a, b) => a > b;

function indexOfBest(values: number[], better: Better): number {
  return values.reduce((best, v, i) => (best === -1 || better(v, values[best]) ? i : best), -1);
}

function numericRow(label: string, cars: Listing[], get: (l: Listing) => number, text: (l: Listing) => string, better: Better, color: (v: number) => string = () => INK): CompareRow {
  const values = cars.map(get);
  const best = cars.length > 1 ? indexOfBest(values, better) : -1;
  return { label, cells: cars.map((l, i) => ({ text: text(l), color: color(values[i]), best: i === best })) };
}

const textRow = (label: string, cars: Listing[], text: (l: Listing) => string): CompareRow =>
  ({ label, cells: cars.map((l) => ({ text: text(l), color: INK, best: false })) });

export function compareRows(cars: Listing[]): CompareRow[] {
  if (!cars.length) return [];
  return [
    numericRow("قیمت", cars, (l) => l.price, (l) => `${num(l.price)} میلیون`, lower),
    numericRow("نسبت به بازار", cars, (l) => l.diffPct, (l) => diffText(l.diffPct), lower, (v) => verdictOf(v).color),
    numericRow("ارزش خرید", cars, (l) => l.score, (l) => `${fa(l.score)}/۱۰۰`, higher, scoreColor),
    numericRow("سال ساخت", cars, (l) => l.year, (l) => fa(l.year), higher),
    numericRow("کارکرد", cars, (l) => l.km, (l) => `${num(l.km)} کیلومتر`, lower),
    textRow("گیربکس", cars, (l) => l.gear),
    numericRow("وضعیت بدنه", cars, (l) => l.body.f, (l) => l.body.name, higher),
    numericRow("بیمه", cars, (l) => l.ins, (l) => `${fa(l.ins)} ماه`, higher),
    textRow("شهر", cars, (l) => l.city),
    textRow("نکات آگهی", cars, (l) => l.tags.join("، ") || "—"),
  ];
}
```

- [ ] **Step 7: `src/lib/estimate.ts`**

```ts
import { BODIES, GREEN, MODELS, findModel } from "./catalog";
import { en, fa, num } from "./format";
import { deltaColor, diffText, priceModel, signedMillions, verdictOf } from "./pricing";
import { sortListings } from "./search";
import type { BreakdownRow, CarModel, Gear, Listing, Verdict } from "./types";

export interface EstimateInput { modelId: string; year: number; kmThousands: number; bodyIndex: number; gear: Gear; asking: string; }
export interface EstimateResult { model: CarModel; year: number; years: number[]; gear: Gear; title: string; est: number; low: number; high: number; similar: Listing[]; similarCount: number; breakdown: BreakdownRow[]; asking: { value: number; verdict: Verdict; text: string } | null; }

const NEUTRAL_INSURANCE_MONTHS = 6;
const RANGE_MARGIN = 0.05;
const SIMILAR_YEAR_WINDOW = 1;
const MAX_SIMILAR = 4;
const INK = "#172033";

export function estimate(input: EstimateInput, all: Listing[]): EstimateResult {
  const model = findModel(input.modelId) ?? MODELS[0];
  const years = Object.keys(model.base).map(Number).sort((a, b) => b - a);
  const year = model.base[input.year] !== undefined ? input.year : years[0];
  const body = BODIES[input.bodyIndex] ?? BODIES[0];
  const gear = model.gears.includes(input.gear) ? input.gear : model.gears[0];
  const km = input.kmThousands * 1000;
  const pm = priceModel(model, year, km, body, gear, NEUTRAL_INSURANCE_MONTHS);
  const est = Math.round(pm.est);
  const similarAll = all.filter((l) => l.modelId === model.id && Math.abs(l.year - year) <= SIMILAR_YEAR_WINDOW);
  const askingValue = parseFloat(en(input.asking));
  const hasAsking = !Number.isNaN(askingValue) && askingValue > 0;
  const askingDiff = hasAsking ? ((askingValue - est) / est) * 100 : 0;
  const breakdown: BreakdownRow[] = [
    { label: "قیمت پایهٔ مدل و سال", note: `میانهٔ آگهی‌های ${model.name} مدل ${fa(year)}`, val: `${num(pm.base)} میلیون`, color: INK },
    { label: "کارکرد", note: `${num(km)} در برابر انتظار ${num(pm.expKm)} کیلومتر`, val: signedMillions(pm.parts.km), color: deltaColor(pm.parts.km) },
    { label: "وضعیت بدنه", note: body.name, val: signedMillions(pm.parts.body), color: deltaColor(pm.parts.body) },
    ...(pm.gearF !== 1 ? [{ label: "گیربکس اتوماتیک", note: "نسبت به نسخهٔ دنده‌ای", val: signedMillions(pm.parts.gear), color: GREEN }] : []),
  ];
  return {
    model, year, years, gear, title: `${model.name} مدل ${fa(year)}`, est, low: est * (1 - RANGE_MARGIN), high: est * (1 + RANGE_MARGIN),
    similar: sortListings(similarAll, "score").slice(0, MAX_SIMILAR), similarCount: similarAll.length, breakdown,
    asking: hasAsking ? { value: askingValue, verdict: verdictOf(askingDiff), text: `قیمت ${num(askingValue)} میلیون، ${diffText(askingDiff)}` } : null,
  };
}
```

- [ ] **Step 8: Run** `bun test && bunx tsc --noEmit && bun run lint` — Expected: all PASS.

- [ ] **Step 9: Commit** — `feat(frontend): add assistant replies and screen view-models`

---

### Task 6: App state, toast, icons

**Files:**
- Create: `frontend/src/state/AppState.tsx`, `frontend/src/components/Toast.tsx` + `.module.css`, `frontend/src/components/Icon.tsx`
- Modify: `frontend/src/app/layout.tsx` (wrap children in `<AppStateProvider>`, render `<Toast />`)

**Interfaces (Produces):**

```ts
export const MAX_COMPARE = 3;
export type AvatarAnimation = "idle" | "thinking" | "happy";
export interface AppStateValue {
  compare: string[]; saved: string[]; alerts: PriceAlert[]; loggedIn: boolean;
  bellOpen: boolean; chatOpen: boolean; chatMessages: ChatMessage[]; chatBusy: boolean; avatarAnimation: AvatarAnimation; toast: string;
  toggleCompare(id: string): void; removeFromCompare(id: string): void; toggleSaved(id: string): void;
  addAlert(alert: PriceAlert): void; removeAlert(index: number): void; toggleLogin(): void;
  setBellOpen(open: boolean): void; setChatOpen(open: boolean): void; sendChat(text: string): void; showToast(text: string): void;
}
export function AppStateProvider(props: { children: React.ReactNode }): JSX.Element;
export function useAppState(): AppStateValue; // throws if used outside the provider
// Icon.tsx
export type IconName = "search" | "bell" | "sparkles" | "trendDown" | "filter" | "chevronDown" | "bookmark" | "send" | "home" | "compare" | "estimate";
export function Icon(props: { name?: IconName; d?: string; size?: number; stroke?: string; fill?: string; className?: string }): JSX.Element;
```

- [ ] **Step 1: `src/components/Icon.tsx`**

```tsx
const PATHS = {
  search: "M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16zm10 18-4.3-4.3",
  bell: "M10.3 21a1.9 1.9 0 0 0 3.4 0M3.3 17A2 2 0 0 0 5 20h14a2 2 0 0 0 1.7-3A11 11 0 0 1 19 11.5V9a7 7 0 0 0-14 0v2.5A11 11 0 0 1 3.3 17",
  sparkles: "M9.9 2.2a.5.5 0 0 1 .9 0l1.5 4.1a4 4 0 0 0 2.4 2.4l4.1 1.5a.5.5 0 0 1 0 .9l-4.1 1.5a4 4 0 0 0-2.4 2.4l-1.5 4.1a.5.5 0 0 1-.9 0l-1.5-4.1a4 4 0 0 0-2.4-2.4L2 11.1a.5.5 0 0 1 0-.9l4.1-1.5a4 4 0 0 0 2.4-2.4zM20 3v4M22 5h-4M4 17v2M5 18H3",
  trendDown: "M16 17h6v-6M22 17l-8.5-8.5-5 5L2 7",
  filter: "M10 20a1 1 0 0 0 .6.9 1 1 0 0 0 1-.1l2-1.5a1 1 0 0 0 .4-.8v-4.6a1 1 0 0 1 .3-.7L20.7 6.3A1 1 0 0 0 20 4.6H4a1 1 0 0 0-.7 1.7l6.4 6.9a1 1 0 0 1 .3.7z",
  chevronDown: "m6 9 6 6 6-6",
  bookmark: "m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z",
  send: "m12 19-7-7 7-7M19 12H5",
  home: "M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8M3 10a2 2 0 0 1 .7-1.5l7-6a2 2 0 0 1 2.6 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  compare: "M5 4h5a2 2 0 0 1 2 2v14H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM14 4h5a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-5z",
  estimate: "M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM6 8h12v3H6zM7 15h1M11.5 15h1M16 15h1",
} as const;

export type IconName = keyof typeof PATHS;

interface IconProps { name?: IconName; d?: string; size?: number; stroke?: string; fill?: string; className?: string; }

export function Icon({ name, d, size = 18, stroke = "currentColor", fill = "none", className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke={stroke} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true" style={{ flexShrink: 0 }}>
      <path d={d ?? (name ? PATHS[name] : "")} />
    </svg>
  );
}
```

- [ ] **Step 2: `src/state/AppState.tsx`**

```tsx
"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { scriptedReply } from "@/lib/assistant";
import { LISTINGS } from "@/lib/listings";
import type { ChatMessage, PriceAlert } from "@/lib/types";

export const MAX_COMPARE = 3;
export type AvatarAnimation = "idle" | "thinking" | "happy";

const STORAGE_KEY = "torobcar:v1";
const TOAST_MS = 2200;
const REPLY_DELAY_MS = 700;
const HAPPY_MS = 2500;
const GREETING: ChatMessage = { role: "assistant", text: "سلام! بگو دنبال چه ماشینی هستی، یا بپرس کدوم آگهی به‌صرفه‌تره. من همهٔ آگهی‌های فعال رو می‌بینم." };

interface Persisted { compare: string[]; saved: string[]; alerts: PriceAlert[]; loggedIn: boolean; }
const EMPTY: Persisted = { compare: [], saved: [], alerts: [], loggedIn: false };

export interface AppStateValue extends Persisted {
  bellOpen: boolean; chatOpen: boolean; chatMessages: ChatMessage[]; chatBusy: boolean; avatarAnimation: AvatarAnimation; toast: string;
  toggleCompare(id: string): void; removeFromCompare(id: string): void; toggleSaved(id: string): void;
  addAlert(alert: PriceAlert): void; removeAlert(index: number): void; toggleLogin(): void;
  setBellOpen(open: boolean): void; setChatOpen(open: boolean): void; sendChat(text: string): void; showToast(text: string): void;
}

const AppStateContext = createContext<AppStateValue | null>(null);

function readPersisted(): Persisted {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? { ...EMPTY, ...(JSON.parse(raw) as Partial<Persisted>) } : EMPTY;
  } catch {
    return EMPTY; // storage blocked or corrupt → start clean (spec: Error handling)
  }
}

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const [persisted, setPersisted] = useState<Persisted>(EMPTY);
  const [hydrated, setHydrated] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([GREETING]);
  const [chatBusy, setChatBusy] = useState(false);
  const [recentReply, setRecentReply] = useState(false);
  const [toast, setToast] = useState("");
  const toastTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const happyTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Load after mount so server and first client render match.
  useEffect(() => { setPersisted(readPersisted()); setHydrated(true); }, []);
  useEffect(() => {
    if (!hydrated) return;
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(persisted)); } catch { /* storage unavailable: state stays in memory */ }
  }, [persisted, hydrated]);

  const patch = useCallback((change: (p: Persisted) => Partial<Persisted>) => setPersisted((p) => ({ ...p, ...change(p) })), []);

  const showToast = useCallback((text: string) => {
    setToast(text);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), TOAST_MS);
  }, []);

  const toggleCompare = useCallback((id: string) => {
    if (persisted.compare.includes(id)) { patch((p) => ({ compare: p.compare.filter((x) => x !== id) })); return; }
    if (persisted.compare.length >= MAX_COMPARE) { showToast("حداکثر سه خودرو می‌تونی مقایسه کنی"); return; }
    patch((p) => ({ compare: [...p.compare, id] }));
    showToast("به مقایسه اضافه شد");
  }, [persisted.compare, patch, showToast]);

  const removeFromCompare = useCallback((id: string) => patch((p) => ({ compare: p.compare.filter((x) => x !== id) })), [patch]);

  const toggleSaved = useCallback((id: string) => {
    const wasSaved = persisted.saved.includes(id);
    patch((p) => ({ saved: wasSaved ? p.saved.filter((x) => x !== id) : [...p.saved, id] }));
    showToast(wasSaved ? "از نشان‌ها حذف شد" : "نشان شد");
  }, [persisted.saved, patch, showToast]);

  const addAlert = useCallback((alert: PriceAlert) => {
    if (!persisted.loggedIn) { setBellOpen(true); showToast("برای هشدار قیمت اول وارد شو"); return; }
    patch((p) => ({ alerts: [...p.alerts, alert] }));
    showToast("هشدار قیمت ذخیره شد");
  }, [persisted.loggedIn, patch, showToast]);

  const removeAlert = useCallback((index: number) => patch((p) => ({ alerts: p.alerts.filter((_, i) => i !== index) })), [patch]);

  const toggleLogin = useCallback(() => {
    showToast(persisted.loggedIn ? "خارج شدی" : "خوش اومدی علی!");
    patch((p) => ({ loggedIn: !p.loggedIn }));
    setBellOpen(false);
  }, [persisted.loggedIn, patch, showToast]);

  const sendChat = useCallback((raw: string) => {
    const text = raw.trim();
    if (!text || chatBusy) return;
    setChatMessages((m) => [...m, { role: "user", text }]);
    setChatBusy(true);
    const compareIds = persisted.compare;
    setTimeout(() => {
      setChatMessages((m) => [...m, { role: "assistant", ...scriptedReply(text, LISTINGS, compareIds) }]);
      setChatBusy(false);
      setRecentReply(true);
      clearTimeout(happyTimer.current);
      happyTimer.current = setTimeout(() => setRecentReply(false), HAPPY_MS);
    }, REPLY_DELAY_MS);
  }, [chatBusy, persisted.compare]);

  const avatarAnimation: AvatarAnimation = chatBusy ? "thinking" : recentReply ? "happy" : "idle";

  const value = useMemo<AppStateValue>(() => ({
    ...persisted, bellOpen, chatOpen, chatMessages, chatBusy, avatarAnimation, toast,
    toggleCompare, removeFromCompare, toggleSaved, addAlert, removeAlert, toggleLogin, setBellOpen, setChatOpen, sendChat, showToast,
  }), [persisted, bellOpen, chatOpen, chatMessages, chatBusy, avatarAnimation, toast, toggleCompare, removeFromCompare, toggleSaved, addAlert, removeAlert, toggleLogin, sendChat, showToast]);

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState(): AppStateValue {
  const value = useContext(AppStateContext);
  if (!value) throw new Error("useAppState must be used inside <AppStateProvider>");
  return value;
}
```

If ESLint's `react-hooks/set-state-in-effect` flags the load effect, keep the code and add on the line above it: `// eslint-disable-next-line react-hooks/set-state-in-effect -- one-time hydration-safe load from localStorage`.

- [ ] **Step 3: `Toast.tsx`** (port prototype lines 599–601)

```tsx
"use client";
import { useAppState } from "@/state/AppState";
import styles from "./Toast.module.css";

export function Toast() {
  const { toast } = useAppState();
  return toast ? <div className={styles.toast} role="status">{toast}</div> : null;
}
```

```css
.toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); background: var(--ink); color: #fff; padding: 10px 16px; border-radius: 10px; font-size: 13px; z-index: 90; animation: tk-pop .15s ease-out; box-shadow: 0 8px 24px rgba(0,0,0,.2); white-space: nowrap; }
@media (max-width: 767px) { .toast { bottom: calc(var(--tabbar-h) + env(safe-area-inset-bottom) + 12px); } }
```

- [ ] **Step 4: Wire into layout** — in `layout.tsx` body: `<AppStateProvider>{children}<Toast /></AppStateProvider>`.

- [ ] **Step 5: Verify** `bun run lint && bunx tsc --noEmit && bun run build` — PASS.

- [ ] **Step 6: Commit** — `feat(frontend): add app state provider, toast, and icon set`

---

### Task 7: Shell — Avatar, Header, tab bar, footer, chat panel

**Files:**
- Create (each `.tsx` + `.module.css`): `Avatar`, `Header`, `HeaderSearch`, `AlertsDropdown`, `MobileTabBar`, `Footer`, `ChatPanel`, `MiniListing`, `VerdictBadge` in `frontend/src/components/`
- Create if needed: `frontend/src/types/avatar-web.d.ts`
- Modify: `frontend/src/app/layout.tsx`

**Interfaces:**
- Consumes: `useAppState`, `Icon`, `cardOf`, `findListing`, `fa`.
- Produces: `<Avatar size body animation />`, `<MiniListing card={CardView} />`, `<VerdictBadge verdict={Verdict} size="sm"|"md" />`, shell mounted in layout with `<main className="page">`.

- [ ] **Step 1: Avatar types (only if `bunx tsc` reports no types for the package)** — `src/types/avatar-web.d.ts`:

```ts
declare module "@bible-strong/avatar-web" {
  export interface AvatarDefinition { colors?: Record<string, string>; [key: string]: unknown; }
  export interface AvatarController { play(animation: string): void; destroy(): void; }
  export function createAvatar(container: HTMLElement, options: { definition: AvatarDefinition; defaultAnimation?: string; size?: string | number; ariaLabel?: string }): AvatarController;
}
```

- [ ] **Step 2: `Avatar.tsx`** (port of `prototype/avatar-host.js`)

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import type { AvatarAnimation } from "@/state/AppState";

const DEFINITION_URL = "/strobi.avatar.json";
const DEFAULT_BODY = "#68b828";

interface AvatarProps { size: number; body?: string; animation?: AvatarAnimation; }
interface Controller { play(animation: string): void; destroy(): void; }

function FallbackFace({ color }: { color: string }) {
  return (
    <svg viewBox="-150 -150 300 300" width="100%" height="100%" aria-label="دستیار" role="img">
      <circle r="120" fill={color} />
      <ellipse cx="-35" cy="-7" rx="10" ry="25" fill="#111316" />
      <ellipse cx="35" cy="-7" rx="10" ry="25" fill="#111316" />
    </svg>
  );
}

export function Avatar({ size, body = DEFAULT_BODY, animation = "idle" }: AvatarProps) {
  const boxRef = useRef<HTMLSpanElement>(null);
  const controllerRef = useRef<Controller | null>(null);
  const animationRef = useRef(animation);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function mount() {
      try {
        const [{ createAvatar }, definition] = await Promise.all([
          import("@bible-strong/avatar-web"),
          fetch(DEFINITION_URL).then((r) => { if (!r.ok) throw new Error(`avatar definition ${r.status}`); return r.json(); }),
        ]);
        if (cancelled || !boxRef.current) return;
        controllerRef.current = createAvatar(boxRef.current, {
          definition: { ...definition, colors: { ...definition.colors, body } }, defaultAnimation: animationRef.current, size: "100%", ariaLabel: "دستیار",
        });
      } catch (error) {
        console.warn("[Avatar] falling back to static face", error);
        if (!cancelled) setFailed(true);
      }
    }
    mount();
    return () => { cancelled = true; controllerRef.current?.destroy(); controllerRef.current = null; };
  }, [body]);

  useEffect(() => { animationRef.current = animation; controllerRef.current?.play(animation); }, [animation]);

  return (
    <span ref={boxRef} style={{ display: "block", width: size, height: size, overflow: "hidden", lineHeight: 0, flexShrink: 0 }}>
      {failed && <FallbackFace color={body} />}
    </span>
  );
}
```

- [ ] **Step 3: `VerdictBadge` and `MiniListing`**

```tsx
// VerdictBadge.tsx — prototype line 262 (md: height 26/28, font 12/13) and line 325 (sm: height 22, font 11)
import { Icon } from "./Icon";
import type { Verdict } from "@/lib/types";
import styles from "./VerdictBadge.module.css";

export function VerdictBadge({ verdict, size = "md" }: { verdict: Verdict; size?: "sm" | "md" }) {
  return <span className={`${styles.badge} ${styles[size]}`} style={{ background: verdict.color }}><Icon d={verdict.icon} size={14} stroke="#fff" />{verdict.label}</span>;
}
```

```tsx
// MiniListing.tsx — prototype lines 452–456 (also used by chat cards 573–577 and estimate 536–540)
import Link from "next/link";
import type { CardView } from "@/lib/view";
import styles from "./MiniListing.module.css";

export function MiniListing({ card, bordered = false }: { card: CardView; bordered?: boolean }) {
  return (
    <Link href={card.href} className={`${styles.row} ${bordered ? styles.bordered : ""}`}>
      <div role="img" aria-label={card.title} className={styles.thumb} style={{ backgroundImage: `url(${card.img})` }} />
      <div className={styles.text}><div className={styles.title}>{card.title}</div><div className={styles.meta}>{card.meta}</div></div>
      <div className={styles.price}><div className={styles.amount}>{card.priceFa}</div><div className={styles.verdict} style={{ color: card.verdict.color }}>{card.verdict.label}</div></div>
    </Link>
  );
}
```

CSS per Porting Convention; `.bordered` = the chat-card style from line 573 (`padding:8px; border:1px solid var(--line); border-radius:10px; background:#fff` + hover border red).

- [ ] **Step 4: `HeaderSearch.tsx`** (lines 99–104 desktop, 146–148 mobile). One component, `variant` prop:

```tsx
"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Icon } from "./Icon";
import styles from "./HeaderSearch.module.css";

const PLACEHOLDER = { desktop: "مثلاً: دنا پلاس اتومات زیر یک میلیارد، کرج", mobile: "جست‌وجو…" } as const;

export function HeaderSearch({ variant }: { variant: "desktop" | "mobile" }) {
  const router = useRouter();
  const query = useSearchParams().get("q") ?? "";
  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = String(new FormData(event.currentTarget).get("q") ?? "").trim();
    router.push(text ? `/results?q=${encodeURIComponent(text)}` : "/results");
  }
  return (
    <form onSubmit={submit} className={styles[variant]} role="search">
      <div className={styles.box}><Icon name="search" stroke="#667085" /><input key={query} name="q" defaultValue={query} placeholder={PLACEHOLDER[variant]} className={styles.input} aria-label="جست‌وجو" /></div>
    </form>
  );
}
```

`.desktop` is hidden under 768px; `.mobile` is `display:none` above it and `position: sticky; top: var(--header-h); z-index: 40` below. Both usages must be wrapped in `<Suspense fallback={null}>` (required by `useSearchParams`).

- [ ] **Step 5: `AlertsDropdown.tsx`** (lines 124–141): reads `alerts, loggedIn, removeAlert, toggleLogin` from `useAppState`. Header text `هشدارهای قیمت` + `${fa(alerts.length)} فعال` when logged in. Logged out → login prompt block (line 128). Each alert row: title, `قیمت کمتر از ${num(a.threshold)} میلیون · الان ${fa(a.matches)} آگهی زیر این قیمت`, `×` button → `removeAlert(i)`. Empty → line 138 copy. Mobile: `width: calc(100vw - 32px); left: -8px`.

- [ ] **Step 6: `Header.tsx`** (lines 87–144)

The logo is a plain `<img>` (no `next/image` anywhere, per Global Constraints), with an eslint-disable comment for `@next/next/no-img-element`:

```tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useRef } from "react";
import { fa } from "@/lib/format";
import { useAppState } from "@/state/AppState";
import { AlertsDropdown } from "./AlertsDropdown";
import { Avatar } from "./Avatar";
import { HeaderSearch } from "./HeaderSearch";
import { Icon } from "./Icon";
import styles from "./Header.module.css";

const SEARCH_SECTION_PREFIXES = ["/results", "/model", "/listing"];
export const isSearchSection = (pathname: string): boolean => SEARCH_SECTION_PREFIXES.some((p) => pathname.startsWith(p));

export function Header() {
  const pathname = usePathname();
  const { compare, alerts, loggedIn, bellOpen, chatOpen, setBellOpen, setChatOpen, toggleLogin } = useAppState();
  const bellRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!bellOpen) return;
    const closeOnOutsideClick = (event: MouseEvent) => { if (!bellRef.current?.contains(event.target as Node)) setBellOpen(false); };
    document.addEventListener("click", closeOnOutsideClick);
    return () => document.removeEventListener("click", closeOnOutsideClick);
  }, [bellOpen, setBellOpen]);

  const tabs = [
    { label: "خانه", href: "/", active: pathname === "/" },
    { label: "جست‌وجو", href: "/results", active: isSearchSection(pathname) },
    { label: compare.length ? `مقایسه (${fa(compare.length)})` : "مقایسه", href: "/compare", active: pathname === "/compare" },
    { label: "تخمین قیمت", href: "/estimate", active: pathname === "/estimate" },
  ];
  const showSearch = pathname !== "/";

  return (
    <>
      <header className={styles.header}>
        <div className={styles.inner}>
          <Link href="/" className={styles.brand}>{/* eslint-disable-next-line @next/next/no-img-element */}<img src="/logo.png" alt="" width={34} height={34} /><span>ترب‌کار</span></Link>
          <nav className={styles.nav}>{tabs.map((t) => <Link key={t.href} href={t.href} className={`${styles.tab} ${t.active ? styles.tabActive : ""}`}>{t.label}</Link>)}</nav>
          {showSearch && <Suspense fallback={null}><HeaderSearch variant="desktop" /></Suspense>}
          <div className={styles.actions} ref={bellRef}>
            <button className={styles.chatButton} onClick={() => setChatOpen(!chatOpen)}><span className={styles.chatAvatar}><Avatar size={24} /></span>دستیار</button>
            <button className={styles.iconButton} aria-label="هشدارها" aria-expanded={bellOpen} onClick={() => setBellOpen(!bellOpen)}><Icon name="bell" stroke="#172033" />{loggedIn && alerts.length > 0 && <span className={styles.dot} />}</button>
            {loggedIn
              ? <button className={styles.user} title="خروج" onClick={toggleLogin}><span>علی</span><span className={styles.userBadge}>ع</span></button>
              : <button className={styles.login} onClick={toggleLogin}>ورود</button>}
            {bellOpen && <AlertsDropdown />}
          </div>
        </div>
      </header>
      {showSearch && <Suspense fallback={null}><HeaderSearch variant="mobile" /></Suspense>}
    </>
  );
}
```

CSS: port 87–122. Mobile: `.inner{height:56px;padding:0 16px;gap:10px}`, hide `.nav` and `.chatButton`; `.header{padding-top: env(safe-area-inset-top)}`.

- [ ] **Step 7: `MobileTabBar.tsx`** (lines 552–556, 952–955)

```tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAppState } from "@/state/AppState";
import { isSearchSection } from "./Header";
import { Icon, type IconName } from "./Icon";
import styles from "./MobileTabBar.module.css";

const ACTIVE_FILL = "#fde2e4";

export function MobileTabBar() {
  const pathname = usePathname();
  const { chatOpen, setChatOpen } = useAppState();
  const links: { label: string; href: string; icon: IconName; active: boolean }[] = [
    { label: "خانه", href: "/", icon: "home", active: pathname === "/" },
    { label: "جست‌وجو", href: "/results", icon: "search", active: isSearchSection(pathname) },
    { label: "مقایسه", href: "/compare", icon: "compare", active: pathname === "/compare" },
    { label: "تخمین", href: "/estimate", icon: "estimate", active: pathname === "/estimate" },
  ];
  const item = (l: (typeof links)[number]) => (
    <Link key={l.href} href={l.href} className={`${styles.item} ${l.active ? styles.active : ""}`} onClick={() => setChatOpen(false)}>
      <Icon name={l.icon} size={22} fill={l.active ? ACTIVE_FILL : "none"} />{l.label}
    </Link>
  );
  return (
    <nav className={styles.bar} aria-label="ناوبری اصلی">
      {links.slice(0, 2).map(item)}
      <button className={`${styles.item} ${chatOpen ? styles.active : ""}`} onClick={() => setChatOpen(!chatOpen)}><Icon name="sparkles" size={22} fill={chatOpen ? ACTIVE_FILL : "none"} />دستیار</button>
      {links.slice(2).map(item)}
    </nav>
  );
}
```

CSS: `.bar{display:none}`; under 768px: `display:grid; grid-template-columns:repeat(5,1fr); position:fixed; inset:auto 0 0 0; height:calc(var(--tabbar-h) + env(safe-area-inset-bottom)); padding-bottom:env(safe-area-inset-bottom); background:#fff; border-top:1px solid var(--line); z-index:70`. `.item` = flex column, centered, gap 4, font 11/600, color `var(--muted)`, no border/background; `.active{color:var(--red)}`.

- [ ] **Step 8: `Footer.tsx`** (line 550; hidden under 768px) and **`ChatPanel.tsx`** (lines 559–597):

```tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { findListing } from "@/lib/listings";
import { cardOf } from "@/lib/view";
import { useAppState } from "@/state/AppState";
import { Avatar } from "./Avatar";
import { Icon } from "./Icon";
import { MiniListing } from "./MiniListing";
import styles from "./ChatPanel.module.css";

const OPENING = ["دنا پلاس زیر ۹۰۰ میلیون", "کم‌کارکردترین ۲۰۶ تهران", "تارا اتومات به‌صرفه"];
const COMPARING = ["بین این‌ها کدوم به‌صرفه‌تره؟"];
const FOLLOW_UP = ["ارزان‌ترین جک J4", "فقط ارزان‌تر از بازار نشون بده"];

export function ChatPanel() {
  const { chatOpen, setChatOpen, chatMessages, chatBusy, avatarAnimation, compare, sendChat } = useAppState();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight }); }, [chatMessages, chatBusy]);
  if (!chatOpen) return null;

  const suggestions = chatMessages.length <= 1 ? OPENING : compare.length >= 2 ? COMPARING : FOLLOW_UP;
  function submit(event: React.FormEvent) { event.preventDefault(); sendChat(input); setInput(""); }

  return (
    <aside className={styles.panel} aria-label="دستیار خرید">
      <div className={styles.head}><div className={styles.avatar}><Avatar size={40} animation={avatarAnimation} /></div><div className={styles.title}>دستیار خرید</div><button className={styles.close} onClick={() => setChatOpen(false)} aria-label="بستن">×</button></div>
      <div className={styles.messages} ref={scrollRef}>
        {chatMessages.map((m, i) => (
          <div key={i} className={m.role === "user" ? styles.fromUser : styles.fromAssistant}>
            <div className={styles.bubble}>{m.text}</div>
            {m.cardIds && <div className={styles.cards}>{m.cardIds.map((id) => { const l = findListing(id); return l ? <MiniListing key={id} card={cardOf(l)} bordered /> : null; })}</div>}
          </div>
        ))}
        {chatBusy && <div className={styles.typing}><span /><span /><span /></div>}
      </div>
      <div className={styles.suggestions}>{suggestions.map((s) => <button key={s} className={styles.chip} onClick={() => sendChat(s)}>{s}</button>)}</div>
      <form className={styles.form} onSubmit={submit}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="مثلاً: بین این‌ها کدوم به‌صرفه‌تره؟" className={styles.input} aria-label="پیام" />
        <button type="submit" className={styles.send} aria-label="ارسال"><Icon name="send" stroke="#fff" /></button>
      </form>
    </aside>
  );
}
```

CSS: `.fromUser{align-items:flex-start}` with bubble `background:var(--ink);color:#fff`; `.fromAssistant{align-items:flex-end}` with bubble `background:var(--fill)`. `.typing span` uses `tk-dots` with delays 0/.2s/.4s. Mobile: `.panel{width:100%; bottom:calc(var(--tabbar-h) + env(safe-area-inset-bottom)); padding-top:env(safe-area-inset-top)}`.

- [ ] **Step 9: Layout wiring** — `layout.tsx` body:

```tsx
<AppStateProvider>
  <div className="app"><Header /><main className="page">{children}</main><Footer /></div>
  <MobileTabBar /><ChatPanel /><Toast />
</AppStateProvider>
```

Add to `globals.css`:

```css
.app { min-height: 100vh; display: flex; flex-direction: column; }
.page { flex: 1; width: 100%; max-width: var(--page-w); margin: 0 auto; padding: 0 24px 64px; }
@media (max-width: 767px) { .page { padding: 0 16px calc(var(--tabbar-h) + env(safe-area-inset-bottom) + 24px); } }
```

- [ ] **Step 10: Verify** — `bun run lint && bunx tsc --noEmit && bun run build`; then `bun run dev`, open `http://localhost:3000`: header renders RTL, avatar animates in the header button, chat opens, a suggestion yields a reply with 3 cards after the thinking animation, login toggles, bell dropdown opens/closes on outside click. At 390px: tab bar shows, nav hidden.

- [ ] **Step 11: Commit** — `feat(frontend): add app shell with header, tab bar, assistant chat and avatar`

---

### Task 8: Home page and listing card

**Files:**
- Create: `frontend/src/components/ListingCard.tsx` + `.module.css`, `ScoreBar.tsx` + `.module.css`, `HomeSearch.tsx` + `.module.css`
- Modify: `frontend/src/app/page.tsx` (+ create `page.module.css`)

**Interfaces:** Produces `<ListingCard card={CardView} />`, `<ScoreBar score scoreFa color />`.

- [ ] **Step 1: `ListingCard.tsx`** (lines 259–273) — the worked example of the Porting Convention:

```tsx
import Link from "next/link";
import type { CardView } from "@/lib/view";
import { ScoreBar } from "./ScoreBar";
import { VerdictBadge } from "./VerdictBadge";
import styles from "./ListingCard.module.css";

export function ListingCard({ card }: { card: CardView }) {
  return (
    <Link href={card.href} className={styles.card}>
      <div className={styles.photoWrap}>
        <div role="img" aria-label={card.title} className={styles.photo} style={{ backgroundImage: `url(${card.img})` }} />
        <span className={styles.badge}><VerdictBadge verdict={card.verdict} /></span>
      </div>
      <div className={styles.body}>
        <div className={styles.titleRow}><span className={styles.title}>{card.title}</span><span className={styles.posted}>{card.posted}</span></div>
        <div className={styles.meta}>{card.meta}</div>
        <div className={styles.priceRow}>
          <span className={styles.price}>{card.priceFa} <span className={styles.unit}>میلیون</span></span>
          <span className={styles.diff} style={{ color: card.verdict.color }}>{card.diffText}</span>
        </div>
        <ScoreBar score={card.score} scoreFa={card.scoreFa} color={card.scoreColor} />
      </div>
    </Link>
  );
}
```

```css
.card { display: block; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; overflow: hidden; transition: box-shadow .15s; color: var(--ink); }
.card:hover { box-shadow: 0 8px 24px rgba(23,32,51,.08); border-color: var(--line-strong); color: var(--ink); }
.photoWrap { position: relative; aspect-ratio: 4/3; background: var(--photo); }
.photo { width: 100%; height: 100%; background-size: cover; background-position: center; }
.badge { position: absolute; top: 10px; right: 10px; }
.body { padding: 12px 14px 14px; }
.titleRow { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.title { font-size: 15px; font-weight: 700; }
.posted { font-size: 11px; color: var(--faint); white-space: nowrap; }
.meta { font-size: 12px; color: var(--muted); margin-top: 4px; }
.priceRow { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; }
.price { font-size: 17px; font-weight: 800; }
.unit { font-size: 11px; font-weight: 500; color: var(--muted); }
.diff { font-size: 12px; font-weight: 600; }
```

`ScoreBar` = line 271: track `flex:1;height:4px;border-radius:2px;background:var(--line-soft)`, fill `width:${score}%` + `background:color`, label `ارزش خرید {scoreFa}`.

- [ ] **Step 2: `HomeSearch.tsx`** (lines 159–170): client form → `router.push('/results?q=' + encodeURIComponent(text))` (empty → `/results`); the 4 example chips `["پژو ۲۰۶ کم‌کارکرد تهران","دنا پلاس اتومات زیر یک میلیارد","تارا ارزان‌تر از بازار","جک J4 زیر ۹۰۰ میلیون"]` are `<Link href={"/results?q=" + encodeURIComponent(text)}>`. Placeholder: `مثلاً: پژو ۲۰۶ کم‌کارکرد زیر ۷۰۰ میلیون، تهران`. Border turns red on `:focus-within`.

- [ ] **Step 3: `app/page.tsx`** (server component; lines 155–176): logo 72px, `<h1>ماشین می‌خوای؟ فقط بگو چی.</h1>`, `<HomeSearch />`, stats line using `fa(LISTINGS.length)` آگهی فعال · `fa(MODELS.length)` مدل · `به‌روزرسانی: ۱۲ دقیقه پیش`. Mobile: section padding `40px 0 24px`, h1 26px, stats wrap with `gap:16px`.

- [ ] **Step 4: Verify** in browser: home matches prototype at desktop and 390px; submitting navigates to `/results?q=…` (404 for now is expected). `bun run lint && bunx tsc --noEmit`.

- [ ] **Step 5: Commit** — `feat(frontend): add home page and listing card`

---

### Task 9: Results page

**Files:**
- Create (each + `.module.css`): `FiltersPanel`, `ParsedChips`, `ResultsToolbar`, `ModelCard`, `ResultsScreen` in `frontend/src/components/`
- Create: `frontend/src/app/results/page.tsx`

**Interfaces:**
- Consumes: `parseQuery, chipsOf, filtersFromQuery, filterListings, sortListings, activeFilterCount, DEFAULT_FILTERS`, `modelRange`, `cardOf`, `LISTINGS`, `MODELS`, `CITIES`, `listingsOfModel`, `useAppState().addAlert/loggedIn`.
- Produces: route `/results?q=`.

- [ ] **Step 1: `app/results/page.tsx`**

```tsx
"use client";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ResultsScreen } from "@/components/ResultsScreen";

function Results() {
  const query = useSearchParams().get("q") ?? "";
  return <ResultsScreen key={query} query={query} />; // key resets filters when the query changes
}

export default function ResultsPage() {
  return <Suspense fallback={null}><Results /></Suspense>;
}
```

- [ ] **Step 2: `ResultsScreen.tsx`**

```tsx
"use client";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { fa } from "@/lib/format";
import { LISTINGS } from "@/lib/listings";
import { modelRange } from "@/lib/modelStats";
import { CHEAP_THRESHOLD_PCT } from "@/lib/pricing";
import { DEFAULT_FILTERS, activeFilterCount, chipsOf, filterListings, filtersFromQuery, parseQuery, sortListings } from "@/lib/search";
import type { Filters, SortKey } from "@/lib/types";
import { cardOf } from "@/lib/view";
import { useAppState } from "@/state/AppState";
import { FiltersPanel } from "./FiltersPanel";
import { ListingCard } from "./ListingCard";
import { ModelCard } from "./ModelCard";
import { ParsedChips } from "./ParsedChips";
import { ResultsToolbar } from "./ResultsToolbar";
import styles from "./ResultsScreen.module.css";

const MAX_MODEL_CARDS = 4;

export function ResultsScreen({ query }: { query: string }) {
  const router = useRouter();
  const { addAlert } = useAppState();
  const parsed = useMemo(() => (query ? parseQuery(query) : null), [query]);
  const [filters, setFilters] = useState<Filters>(() => (parsed ? filtersFromQuery(parsed) : DEFAULT_FILTERS));
  const [sort, setSort] = useState<SortKey>("score");
  const [sheetOpen, setSheetOpen] = useState(false);

  useEffect(() => { document.body.style.overflow = sheetOpen ? "hidden" : ""; return () => { document.body.style.overflow = ""; }; }, [sheetOpen]);

  const filtered = useMemo(() => filterListings(LISTINGS, filters), [filters]);
  const results = useMemo(() => sortListings(filtered, sort), [filtered, sort]);
  const chips = parsed ? chipsOf(parsed) : [];
  const modelsInResults = [...new Set(filtered.map((l) => l.modelId))];
  const modelCardIds = filters.models.length ? filters.models : modelsInResults.length <= MAX_MODEL_CARDS ? modelsInResults : [];
  const cheaperCount = filtered.filter((l) => l.diffPct <= CHEAP_THRESHOLD_PCT).length;
  const activeCount = activeFilterCount(filters);

  function resetFilters() { setFilters(DEFAULT_FILTERS); if (query) router.replace("/results"); }
  function saveSearch() {
    addAlert({ title: chips.length ? chips.slice(0, 2).join(" · ") : "جست‌وجوی فعلی", threshold: filters.maxPrice, matches: filtered.filter((l) => l.price < filters.maxPrice).length });
  }

  return (
    <section className={styles.layout}>
      <FiltersPanel filters={filters} onChange={setFilters} onReset={resetFilters} open={sheetOpen} onClose={() => setSheetOpen(false)} resultCount={results.length} />
      <div className={styles.main}>
        {chips.length > 0 && <ParsedChips chips={chips} />}
        <ResultsToolbar countFa={fa(results.length)} subtitle={`${fa(cheaperCount)} آگهی ارزان‌تر از بازار`} filtersLabel={activeCount ? `فیلترها (${fa(activeCount)})` : "فیلترها"} onOpenFilters={() => setSheetOpen(true)} sort={sort} onSort={setSort} onSave={saveSearch} />
        {modelCardIds.length > 0 && <div className={styles.modelCards}>{modelCardIds.map((id) => <ModelCard key={id} range={modelRange(id, LISTINGS)} />)}</div>}
        <div className={styles.grid}>{results.map((l) => <ListingCard key={l.id} card={cardOf(l)} />)}</div>
        {results.length === 0 && <div className={styles.empty}>با این فیلترها چیزی پیدا نشد. سقف قیمت یا کارکرد رو بالا ببر.</div>}
      </div>
    </section>
  );
}
```

CSS: `.layout` = line 181 (`grid-template-columns:260px minmax(0,1fr); gap:24px; padding-top:24px; align-items:start`), mobile single column gap 14px. `.modelCards` = line 245, `.grid` = line 257, `.empty` = line 277.

- [ ] **Step 3: `FiltersPanel.tsx`** (lines 182–216 + mobile rules 54–65)

Props: `{ filters: Filters; onChange(next: Filters): void; onReset(): void; open: boolean; onClose(): void; resultCount: number }`.

```tsx
"use client";
import { CITIES, MODELS } from "@/lib/catalog";
import { fa, num } from "@/lib/format";
import { listingsOfModel } from "@/lib/listings";
import type { Filters, GearFilter } from "@/lib/types";
import styles from "./FiltersPanel.module.css";

const GEARS: GearFilter[] = ["همه", "دنده‌ای", "اتوماتیک"];
const toggle = <T,>(list: T[], item: T): T[] => (list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);

interface Props { filters: Filters; onChange(next: Filters): void; onReset(): void; open: boolean; onClose(): void; resultCount: number; }

export function FiltersPanel({ filters, onChange, onReset, open, onClose, resultCount }: Props) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  return (
    <>
      <aside className={styles.panel} data-open={open}>
        <div className={styles.sheetHead}><span className={styles.grabber} /><div className={styles.sheetTitleRow}><span className={styles.sheetTitle}>فیلترها</span><button className={styles.clear} onClick={onReset}>پاک‌کردن</button></div></div>
        <div className={styles.deskHead}>فیلترها</div>
        <div className={styles.body}>
          <div className={styles.label}>مدل</div>
          <div className={styles.models}>{MODELS.map((m) => (
            <label key={m.id} className={styles.check}><input type="checkbox" checked={filters.models.includes(m.id)} onChange={() => set({ models: toggle(filters.models, m.id) })} />{m.name}<span className={styles.count}>{fa(listingsOfModel(m.id).length)}</span></label>
          ))}</div>
          <div className={styles.label}>شهر</div>
          <div className={styles.cities}>{CITIES.map((c) => <button key={c.name} className={styles.pill} data-on={filters.cities.includes(c.name)} aria-pressed={filters.cities.includes(c.name)} onClick={() => set({ cities: toggle(filters.cities, c.name) })}>{c.name}</button>)}</div>
          <div className={styles.rangeHead}><span>حداکثر قیمت</span><b>{num(filters.maxPrice)} میلیون</b></div>
          <input type="range" min={300} max={1400} step={10} value={filters.maxPrice} onChange={(e) => set({ maxPrice: Number(e.target.value) })} className={styles.range} aria-label="حداکثر قیمت" />
          <div className={styles.rangeHead}><span>حداکثر کارکرد</span><b>{fa(filters.maxKm)} هزار کیلومتر</b></div>
          <input type="range" min={10} max={250} step={5} value={filters.maxKm} onChange={(e) => set({ maxKm: Number(e.target.value) })} className={styles.range} aria-label="حداکثر کارکرد" />
          <div className={styles.label}>گیربکس</div>
          <div className={styles.gears}>{GEARS.map((g) => <button key={g} className={styles.gear} data-on={filters.gear === g} aria-pressed={filters.gear === g} onClick={() => set({ gear: g })}>{g}</button>)}</div>
          <label className={`${styles.check} ${styles.onlyBelow}`}><input type="checkbox" checked={filters.onlyBelow} onChange={() => set({ onlyBelow: !filters.onlyBelow })} />فقط ارزان‌تر از بازار</label>
          <button className={styles.deskReset} onClick={onReset}>پاک‌کردن فیلترها</button>
        </div>
        <div className={styles.sheetFoot}><button className={styles.apply} onClick={onClose}>نمایش {fa(resultCount)} آگهی</button></div>
      </aside>
      {open && <div className={styles.backdrop} onClick={onClose} />}
    </>
  );
}
```

CSS: selected state via `[data-on="true"]{border-color:var(--red);background:var(--red-soft);color:var(--red-ink)}`; inputs `accent-color:var(--red)`. Desktop: `.sheetHead,.sheetFoot,.backdrop{display:none}`, panel sticky `top:84px`. Mobile: `.panel{display:none; position:fixed; inset:auto 0 0 0; max-height:85vh; border-radius:20px 20px 0 0; border:0; z-index:76; box-shadow:0 -12px 40px rgba(23,32,51,.18); animation:tk-sheet .25s ease-out; padding:12px 16px 16px; overflow:hidden}`, `.panel[data-open="true"]{display:flex;flex-direction:column}`, `.body{flex:1;overflow-y:auto;min-height:0}`, `.sheetHead{display:flex}`, `.sheetFoot{display:block; padding-bottom:calc(12px + env(safe-area-inset-bottom))}`, `.deskHead,.deskReset{display:none}`, `.backdrop{display:block;position:fixed;inset:0;background:rgba(23,32,51,.45);z-index:74}`, labels/buttons `min-height:40px`.

- [ ] **Step 4: `ParsedChips`** (lines 220–225; props `{ chips: string[] }`), **`ModelCard`** (lines 247–252; props `{ range: ModelRange }`; link `/model/${range.id}`; bar `style={{ right: `${range.barStartPct}%`, width: `${range.barWidthPct}%` }}`), **`ResultsToolbar`** (lines 227–242 + mobile rules 66–78).

`ResultsToolbar` props: `{ countFa: string; subtitle: string; filtersLabel: string; onOpenFilters(): void; sort: SortKey; onSort(s: SortKey): void; onSave(): void }`. Save label: `loggedIn ? "ذخیره و هشدار قیمت" : "هشدار قیمت (ورود)"` (from `useAppState`). Sort options: `score` بهترین ارزش خرید · `price` ارزان‌ترین · `km` کم‌کارکردترین · `new` جدیدترین. Mobile grid: `grid-template-areas:"count save" "filter sort"; grid-template-columns:1fr 1fr`, subtitle and save label hidden, filter button visible.

- [ ] **Step 5: Verify** in browser: `/results?q=دنا پلاس اتومات زیر یک میلیارد` shows chips «دنا پلاس · زیر ۱,۰۰۰ میلیون · اتوماتیک», Dena checkbox checked, price slider at 1000, one model card, only automatic Dena ≤ 1000. Header search shows the query. Sorting works. Reset clears filters and URL. Logged-out save → bell opens + toast; logged-in save → alert appears in bell. At 390px: filter sheet opens/closes, body scroll locked, "نمایش N آگهی" closes. `bun run lint && bunx tsc --noEmit && bun run build`.

- [ ] **Step 6: Commit** — `feat(frontend): add results page with NL-parsed filters`

---

### Task 10: Map and model page

**Files:**
- Create (each + `.module.css` where styled): `ListingsMap`, `MapCard`, `ListingRow`, `PriceHistogram`, `IssueBars`, `Breadcrumbs`, `ModelScreen`
- Create: `frontend/src/app/model/[id]/page.tsx`

**Interfaces:**
- Produces: `<MapCard title hint height? listings single? />` (client; dynamically loads `ListingsMap`), `<Breadcrumbs items={{ label: string; href?: string }[]} />`, `<ListingRow card={CardView} />`.

- [ ] **Step 1: `ListingsMap.tsx`** (port of `syncMap`, lines 838–850)

```tsx
"use client";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { RED } from "@/lib/catalog";
import { fa, num } from "@/lib/format";
import { verdictOf } from "@/lib/pricing";
import type { Listing } from "@/lib/types";

const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const SINGLE_ZOOM = 13;
const APPROXIMATE_RADIUS_M = 900;
const BOUNDS_PADDING = 0.3;

export default function ListingsMap({ listings, single = false }: { listings: Listing[]; single?: boolean }) {
  const elementRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (!elementRef.current || listings.length === 0) return;
    const map = L.map(elementRef.current, { scrollWheelZoom: !single });
    L.tileLayer(TILE_URL, { attribution: "© OpenStreetMap" }).addTo(map);
    for (const l of listings) {
      L.circleMarker([l.lat, l.lng], { radius: 9, color: "#fff", weight: 2, fillColor: verdictOf(l.diffPct).color, fillOpacity: 0.95 })
        .bindTooltip(`${l.modelName} ${fa(l.year)} · ${num(l.price)} میلیون`, { direction: "top" })
        .on("click", () => router.push(`/listing/${l.id}`)).addTo(map);
    }
    if (single) {
      const [only] = listings;
      L.circle([only.lat, only.lng], { radius: APPROXIMATE_RADIUS_M, color: RED, weight: 1, fillColor: RED, fillOpacity: 0.12 }).addTo(map);
      map.setView([only.lat, only.lng], SINGLE_ZOOM);
    } else {
      map.fitBounds(L.latLngBounds(listings.map((l) => [l.lat, l.lng] as [number, number])).pad(BOUNDS_PADDING));
    }
    return () => { map.remove(); };
  }, [listings, single, router]);

  return <div ref={elementRef} style={{ width: "100%", height: "100%", background: "#eef0f3", position: "relative", zIndex: 0, isolation: "isolate" }} />;
}
```

Callers must pass a **stable** `listings` array (memoized), or the map re-creates on every render.

- [ ] **Step 2: `MapCard.tsx`** (card chrome from lines 339–342 / 396–399)

```tsx
"use client";
import dynamic from "next/dynamic";
import type { Listing } from "@/lib/types";
import styles from "./MapCard.module.css";

const ListingsMap = dynamic(() => import("./ListingsMap"), { ssr: false });

interface Props { title: string; hint: string; listings: Listing[]; single?: boolean; sticky?: boolean; }

export function MapCard({ title, hint, listings, single = false, sticky = false }: Props) {
  return (
    <div className={`${styles.card} ${sticky ? styles.sticky : styles.fixed}`}>
      <div className={styles.head}><span className={styles.title}>{title}</span><span className={styles.hint}>{hint}</span></div>
      <div className={styles.map}><ListingsMap listings={listings} single={single} /></div>
    </div>
  );
}
```

CSS: `.sticky{position:sticky;top:84px;height:calc(100vh - 108px);display:flex;flex-direction:column}` with `.map{flex:1}`; `.fixed .map{height:260px}`. Mobile: `.sticky{position:static;height:auto}` and `.sticky .map{height:260px;flex:none}`.

- [ ] **Step 3: `Breadcrumbs`** (line 286), **`ListingRow`** (lines 322–334; props `{ card: CardView }`; third meta line `${card.body} · بیمه ${card.insFa} ماه`; uses `<VerdictBadge size="sm" />`), **`PriceHistogram`** (lines 293–305; props `{ buckets: HistogramBucket[]; minFa: string; maxFa: string }`; bar `style={{ height: `${b.heightPct}%`, background: b.isMedian ? "var(--red)" : "var(--line)" }}`, `title={b.tip}`), **`IssueBars`** (lines 306–314; props `{ issues: IssueBar[] }`; fill color `neg ? var(--red) : var(--green)`).

- [ ] **Step 4: `ModelScreen.tsx`**

```tsx
"use client";
import { useMemo } from "react";
import { num } from "@/lib/format";
import { LISTINGS } from "@/lib/listings";
import { modelStats } from "@/lib/modelStats";
import { cardOf } from "@/lib/view";
import { useAppState } from "@/state/AppState";
import { Breadcrumbs } from "./Breadcrumbs";
import { Icon } from "./Icon";
import { IssueBars } from "./IssueBars";
import { ListingRow } from "./ListingRow";
import { MapCard } from "./MapCard";
import { PriceHistogram } from "./PriceHistogram";
import styles from "./ModelScreen.module.css";

export function ModelScreen({ modelId }: { modelId: string }) {
  const { addAlert } = useAppState();
  const stats = useMemo(() => modelStats(modelId, LISTINGS), [modelId]);
  const saveAlert = () => addAlert({ title: stats.model.name, threshold: stats.alertThreshold, matches: stats.listings.filter((l) => l.price < stats.median * 0.9).length });

  return (
    <section className={styles.screen}>
      <Breadcrumbs items={[{ label: "خانه", href: "/" }, { label: "جست‌وجو", href: "/results" }, { label: stats.model.name }]} />
      <div className={styles.head}>
        <div><h1 className={styles.name}>{stats.model.name}</h1><div className={styles.sub}>{stats.countFa} آگهی فعال · سال‌های {stats.yearRange} · میانهٔ قیمت <b>{num(stats.median)}</b> میلیون</div></div>
        <button className={styles.alert} onClick={saveAlert}><Icon name="bell" size={16} />هشدار قیمت زیر {num(stats.alertThreshold)} میلیون</button>
      </div>
      <div className={styles.topGrid}>
        <PriceHistogram buckets={stats.buckets} minFa={num(stats.min)} maxFa={num(stats.max)} />
        <IssueBars issues={stats.issues} />
      </div>
      <div className={styles.bottomGrid}>
        <div>
          <div className={styles.listHead}><h2>آگهی‌ها به ترتیب ارزش خرید</h2><span>قیمت نسبت به بازار + کارکرد + بدنه</span></div>
          <div className={styles.rows}>{stats.listings.map((l) => <ListingRow key={l.id} card={cardOf(l)} />)}</div>
        </div>
        <MapCard sticky title="آگهی‌ها روی نقشه" hint="رنگ نقطه = قیمت نسبت به بازار · کلیک = آگهی" listings={stats.listings} />
      </div>
    </section>
  );
}
```

Replace the literal `0.9` with an exported constant from `modelStats.ts` (`export const ALERT_FRACTION_OF_MEDIAN = 0.9`). CSS: `.topGrid` = line 292 (`1.4fr 1fr`), `.bottomGrid` = line 317 (`1fr 1fr`); both single-column on mobile; `.head button` full-width centered on mobile, h1 22px.

- [ ] **Step 5: `app/model/[id]/page.tsx`** (server)

```tsx
import { notFound } from "next/navigation";
import { ModelScreen } from "@/components/ModelScreen";
import { MODELS, findModel } from "@/lib/catalog";

export const generateStaticParams = () => MODELS.map((m) => ({ id: m.id }));

export default async function ModelPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!findModel(id)) notFound();
  return <ModelScreen modelId={id} />;
}
```

- [ ] **Step 6: Verify** `/model/dena`: histogram has one red bar, issue bars, rows sorted by score, map fits markers, marker click opens listing route, alert button works per login state; `/model/xyz` → 404. Mobile: stacked, map 260px. Lint + tsc + build.

- [ ] **Step 7: Commit** — `feat(frontend): add model page with histogram, insights and map`

---

### Task 11: Listing page

**Files:**
- Create (each + `.module.css`): `Gallery`, `SummaryCard`, `SpecsGrid`, `SellerText`, `PriceCard`, `SellerAssessmentCard`, `BreakdownCard`, `SimilarListings`, `ListingScreen`
- Create: `frontend/src/app/listing/[id]/page.tsx`

**Interfaces:** Produces `<BreakdownCard>` and `<SimilarListings title cards />` reused by Task 12.

- [ ] **Step 1: `app/listing/[id]/page.tsx`** (server)

```tsx
import { notFound } from "next/navigation";
import { ListingScreen } from "@/components/ListingScreen";
import { LISTINGS, findListing } from "@/lib/listings";

export const generateStaticParams = () => LISTINGS.map((l) => ({ id: l.id }));

export default async function ListingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!findListing(id)) notFound();
  return <ListingScreen listingId={id} />;
}
```

- [ ] **Step 2: Components**

- `Gallery` (lines 355–363) — client; props `{ photos: string[]; title: string }`; local `selected` index; hero `aspect-ratio:16/10`, count badge `${fa(photos.length)} عکس`, thumbnails grid of 6 as `<button aria-label={`عکس ${fa(i+1)}`} aria-pressed>` with `border: 2px solid ${i===selected ? red : transparent}; opacity: i===selected ? 1 : .75`.
- `SummaryCard` (365–377) — props `{ summary: string; tags: string[] }`; tag colors: negative → `var(--red-soft)`/`var(--red-ink)`, positive → `var(--green-soft)`/`var(--green)` via `isNegativeIssue`.
- `SpecsGrid` (378–385) — props `{ specs: { k: string; v: string }[] }`.
- `SellerText` (386–394) — props `{ desc: string; links: { text: string; href: string }[] }`; `white-space: pre-line`.
- `PriceCard` (404–418) — client; props `{ listing: Listing; card: CardView }`; uses `useAppState()`: compare button label `inCompare ? "✓ در مقایسه" : "+ مقایسه"` (selected styling as filters' `data-on`), bookmark `fill={saved ? "#172033" : "none"}` with `aria-pressed`; Divar link `https://divar.ir/v/-/${listing.token}` `target="_blank" rel="noopener"`; quick facts: کارکرد `num(km)`, مدل (سال تولید) `fa(year)`, رنگ `color`.
- `SellerAssessmentCard` (420–428) — props `{ assess: SellerAssessment }`; rows موتور / وضعیت شاسی‌ها / بدنه / گیربکس; `ok = value.startsWith("سالم")` → `✓` green on green-soft, else `!` orange on orange-soft.
- `BreakdownCard` (430–446) — props `{ verdict: Verdict; diffText: string; rows: BreakdownRow[]; estFa: string; priceFa: string; note: string }`; header background `verdict.bg`.
- `SimilarListings` (448–459) — props `{ title: string; cards: CardView[] }`; renders `<MiniListing>` list; renders nothing when `cards` is empty.

- [ ] **Step 3: `ListingScreen.tsx`**

```tsx
"use client";
import { useMemo } from "react";
import { fa, num } from "@/lib/format";
import { LISTINGS, findListing } from "@/lib/listings";
import { breakdownRows, summaryOf, verdictNote } from "@/lib/pricing";
import type { Listing } from "@/lib/types";
import { cardOf } from "@/lib/view";
// + component imports
import styles from "./ListingScreen.module.css";

const SIMILAR_COUNT = 3;
const TOMAN_PER_MILLION = 1e6;

function similarTo(listing: Listing): Listing[] {
  return LISTINGS.filter((x) => x.modelId === listing.modelId && x.id !== listing.id)
    .sort((a, b) => Math.abs(a.price - listing.price) - Math.abs(b.price - listing.price)).slice(0, SIMILAR_COUNT);
}

function specsOf(l: Listing): { k: string; v: string }[] {
  return [
    ["برند و مدل", l.modelName], ["سال ساخت", fa(l.year)], ["کارکرد", `${num(l.km)} کیلومتر`], ["رنگ", l.color], ["گیربکس", l.gear], ["نوع سوخت", "بنزین"],
    ["وضعیت بدنه", l.body.name], ["قیمت پایه (فروشنده)", `${num(l.price * TOMAN_PER_MILLION)} تومان`], ["مهلت بیمهٔ شخص ثالث", `${fa(l.ins)} ماه`], ["محل", `${l.city}، ${l.district}`], ["منبع", "دیوار"],
  ].map(([k, v]) => ({ k, v }));
}

export function ListingScreen({ listingId }: { listingId: string }) {
  const listing = findListing(listingId);
  if (!listing) throw new Error(`Listing ${listingId} not found`); // page.tsx already 404s unknown ids
  const card = cardOf(listing);
  const mapListings = useMemo(() => [listing], [listing]);
  const modelHref = `/model/${listing.modelId}`;
  const cityQuery = `${listing.modelName} ${listing.city}`;

  return (
    <section className={styles.screen}>
      <Breadcrumbs items={[{ label: "خانه", href: "/" }, { label: listing.modelName, href: modelHref }, { label: card.title }]} />
      <div className={styles.grid}>
        <div className={styles.mainCol}>
          <Gallery key={listing.id} photos={listing.photos} title={card.title} />
          <SummaryCard summary={summaryOf(listing)} tags={listing.tags} />
          <SpecsGrid specs={specsOf(listing)} />
          <SellerText desc={listing.desc} links={[{ text: listing.modelName, href: modelHref }, { text: `${listing.modelName} در ${listing.city}`, href: `/results?q=${encodeURIComponent(cityQuery)}` }]} />
          <MapCard title="محل خودرو" hint={`${listing.city}، ${listing.district} · محدودهٔ تقریبی`} listings={mapListings} single />
        </div>
        <div className={styles.sideCol}>
          <PriceCard listing={listing} card={card} />
          <SellerAssessmentCard assess={listing.assess} />
          <BreakdownCard verdict={card.verdict} diffText={card.diffText} rows={breakdownRows(listing)} estFa={num(listing.est)} priceFa={card.priceFa} note={verdictNote(listing)} />
          <SimilarListings title="آگهی‌های مشابه" cards={similarTo(listing).map(cardOf)} />
        </div>
      </div>
    </section>
  );
}
```

Hooks rule: move the `throw` below `useMemo` or compute `mapListings` from `listingId` — hooks must not follow an early exit. Simplest: `const listing = useMemo(() => findListing(listingId), [listingId])`, then `const mapListings = useMemo(() => (listing ? [listing] : []), [listing])`, then throw.

CSS: `.grid` = line 352 (`1.5fr 1fr`, gap 20px), `.sideCol` sticky `top:84px`; mobile: single column, `.sideCol{position:static}`.

- [ ] **Step 4: Verify** `/listing/l20`: gallery switches photos, compare toggles (4th add → toast), bookmark toggles, Divar link opens new tab, breakdown rows colored, similar links navigate and gallery resets, map shows radius circle, crumbs chip opens results. `/listing/zzz` → 404. Mobile: stacked. Lint + tsc + build.

- [ ] **Step 5: Commit** — `feat(frontend): add listing page with verdict breakdown and gallery`

---

### Task 12: Compare and estimate pages

**Files:**
- Create (each + `.module.css`): `CompareTable`, `EstimateForm`, `EstimateResultCard`
- Create: `frontend/src/app/compare/page.tsx` + `page.module.css`, `frontend/src/app/estimate/page.tsx` + `page.module.css`

- [ ] **Step 1: `app/compare/page.tsx`** (client; lines 467–496)

```tsx
"use client";
import Link from "next/link";
import { CompareTable } from "@/components/CompareTable";
import { findListing } from "@/lib/listings";
import type { Listing } from "@/lib/types";
import { useAppState } from "@/state/AppState";
import styles from "./page.module.css";

export default function ComparePage() {
  const { compare, removeFromCompare } = useAppState();
  const cars = compare.map(findListing).filter((l): l is Listing => l !== undefined);
  return (
    <section className={styles.screen}>
      <h1 className={styles.title}>مقایسه</h1>
      <p className={styles.lead}>تا سه خودرو رو از صفحهٔ آگهی به مقایسه اضافه کن.</p>
      {cars.length === 0
        ? <div className={styles.empty}>هنوز چیزی برای مقایسه انتخاب نکردی.<div><Link href="/results" className={styles.cta}>برو به آگهی‌ها</Link></div></div>
        : <CompareTable cars={cars} onRemove={removeFromCompare} />}
    </section>
  );
}
```

`CompareTable` props `{ cars: Listing[]; onRemove(id: string): void }`: header row (photo 16/10, title link, meta, `×` remove button with `aria-label="حذف از مقایسه"`), then `compareRows(cars)`; grid columns `160px repeat(${cars.length}, minmax(0,1fr))` as inline style; cell `style={{ color: cell.color, background: cell.best ? "var(--green-soft)" : "transparent" }}`. Mobile: wrap the table in `overflow-x:auto` and use `110px repeat(n, minmax(140px,1fr))`.

- [ ] **Step 2: `app/estimate/page.tsx`** (client; lines 501–545)

```tsx
"use client";
import { useMemo, useState } from "react";
import { BreakdownList } from "@/components/BreakdownList";
import { EstimateForm } from "@/components/EstimateForm";
import { EstimateResultCard } from "@/components/EstimateResultCard";
import { SimilarListings } from "@/components/SimilarListings";
import { estimate, type EstimateInput } from "@/lib/estimate";
import { LISTINGS } from "@/lib/listings";
import { cardOf } from "@/lib/view";
import styles from "./page.module.css";

const INITIAL: EstimateInput = { modelId: "206", year: 1401, kmThousands: 80, bodyIndex: 0, gear: "دنده‌ای", asking: "" };

export default function EstimatePage() {
  const [input, setInput] = useState<EstimateInput>(INITIAL);
  const result = useMemo(() => estimate(input, LISTINGS), [input]);
  return (
    <section className={styles.grid}>
      <EstimateForm input={input} result={result} onChange={(patch) => setInput((i) => ({ ...i, ...patch }))} />
      <div className={styles.results}>
        <EstimateResultCard result={result} />
        <BreakdownList title="چطور حساب شد؟" rows={result.breakdown} />
        <SimilarListings title="آگهی‌های مشابه الان در بازار" cards={result.similar.map(cardOf)} />
      </div>
    </section>
  );
}
```

- `BreakdownList` — create `components/BreakdownList.tsx` (lines 526–531; props `{ title: string; rows: BreakdownRow[] }`) and **refactor `BreakdownCard` (Task 11) to render its rows through the same row markup** (export a shared `BreakdownRows` from `BreakdownList.tsx`).
- `EstimateForm` props `{ input: EstimateInput; result: EstimateResult; onChange(patch: Partial<EstimateInput>): void }`: model `<select>` from `MODELS`; year `<select>` from `result.years` with **`value={result.year}`**; km range 0–300 step 5 with `fa(input.kmThousands)`; body `<select>` from `BODIES` by index; gear buttons from `result.model.gears` with `data-on={g === result.gear}`; asking `<input type="text" inputMode="numeric" dir="ltr">` (text, not number, so Persian digits are accepted — `estimate` runs `en()`), placeholder `مثلاً ۶۵۰`. Every control has a visible `<label>`.
- `EstimateResultCard` (lines 515–525) props `{ result: EstimateResult }`: dark card; `تخمین ترب‌کار برای {title}`, `num(est)`, `بازهٔ منطقی: num(low) تا num(high) میلیون · بر اساس fa(similarCount) آگهی فعال`; when `result.asking`: `<VerdictBadge>` + `asking.text`.

CSS grid = line 501 (`1fr 1.3fr`, gap 20px), single column on mobile.

- [ ] **Step 3: Verify**: compare empty state; add 2–3 cars from listing pages → best cells green, remove works, state survives reload (localStorage), chat suggestion «بین این‌ها کدوم به‌صرفه‌تره؟» appears and answers. Estimate: changing model to جک J4 switches gear to اتوماتیک and year to a valid one; asking `۲۰۰۰` shows «بالاتر از بازار». `bun test && bun run lint && bunx tsc --noEmit && bun run build`.

- [ ] **Step 4: Commit** — `feat(frontend): add compare and price-estimate pages`

---

### Task 13: PWA, not-found, final verification

**Files:**
- Create: `frontend/src/app/manifest.ts`, `frontend/src/app/not-found.tsx` + `not-found.module.css`, `frontend/public/icons/icon-192.png`, `icon-512.png`, `apple-touch-icon.png`
- Modify: `frontend/src/app/layout.tsx` (metadata icons), `README.md` (create at repo root: how to run the frontend)

- [ ] **Step 1: Icons** (macOS `sips`, from repo root)

```bash
mkdir -p frontend/public/icons
sips -z 192 192 prototype/assets/logo.png --out frontend/public/icons/icon-192.png
sips -z 512 512 prototype/assets/logo.png --out frontend/public/icons/icon-512.png
sips -z 180 180 prototype/assets/logo.png --out frontend/public/icons/apple-touch-icon.png
```

- [ ] **Step 2: `src/app/manifest.ts`**

```ts
import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ترب‌کار", short_name: "ترب‌کار", description: "ماشین می‌خوای؟ فقط بگو چی.",
    start_url: "/", display: "standalone", dir: "rtl", lang: "fa",
    theme_color: "#d9232e", background_color: "#f6f7f9",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
```

In `layout.tsx` metadata add: `icons: { icon: "/icons/icon-192.png", apple: "/icons/apple-touch-icon.png" }, appleWebApp: { capable: true, title: "ترب‌کار", statusBarStyle: "default" }`.

- [ ] **Step 3: `not-found.tsx`** (server): centered card in the dashed empty-state style — `<h1>این صفحه پیدا نشد</h1>`, `<p>آگهی یا مدلی با این نشانی نداریم.</p>`, `<Link href="/">برگشت به خانه</Link>` styled as the red CTA.

- [ ] **Step 4: README.md** (repo root): project one-liner, `cd frontend && bun install && bun run dev`, test/lint/build commands, note that data is synthetic and `prototype/` is the design reference, AGPL note for the avatar package.

- [ ] **Step 5: Full verification**

```bash
cd frontend && bun test && bun run lint && bunx tsc --noEmit && bun run build && bun run start
```

In a browser (use the `/browse` skill), at 1280px and 390px, walk: `/` → example chip → results → model card → model page → listing → add to compare ×2 → `/compare` → chat compare question → `/estimate` → unknown `/listing/x`. Check: no console errors, no hydration warnings, no horizontal scroll at 390px, keyboard focus visible on all controls, `/manifest.webmanifest` serves, Chrome DevTools → Application → Manifest shows installable with no errors. Compare each screen side-by-side with `prototype/Torobcar.dc.html` and fix visual drift.

- [ ] **Step 6: Commit** — `feat(frontend): add PWA manifest, icons, not-found page and README`

---

## Self-Review Notes

- Spec coverage: routes (T8–T12), lib modules (T2–T5; `view/modelStats/compare/estimate` added as pure screen view-models so page logic stays testable), state + persistence (T6), components (T7–T12), responsive rules (each UI task + convention §6), PWA (T13), assets (T1, T13), error handling (T6 storage, T7 avatar fallback, T10/T11 `notFound`, T9/T12 empty states), testing (T2–T5, T13).
- Deliberate deviation from spec wording: `ChatMessage.cardIds` stores ids rather than card objects so persisted/serializable state stays small; cards are derived at render.