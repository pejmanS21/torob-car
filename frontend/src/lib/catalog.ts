import type { BodyCondition, CarModel, City, Issue } from "./types";

export const RED = "#d9232e";
export const GREEN = "#15803d";
export const AMBER = "#b45309";
export const ORANGE = "#c2410c";
export const NOW_YEAR = 1404;

const DIVAR_PHOTO_BASE = "https://s100.divarcdn.com/static/photo/neda/webp_post";
const PHOTO_PATHS = [
  "VtwerECSMoAG8xi-0kC7oQ/d6cac8f1-a686-4d78-9fb7-78e0e9f44537",
  "pF8zpcoW7jmJn_kE_nVDKw/0171c012-4d3c-41d6-8d85-10eb1f658765",
  "p6BCJ0OiFsy7KYY_vpLPzw/3a29ac4f-c735-4be0-a194-94713513af9e",
  "wDQT4zuySrem2eex0N2KZg/5bdbb4d7-37dd-4e3e-b1bb-d3f9e60d6c2c",
  "wcNqNzWJxvELmxsuP3liOQ/a620cd4f-9ffd-4523-9690-de2da05aae84",
  "phH0zzXd5Ybd-GrP5YXajg/ce038931-d702-425c-a0b8-11ebaa9c7f52",
  "lnuorukb89oVrwaKVBnntQ/e07c28a2-7818-4eb3-89f6-d1813aa018df",
  "-sTjsI3ogjHTsdUAJl9HVA/53241d59-563b-4781-9bd4-965158f748f5",
  "B17b9cgejkmcIWogAGPDzQ/eb3c0447-34fb-448b-bb11-b988d373f304",
  "zo0Ub8JHjJMLixJKo6mmSw/76498849-a1a0-4af5-84a3-42961fb6dc27",
  "jqRK4JvydKjm5Ukhe5GMVg/4e28c5a8-1e45-4c68-9af6-c015b20ff61d",
];
export const IMAGES: string[] = PHOTO_PATHS.map((p) => `${DIVAR_PHOTO_BASE}/${p}.webp`);

export const MODELS: CarModel[] = [
  { id: "206", name: "پژو ۲۰۶", aliases: ["206", "۲۰۶"], base: { 1403: 790, 1402: 730, 1401: 670, 1400: 610, 1399: 560, 1398: 510, 1397: 470, 1396: 435 }, gears: ["دنده‌ای"] },
  { id: "dena", name: "دنا پلاس", aliases: ["دنا"], base: { 1403: 1180, 1402: 1090, 1401: 1000, 1400: 920, 1399: 850, 1398: 790 }, gears: ["دنده‌ای", "اتوماتیک"] },
  { id: "tara", name: "تارا", aliases: ["تارا"], base: { 1403: 1260, 1402: 1170, 1401: 1090, 1400: 1010 }, gears: ["دنده‌ای", "اتوماتیک"] },
  { id: "j4", name: "جک J4", aliases: ["جک", "j4", "جی۴"], base: { 1402: 930, 1401: 860, 1400: 800, 1399: 740, 1398: 690 }, gears: ["اتوماتیک"] },
];
export const BODIES: BodyCondition[] = [
  { name: "سالم و بی‌خط و خش", f: 1 }, { name: "خط و خش جزیی", f: 0.98 }, { name: "رنگ‌شدگی، در ۱ ناحیه", f: 0.94 },
  { name: "رنگ‌شدگی، در ۲ ناحیه", f: 0.9 }, { name: "دوررنگ", f: 0.82 }, { name: "تصادفی", f: 0.72 },
];
export const CITIES: City[] = [
  { name: "تهران", lat: 35.72, lng: 51.4, districts: ["پونک", "سعادت‌آباد", "نارمک", "تهرانپارس", "پیروزی", "جنت‌آباد"] },
  { name: "کرج", lat: 35.83, lng: 50.97, districts: ["گوهردشت", "مهرشهر", "عظیمیه", "فردیس"] },
  { name: "اصفهان", lat: 32.66, lng: 51.67, districts: ["خانه اصفهان", "ملک‌شهر", "سپاهان‌شهر", "مرداویج"] },
];
export const COLORS = ["سفید", "مشکی", "نوک‌مدادی", "سفید", "خاکستری", "سفید", "آبی"];
export const POSTED = ["۲ ساعت پیش", "۵ ساعت پیش", "دیروز", "دیروز", "۲ روز پیش", "۳ روز پیش", "هفتهٔ پیش"];
export const ISSUES: Issue[] = [
  { name: "رنگ‌شدگی", neg: true }, { name: "تعویض موتور", neg: true }, { name: "تصادف جزئی", neg: true }, { name: "لاستیک نو", neg: false },
  { name: "معاینه فنی دارد", neg: false }, { name: "فنی سالم", neg: false }, { name: "سند تک‌برگ", neg: false }, { name: "بیمه کامل", neg: false }, { name: "قابلیت معاوضه", neg: false },
];
export const SNIPS: Record<string, string> = {
  "رنگ‌شدگی": "یه گلگیر رنگ داره، بقیه بدنه فابریک.",
  "تعویض موتور": "موتور تعویض شده، فاکتور موجود.",
  "تصادف جزئی": "یه ضربه کوچیک از عقب داشته، صافکاری بدون رنگ.",
  "لاستیک نو": "چهار حلقه لاستیک نو.",
  "معاینه فنی دارد": "معاینه فنی تا آخر سال.",
  "فنی سالم": "فنی سالم، بدون خرج.",
  "سند تک‌برگ": "سند تک‌برگ آماده انتقال.",
  "بیمه کامل": "بیمه بدنه و ثالث کامل.",
  "قابلیت معاوضه": "معاوضه با پایین‌تر انجام می‌شه.",
};

export const findModel = (id: string): CarModel | undefined => MODELS.find((m) => m.id === id);
export const isNegativeIssue = (name: string): boolean => ISSUES.some((i) => i.name === name && i.neg);
