// Persian names for the API's closed vocabularies (backend/enums.py).
import type { BodyCondition, Category, DocumentStatus, EstimateBasis, Fuel, Gearbox, PriceType, Source, SortKey } from "./api/types";

export const CATEGORY_NAMES: Record<Category, string> = {
  light: "سواری و شاسی‌بلند", heavy: "سنگین و نیمه‌سنگین", motorcycle: "موتورسیکلت", rental: "اجاره", classic: "کلاسیک",
};
export const GEARBOX_NAMES: Record<Gearbox, string> = { manual: "دنده‌ای", automatic: "اتوماتیک" };
export const SOURCE_NAMES: Record<Source, string> = {
  divar: "دیوار", bama: "باما", karnameh: "کارنامه", hamrah_mechanic: "همراه مکانیک",
};
export const PRICE_TYPE_NAMES: Record<PriceType, string> = {
  lumpsum: "نقد", negotiable: "توافقی", installment: "اقساطی",
};
export const DOCUMENT_STATUS_NAMES: Record<DocumentStatus, string> = {
  title_in_name: "سند به نام", ready_to_transfer: "آماده انتقال", white_title: "سند سفید", no_title: "فاقد سند",
  mortgaged: "سند در رهن", single_page: "سند تک‌برگی", two_page: "سند دو‌برگی", multi_page: "سند چندبرگی",
};
export const FUEL_NAMES: Record<Fuel, string> = {
  petrol: "بنزینی", dual_factory: "دوگانه‌سوز شرکتی", dual_aftermarket: "دوگانه‌سوز دستی", hybrid: "هیبرید",
  plugin_hybrid: "پلاگین هیبرید", electric: "برقی", diesel: "گازوئیلی",
};
export const BODY_NAMES: Record<BodyCondition, string> = {
  intact: "سالم و بی‌خط و خش", no_paint: "بدون رنگ", minor_scratches: "خط و خش جزئی", partial_paint: "رنگ‌شدگی جزئی",
  heavy_paint: "رنگ‌شدگی زیاد", dropped: "زمین‌خوردگی", accident: "تصادفی", original: "فابریک", restored: "بازسازی‌شدهٔ کامل",
};
export const BASIS_NAMES: Record<EstimateBasis, string> = {
  trim_year: "همین تیپ و سال", trim_near_year: "همین تیپ، سال‌های مجاور", model_year: "همین مدل و سال",
  model_near_year: "همین مدل، سال‌های مجاور", none: "بدون تخمین",
};
export const SORT_NAMES: Record<SortKey, string> = {
  relevance: "مرتبط‌ترین", deal: "بهترین ارزش خرید", price: "ارزان‌ترین", km: "کم‌کارکردترین", newest: "جدیدترین",
};
/** Categories whose listings carry a body-condition field on Divar. */
export const BODY_CONDITION_CATEGORIES: Category[] = ["motorcycle", "heavy"];
export const CATEGORY_ORDER: Category[] = ["light", "motorcycle", "heavy", "classic", "rental"];
