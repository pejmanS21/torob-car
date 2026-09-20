import { expect, test } from "bun:test";
import type { SearchParams } from "./api/types";
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
  expect(activeFilterCount({ sources: ["divar", "bama"], price_types: ["lumpsum"], document_statuses: ["no_title"] })).toBe(4);
});

test("sources/price_types/document_statuses round-trip and drop junk values", () => {
  const query = new URLSearchParams(
    "sources=divar&sources=bama&sources=ebay&price_types=lumpsum&price_types=cash&document_statuses=no_title&document_statuses=single_page&document_statuses=lost",
  );
  expect(queryToParams(query)).toEqual({
    sources: ["divar", "bama"], price_types: ["lumpsum"], document_statuses: ["no_title", "single_page"],
  });
  const params: SearchParams = { sources: ["karnameh", "hamrah_mechanic"], price_types: ["installment"], document_statuses: ["white_title"] };
  const roundTripped = queryToParams(new URLSearchParams(paramsToQuery(params)));
  expect(roundTripped).toEqual({
    sources: ["karnameh", "hamrah_mechanic"], price_types: ["installment"], document_statuses: ["white_title"],
  });
});
