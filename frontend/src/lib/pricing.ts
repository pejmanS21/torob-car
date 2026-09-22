import type { EstimateBasis, EstimateRequest, EstimateResponse, ListingDetail, Verdict } from "./api/types";
import { fa, formatToman, num } from "./format";
import { BASIS_NAMES, BODY_NAMES } from "./labels";
import { AMBER, GREEN, INK, NEUTRAL, RED } from "./theme";
import type { BreakdownRow, VerdictStyle } from "./types";

const VERDICTS: Record<Verdict, VerdictStyle> = {
  cheap: { label: "ارزان‌تر از بازار", color: GREEN, bg: "#ecfdf3", icon: "M16 17h6v-6M22 17l-8.5-8.5-5 5L2 7" },
  expensive: { label: "بالاتر از بازار", color: RED, bg: "#fdecec", icon: "M16 7h6v6M22 7l-8.5 8.5-5-5L2 17" },
  fair: { label: "قیمت منصفانه", color: AMBER, bg: "#fffbeb", icon: "M20 6 9 17l-5-5" },
  unknown: { label: "بدون تخمین", color: NEUTRAL, bg: "#f1f3f6", icon: "M12 8v4M12 16h.01" },
};
const NO_ESTIMATE_TEXT = "تخمینی برای این آگهی نداریم";
const HIGH_KM_FACTOR = 1.02;
const LOW_KM_FACTOR = 0.97;

export const verdictStyle = (verdict: Verdict): VerdictStyle => VERDICTS[verdict];

export function diffText(d: number | null): string {
  if (d === null) return NO_ESTIMATE_TEXT;
  if (d > 0.5) return `${fa(Math.abs(d).toFixed(0))}٪ بالاتر از تخمین`;
  if (d < -0.5) return `${fa(Math.abs(d).toFixed(0))}٪ ارزان‌تر از تخمین`;
  return "برابر تخمین بازار";
}

export function scoreColor(score: number): string {
  if (score >= 70) return GREEN;
  return score >= 45 ? AMBER : RED;
}

export const signedToman = (d: number): string => (d >= 0 ? "+" : "−") + formatToman(Math.abs(d));
export function deltaColor(d: number): string {
  if (Math.abs(d) < 1) return NEUTRAL;
  return d > 0 ? GREEN : RED;
}

export const basisText = (basis: EstimateBasis, sampleSize: number): string =>
  basis === "none" ? BASIS_NAMES.none : `میانهٔ ${fa(sampleSize)} آگهی ${BASIS_NAMES[basis]}`;

/** Base, km and insurance rows from the API breakdown — nothing is computed client-side. */
export function breakdownRows(detail: ListingDetail): BreakdownRow[] {
  const p = detail.price_breakdown;
  if (p.base === null || p.km_adjustment === null || p.insurance_adjustment === null) return [];
  return [
    { label: "قیمت پایهٔ تیپ و سال", note: basisText(p.est_basis, p.est_sample_size), val: formatToman(p.base), color: INK },
    { label: "کارکرد", note: detail.km === null ? "کارکرد نامشخص" : `${num(detail.km)} کیلومتر`, val: signedToman(p.km_adjustment), color: deltaColor(p.km_adjustment) },
    { label: "بیمهٔ شخص ثالث", note: detail.insurance_months === null ? "نامشخص" : `${fa(detail.insurance_months)} ماه باقی‌مانده`, val: signedToman(p.insurance_adjustment), color: deltaColor(p.insurance_adjustment) },
  ];
}

const kmWord = (detail: ListingDetail): string => {
  const p = detail.price_breakdown;
  if (p.base === null || p.km_adjustment === null) return "";
  const factor = 1 + p.km_adjustment / p.base;
  if (factor > HIGH_KM_FACTOR) return "کم‌کارکرد نسبت به سنش";
  return factor < LOW_KM_FACTOR ? "پرکارکرد نسبت به سنش" : "با کارکرد معمول";
};

const SUMMARY_PRICES: Record<Verdict, string> = {
  cheap: " قیمت ارزان‌تر از تخمین بازار است؛ ارزش بازدید سریع دارد، ولی دلیل قیمت پایین را حضوری بپرس.",
  expensive: " قیمت بالاتر از تخمین بازار است؛ جای مذاکره دارد.",
  fair: " قیمت در محدودهٔ بازار است؛ اگر بازدید رضایت‌بخش بود منطقی است.",
  unknown: " برای این آگهی تخمین قیمت نداریم؛ با آگهی‌های مشابه مقایسه کن.",
};

/** One-paragraph summary from real fields only: title, km, body, verdict and advice. */
export function summaryOf(detail: ListingDetail): string {
  const parts = [detail.trim ?? detail.title, detail.year ? `مدل ${fa(detail.year)}` : "", kmWord(detail)].filter(Boolean).join("، ");
  const body = detail.body_condition ? ` بدنه «${BODY_NAMES[detail.body_condition]}».` : "";
  const price = SUMMARY_PRICES[detail.verdict];
  return `${parts}.${body}${price}`;
}

export function verdictNote(detail: ListingDetail): string {
  if (detail.est_price === null || detail.price === null) return "برای این آگهی آگهی‌های مشابه کافی برای تخمین نداریم.";
  if (detail.verdict === "cheap") return `این آگهی حدود ${formatToman(detail.est_price - detail.price)} زیر تخمین ماست. قبل از پرداخت، دلیل قیمت پایین (سند، رنگ، تصادف) رو حضوری چک کن.`;
  if (detail.verdict === "expensive") return `حدود ${formatToman(detail.price - detail.est_price)} بالاتر از تخمین. با اشاره به آگهی‌های مشابه، جای مذاکره داری.`;
  return "قیمت در بازهٔ منطقی آگهی‌های مشابه است.";
}

/** Rows for the /estimates result: the same three rows, from the API breakdown. */
export function estimateBreakdownRows(result: EstimateResponse, request: EstimateRequest | null): BreakdownRow[] {
  const b = result.breakdown;
  return [
    { label: "قیمت پایهٔ تیپ و سال", note: basisText(result.est_basis, result.est_sample_size), val: formatToman(b.base), color: INK },
    { label: "کارکرد", note: request?.km == null ? "کارکرد نامشخص" : `${num(request.km)} کیلومتر`, val: signedToman(b.km_adjustment), color: deltaColor(b.km_adjustment) },
    { label: "بیمهٔ شخص ثالث", note: request?.insurance_months == null ? "نامشخص" : `${fa(request.insurance_months)} ماه`, val: signedToman(b.insurance_adjustment), color: deltaColor(b.insurance_adjustment) },
  ];
}
