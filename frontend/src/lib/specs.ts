import type { ListingDetail } from "./api/types";
import { fa, num } from "./format";
import { BODY_NAMES, CATEGORY_NAMES, FUEL_NAMES, GEARBOX_NAMES } from "./labels";

export interface SpecRow { k: string; v: string; }

// Divar attribute keys worth a row on the specs grid (see backend/ingest/column_maps.py).
const ATTRIBUTE_ROWS: [key: string, label: string][] = [
  ["حجم موتور", "حجم موتور"],
  ["مالکیت خودرو", "مالکیت"],
  ["مایل به معاوضه", "معاوضه"],
  ["معاینه فنی", "معاینه فنی"],
  ["وضعیت سند و مدارک", "سند و مدارک"],
  ["وضعیت فنی موتور", "وضعیت فنی موتور"],
  ["وضعیت فنی موتور و گیربکس", "موتور و گیربکس"],
  ["نوع استارت", "نوع استارت"],
  ["نوع کلاچ", "نوع کلاچ"],
  ["وضعیت لاستیک‌ها", "لاستیک‌ها"],
];

const row = (k: string, v: string | null | undefined): SpecRow | null => (v ? { k, v } : null);

/** Per-category spec rows from typed fields plus Divar attributes; empty rows are dropped. */
export function specsOf(l: ListingDetail): SpecRow[] {
  const typed = [
    row("دسته", CATEGORY_NAMES[l.category]),
    row("برند و مدل", l.trim),
    row("سال ساخت", l.year === null ? null : fa(l.year)),
    row("کارکرد", l.km === null ? null : `${num(l.km)} کیلومتر`),
    row("رنگ", l.color),
    row("گیربکس", l.gearbox ? GEARBOX_NAMES[l.gearbox] : null),
    row("نوع سوخت", l.fuel ? FUEL_NAMES[l.fuel] : null),
    row("وضعیت بدنه", l.body_condition ? BODY_NAMES[l.body_condition] : null),
    row("مهلت بیمهٔ شخص ثالث", l.insurance_months === null ? null : `${fa(l.insurance_months)} ماه`),
    row("فروشنده", l.is_dealer ? "نمایشگاه" : "شخصی"),
    row("محل", l.district ? `${l.city}، ${l.district}` : l.city),
  ];
  const attributes = ATTRIBUTE_ROWS.map(([key, label]) => row(label, l.attributes[key]));
  return [...typed, ...attributes].filter((spec): spec is SpecRow => spec !== null);
}
