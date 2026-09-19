import { expect, test } from "bun:test";
import { en, fa, formatToman, num, relativeTime } from "./format";

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
test("formatToman uses the backend's millions/billions wording", () => {
  expect(formatToman(970_000_000)).toBe("۹۷۰ میلیون");
  expect(formatToman(1_200_000_000)).toBe("۱.۲ میلیارد");
  expect(formatToman(1_000_000_000)).toBe("۱ میلیارد");
  expect(formatToman(1_155_000_000)).toBe("۱.۱۶ میلیارد");
  expect(formatToman(4_598_198)).toBe("۵ میلیون");
});
test("relativeTime buckets the age of a listing against the data snapshot", () => {
  const asOf = "2026-09-17T16:43:20Z";
  expect(relativeTime("2026-09-17T16:20:00Z", asOf)).toBe("دقایقی پیش");
  expect(relativeTime("2026-09-17T10:38:38Z", asOf)).toBe("۶ ساعت پیش");
  expect(relativeTime("2026-09-16T12:00:00Z", asOf)).toBe("دیروز");
  expect(relativeTime("2026-09-14T12:12:31Z", asOf)).toBe("۳ روز پیش");
  expect(relativeTime("2026-09-01T12:00:00Z", asOf)).toBe("۲ هفته پیش");
  expect(relativeTime("2026-06-01T12:00:00Z", asOf)).toBe("۳ ماه پیش");
  expect(relativeTime(null, asOf)).toBe("");
});
