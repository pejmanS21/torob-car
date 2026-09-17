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
