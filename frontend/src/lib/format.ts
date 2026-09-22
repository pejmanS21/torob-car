const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";
const TOMAN_PER_MILLION = 1_000_000;
const MILLIONS_PER_BILLION = 1_000;
const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;
const WEEK_MS = 7 * DAY_MS;
const MONTH_MS = 30 * DAY_MS;

export const fa = (value: string | number): string =>
  String(value).replace(/\d/g, (d) => FA_DIGITS[Number(d)]);

export const en = (value: string | number): string =>
  String(value)
    .replace(/[۰-۹]/g, (d) => String(FA_DIGITS.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(AR_DIGITS.indexOf(d)));

export const num = (n: number): string => fa(Math.round(n).toLocaleString("en-US"));

/** Toman → «۹۷۰ میلیون» / «۱.۲ میلیارد», the same wording as the backend's labels. */
export function formatToman(amount: number): string {
  const millions = Math.round(amount / TOMAN_PER_MILLION);
  if (millions >= MILLIONS_PER_BILLION) {
    const billions = Number((millions / MILLIONS_PER_BILLION).toFixed(2)).toString();
    return `${fa(billions)} میلیارد`;
  }
  return `${fa(millions)} میلیون`;
}

/** «۳ روز پیش»-style age of `postedAt` relative to `reference` (usually the data snapshot). */
export function relativeTime(postedAt: string | null, reference: string | Date): string {
  if (!postedAt) return "";
  const elapsed = new Date(reference).getTime() - new Date(postedAt).getTime();
  if (Number.isNaN(elapsed) || elapsed < HOUR_MS) return "دقایقی پیش";
  if (elapsed < DAY_MS) return `${fa(Math.floor(elapsed / HOUR_MS))} ساعت پیش`;
  if (elapsed < 2 * DAY_MS) return "دیروز";
  if (elapsed < WEEK_MS) return `${fa(Math.floor(elapsed / DAY_MS))} روز پیش`;
  if (elapsed < MONTH_MS) return `${fa(Math.floor(elapsed / WEEK_MS))} هفته پیش`;
  return `${fa(Math.floor(elapsed / MONTH_MS))} ماه پیش`;
}
