import { expect, test } from "bun:test";
import { BODIES, MODELS } from "./catalog";
import { diffText, priceModel, scoreColor, verdictOf } from "./pricing";

const peugeot206 = MODELS.find((m) => m.id === "206")!;
const dena = MODELS.find((m) => m.id === "dena")!;
const EXPECTED_KM_FOR_1401 = 62000; // age 3 × 18000 + 8000

test("neutral inputs return the base price", () => {
  const r = priceModel(peugeot206, 1401, EXPECTED_KM_FOR_1401, BODIES[0], "دنده‌ای", 6);
  expect(r.base).toBe(670);
  expect(r.expKm).toBe(EXPECTED_KM_FOR_1401);
  expect(r.est).toBeCloseTo(670, 6);
});
test("est is the product of all factors and parts are base × (factor − 1)", () => {
  const r = priceModel(dena, 1401, 100000, BODIES[2], "اتوماتیک", 12);
  expect(r.est).toBeCloseTo(r.base * BODIES[2].f * r.kmF * r.insF * r.gearF, 6);
  expect(r.parts.body).toBeCloseTo(r.base * (BODIES[2].f - 1), 6);
  expect(r.parts.km).toBeCloseTo(r.base * (r.kmF - 1), 6);
});
test("km factor clamps at +4% and −8%", () => {
  expect(priceModel(peugeot206, 1401, 0, BODIES[0], "دنده‌ای", 6).kmF).toBeCloseTo(1.04, 6);
  expect(priceModel(peugeot206, 1401, 900000, BODIES[0], "دنده‌ای", 6).kmF).toBeCloseTo(0.92, 6);
});
test("automatic premium applies only to models with two gearboxes", () => {
  expect(priceModel(dena, 1401, EXPECTED_KM_FOR_1401, BODIES[0], "اتوماتیک", 6).gearF).toBe(1.06);
  const j4 = MODELS.find((m) => m.id === "j4")!;
  expect(priceModel(j4, 1401, EXPECTED_KM_FOR_1401, BODIES[0], "اتوماتیک", 6).gearF).toBe(1);
});
test("unknown model year throws", () => {
  expect(() => priceModel(peugeot206, 1380, 1000, BODIES[0], "دنده‌ای", 6)).toThrow(RangeError);
});
test("verdict thresholds are −5 and +6", () => {
  expect(verdictOf(-5).label).toBe("ارزان‌تر از بازار");
  expect(verdictOf(-4.9).label).toBe("قیمت منصفانه");
  expect(verdictOf(5.9).label).toBe("قیمت منصفانه");
  expect(verdictOf(6).label).toBe("بالاتر از بازار");
});
test("diffText and scoreColor", () => {
  expect(diffText(7.4)).toBe("۷٪ بالاتر از تخمین");
  expect(diffText(-12)).toBe("۱۲٪ ارزان‌تر از تخمین");
  expect(diffText(0.2)).toBe("برابر تخمین بازار");
  expect(scoreColor(70)).toBe("#15803d");
  expect(scoreColor(45)).toBe("#b45309");
  expect(scoreColor(44)).toBe("#d9232e");
});
