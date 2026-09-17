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
