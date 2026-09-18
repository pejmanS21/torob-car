import { expect, test } from "bun:test";
import estimate from "./api/__fixtures__/estimate.json";
import listing from "./api/__fixtures__/listing.json";
import type { EstimateResponse, ListingDetail } from "./api/types";
import { formatToman } from "./format";
import { basisText, breakdownRows, diffText, estimateBreakdownRows, scoreColor, summaryOf, verdictNote, verdictStyle } from "./pricing";
import { GREEN, NEUTRAL, RED } from "./theme";

const detail = listing as ListingDetail;

test("verdictStyle maps the API enum, including unknown", () => {
  expect(verdictStyle("cheap").label).toBe("ارزان‌تر از بازار");
  expect(verdictStyle("fair").label).toBe("قیمت منصفانه");
  expect(verdictStyle("expensive").label).toBe("بالاتر از بازار");
  expect(verdictStyle("unknown").color).toBe(NEUTRAL);
});
test("diffText and scoreColor", () => {
  expect(diffText(7.4)).toBe("۷٪ بالاتر از تخمین");
  expect(diffText(-12)).toBe("۱۲٪ ارزان‌تر از تخمین");
  expect(diffText(0.2)).toBe("برابر تخمین بازار");
  expect(diffText(null)).toBe("تخمینی برای این آگهی نداریم");
  expect(scoreColor(70)).toBe(GREEN);
  expect(scoreColor(45)).toBe("#b45309");
  expect(scoreColor(44)).toBe(RED);
});
test("breakdownRows: base, km and insurance from the API breakdown, basis in words", () => {
  const rows = breakdownRows(detail);
  expect(rows.map((r) => r.label)).toEqual(["قیمت پایهٔ تیپ و سال", "کارکرد", "بیمهٔ شخص ثالث"]);
  expect(rows[0].note).toBe(basisText(detail.price_breakdown.est_basis, detail.price_breakdown.est_sample_size));
  expect(rows[0].note).toContain("میانهٔ ۸ آگهی همین تیپ و سال");
  expect(rows[1].val.startsWith("+") || rows[1].val.startsWith("−")).toBe(true);
});
test("breakdownRows is empty without an estimate", () => {
  const none: ListingDetail = { ...detail, price_breakdown: { base: null, km_adjustment: null, insurance_adjustment: null, est_basis: "none", est_sample_size: 0 } };
  expect(breakdownRows(none)).toEqual([]);
});
test("summaryOf and verdictNote use real fields only", () => {
  const summary = summaryOf(detail);
  expect(summary).toContain(detail.trim!);
  expect(summary).toContain("ارزان‌تر از تخمین بازار");
  expect(verdictNote(detail)).toContain("زیر تخمین ماست");
  const noEstimate: ListingDetail = { ...detail, est_price: null, verdict: "unknown" };
  expect(summaryOf(noEstimate)).toContain("تخمین قیمت نداریم");
  expect(verdictNote(noEstimate)).toContain("کافی برای تخمین نداریم");
});
test("estimateBreakdownRows mirrors the /estimates breakdown", () => {
  const rows = estimateBreakdownRows(estimate as EstimateResponse, { category: "light", trim: "x", year: 1397, km: 90000, insurance_months: 6, body_condition: null, asking_price: null });
  expect(rows).toHaveLength(3);
  expect(rows[0].val).toBe(formatToman(estimate.breakdown.base));
  expect(rows[1].note).toBe("۹۰,۰۰۰ کیلومتر");
});
