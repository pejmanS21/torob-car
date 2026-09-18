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
