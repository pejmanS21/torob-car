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
