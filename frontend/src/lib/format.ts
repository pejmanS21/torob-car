const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";

export const fa = (value: string | number): string =>
  String(value).replace(/\d/g, (d) => FA_DIGITS[Number(d)]);

export const en = (value: string | number): string =>
  String(value)
    .replace(/[۰-۹]/g, (d) => String(FA_DIGITS.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(AR_DIGITS.indexOf(d)));

export const num = (n: number): string => fa(Math.round(n).toLocaleString("en-US"));
