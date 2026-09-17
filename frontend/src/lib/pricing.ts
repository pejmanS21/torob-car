import { AMBER, GREEN, NOW_YEAR, RED, isNegativeIssue } from "./catalog";
import { fa, num } from "./format";
import type { BodyCondition, BreakdownRow, CarModel, Gear, Listing, PriceModelResult, Verdict } from "./types";

const KM_PER_YEAR = 18000;
const KM_BASELINE = 8000;
const KM_WEIGHT = 0.08;
const INSURANCE_NEUTRAL_MONTHS = 6;
const INSURANCE_WEIGHT_PER_MONTH = 0.002;
const AUTOMATIC_PREMIUM = 1.06;
export const CHEAP_THRESHOLD_PCT = -5;
export const EXPENSIVE_THRESHOLD_PCT = 6;
const NEUTRAL_COLOR = "#667085";
const INK = "#172033";

export function priceModel(model: CarModel, year: number, km: number, body: BodyCondition, gear: Gear, insMonths: number): PriceModelResult {
  const base = model.base[year];
  if (base === undefined) throw new RangeError(`No base price for ${model.id} year ${year}`);
  const age = Math.max(0.5, NOW_YEAR - year);
  const expKm = age * KM_PER_YEAR + KM_BASELINE;
  const kmF = 1 - Math.max(-0.5, Math.min(1, (km - expKm) / expKm)) * KM_WEIGHT;
  const insF = 1 + (insMonths - INSURANCE_NEUTRAL_MONTHS) * INSURANCE_WEIGHT_PER_MONTH;
  const gearF = gear === "اتوماتیک" && model.gears.length > 1 ? AUTOMATIC_PREMIUM : 1;
  const est = base * body.f * kmF * insF * gearF;
  return { base, expKm, kmF, insF, gearF, est, parts: { km: base * (kmF - 1), body: base * (body.f - 1), ins: base * (insF - 1), gear: base * (gearF - 1) } };
}

export function verdictOf(diffPct: number): Verdict {
  if (diffPct <= CHEAP_THRESHOLD_PCT) return { label: "ارزان‌تر از بازار", color: GREEN, bg: "#ecfdf3", icon: "M16 17h6v-6M22 17l-8.5-8.5-5 5L2 7" };
  if (diffPct >= EXPENSIVE_THRESHOLD_PCT) return { label: "بالاتر از بازار", color: RED, bg: "#fdecec", icon: "M16 7h6v6M22 7l-8.5 8.5-5-5L2 17" };
  return { label: "قیمت منصفانه", color: AMBER, bg: "#fffbeb", icon: "M20 6 9 17l-5-5" };
}

export const diffText = (d: number): string =>
  d > 0.5 ? `${fa(Math.abs(d).toFixed(0))}٪ بالاتر از تخمین`
  : d < -0.5 ? `${fa(Math.abs(d).toFixed(0))}٪ ارزان‌تر از تخمین`
  : "برابر تخمین بازار";

export const scoreColor = (score: number): string => (score >= 70 ? GREEN : score >= 45 ? AMBER : RED);

export const signedMillions = (d: number): string => (d >= 0 ? "+" : "−") + num(Math.abs(d));
export const deltaColor = (d: number): string => (Math.abs(d) < 1 ? NEUTRAL_COLOR : d > 0 ? GREEN : RED);

export function breakdownRows(l: Listing): BreakdownRow[] {
  const p = l.pm;
  const rows: BreakdownRow[] = [
    { label: "قیمت پایهٔ مدل و سال", note: `میانهٔ آگهی‌های ${l.modelName} مدل ${fa(l.year)}`, val: `${num(p.base)} میلیون`, color: INK },
    { label: "کارکرد", note: `${num(l.km)} کیلومتر در برابر انتظار ${num(p.expKm)}`, val: signedMillions(p.parts.km), color: deltaColor(p.parts.km) },
    { label: "وضعیت بدنه", note: l.body.name, val: signedMillions(p.parts.body), color: deltaColor(p.parts.body) },
    { label: "بیمهٔ شخص ثالث", note: `${fa(l.ins)} ماه باقی‌مانده`, val: signedMillions(p.parts.ins), color: deltaColor(p.parts.ins) },
  ];
  if (p.gearF !== 1) rows.push({ label: "گیربکس اتوماتیک", note: "نسبت به نسخهٔ دنده‌ای", val: signedMillions(p.parts.gear), color: GREEN });
  if (l.extra) rows.push({ label: "تعویض موتور", note: "استخراج‌شده از متن آگهی", val: signedMillions(p.base * l.extra), color: RED });
  return rows;
}

export function summaryOf(l: Listing): string {
  const v = verdictOf(l.diffPct);
  const neg = l.tags.filter(isNegativeIssue);
  const pos = l.tags.filter((t) => !isNegativeIssue(t));
  const kmWord = l.pm.kmF > 1.02 ? "کم‌کارکرد" : l.pm.kmF < 0.97 ? "پرکارکرد" : "با کارکرد معمول";
  const priceWord = v.label === "قیمت منصفانه" ? "در محدودهٔ بازار" : v.label.replace("بازار", "تخمین بازار");
  const advice = l.diffPct <= CHEAP_THRESHOLD_PCT ? "ارزش بازدید سریع دارد، ولی دلیل قیمت پایین را حضوری بپرس."
    : l.diffPct >= EXPENSIVE_THRESHOLD_PCT ? "جای مذاکره دارد." : "اگر بازدید رضایت‌بخش بود قیمت منطقی است.";
  return `${l.modelName} مدل ${fa(l.year)}، ${kmWord} نسبت به سنش. بدنه «${l.body.name}»${neg.length ? ` و فروشنده به ${neg.join(" و ")} اشاره کرده` : ""}. ${pos.length ? `نکات مثبت: ${pos.join("، ")}. ` : ""}قیمت ${priceWord} است؛ ${advice}`;
}

export function verdictNote(l: Listing): string {
  if (l.diffPct <= CHEAP_THRESHOLD_PCT) return `این آگهی حدود ${num(l.est - l.price)} میلیون زیر تخمین ماست. قبل از پرداخت، دلیل قیمت پایین (سند، رنگ، تصادف) رو حضوری چک کن.`;
  if (l.diffPct >= EXPENSIVE_THRESHOLD_PCT) return `حدود ${num(l.price - l.est)} میلیون بالاتر از تخمین. با اشاره به آگهی‌های مشابه، جای مذاکره داری.`;
  return "قیمت در بازهٔ منطقی آگهی‌های مشابه است.";
}
