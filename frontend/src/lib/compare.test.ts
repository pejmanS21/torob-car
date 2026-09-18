import { expect, test } from "bun:test";
import search from "./api/__fixtures__/search.json";
import type { ListingCard, SearchResponse } from "./api/types";
import { compareRows } from "./compare";

const cards = (search as SearchResponse).items.slice(0, 3);

test("compareRows: 9 rows, lowest price marked best, single card marks nothing", () => {
  const rows = compareRows(cards);
  expect(rows).toHaveLength(9);
  expect(rows.map((r) => r.label)).toEqual(["قیمت", "نسبت به بازار", "ارزش خرید", "سال ساخت", "کارکرد", "گیربکس", "وضعیت بدنه", "بیمه", "شهر"]);
  const prices = cards.map((c) => c.price ?? Infinity);
  expect(rows[0].cells[prices.indexOf(Math.min(...prices))].best).toBe(true);
  expect(compareRows([cards[0]]).flatMap((r) => r.cells).some((c) => c.best)).toBe(false);
  expect(compareRows([])).toEqual([]);
});

test("unknown values render as a dash and never win a row", () => {
  const unknown: ListingCard = { ...cards[0], price: null, deal_score: null, diff_pct: null, gearbox: null, insurance_months: null };
  const rows = compareRows([unknown, cards[1]]);
  expect(rows[0].cells[0].text).toBe("توافقی");
  expect(rows[0].cells[0].best).toBe(false);
  expect(rows[0].cells[1].best).toBe(true);
  expect(rows[2].cells[0].text).toBe("—");
  expect(rows[5].cells[0].text).toBe("—");
});
