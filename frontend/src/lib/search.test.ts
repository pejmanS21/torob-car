import { expect, test } from "bun:test";
import { activeFilterCount, paramsToQuery, queryToParams } from "./search";

test("queryToParams keeps valid values and drops junk", () => {
  const query = new URLSearchParams("q=۲۰۶&category=light&models=پژو 206&models=دنا&cities=تهران&year=1398&price_max=900000000&km_max=abc&gearbox=auto&only_below=true&sort=price&page=3");
  expect(queryToParams(query)).toEqual({
    q: "۲۰۶", category: "light", models: ["پژو 206", "دنا"], cities: ["تهران"], year: 1398, price_max: 900000000, only_below: true, sort: "price",
  });
  expect(queryToParams(new URLSearchParams("category=spaceship&sort=random&year=-5"))).toEqual({});
});

test("paramsToQuery round-trips and omits defaults", () => {
  const params = { q: "دنا", cities: ["کرج"], price_max: 1_000_000_000, sort: "relevance" as const, only_below: false };
  const query = paramsToQuery(params);
  expect(query).not.toContain("sort=");
  expect(query).not.toContain("only_below");
  expect(queryToParams(new URLSearchParams(query))).toEqual({ q: "دنا", cities: ["کرج"], price_max: 1_000_000_000 });
  expect(paramsToQuery({})).toBe("");
});

test("activeFilterCount counts every set filter", () => {
  expect(activeFilterCount({})).toBe(0);
  expect(activeFilterCount({ q: "x", models: ["a", "b"], km_max: 100000, only_below: true, category: "light" })).toBe(5);
});
