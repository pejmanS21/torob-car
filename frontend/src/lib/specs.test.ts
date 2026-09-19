import { expect, test } from "bun:test";
import listing from "./api/__fixtures__/listing.json";
import type { ListingDetail } from "./api/types";
import { specsOf } from "./specs";

const detail = listing as ListingDetail;

test("specsOf lists typed fields and Divar attributes, hiding empty rows", () => {
  const rows = specsOf(detail);
  const keys = rows.map((r) => r.k);
  expect(keys).toContain("برند و مدل");
  expect(keys).toContain("گیربکس");
  expect(keys).toContain("مالکیت"); // from attributes
  expect(rows.every((r) => r.v !== "")).toBe(true);
  expect(keys).not.toContain("وضعیت بدنه"); // null for this car
});

test("motorcycles show engine size from attributes and no gearbox row", () => {
  const moto: ListingDetail = {
    ...detail, category: "motorcycle", gearbox: null, fuel: null, body_condition: "intact",
    attributes: { "حجم موتور": "۱۶۰ سی‌سی", "نوع کلاچ": "اتوماتیک" },
  };
  const rows = specsOf(moto);
  expect(rows.find((r) => r.k === "حجم موتور")?.v).toBe("۱۶۰ سی‌سی");
  expect(rows.find((r) => r.k === "نوع کلاچ")?.v).toBe("اتوماتیک");
  expect(rows.find((r) => r.k === "وضعیت بدنه")?.v).toBe("سالم و بی‌خط و خش");
  expect(rows.some((r) => r.k === "گیربکس")).toBe(false);
});
