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
