import type { ListingCard } from "./api/types";
import { fa, formatToman, num } from "./format";
import { BODY_NAMES, GEARBOX_NAMES } from "./labels";
import { diffText, scoreColor, verdictStyle } from "./pricing";
import { INK } from "./theme";

export interface CompareCell { text: string; color: string; best: boolean; }
export interface CompareRow { label: string; cells: CompareCell[]; }

type Better = (a: number, b: number) => boolean;
const lower: Better = (a, b) => a < b;
const higher: Better = (a, b) => a > b;
const DASH = "—";

/** Index of the best known value; unknown (null) values never win. */
function indexOfBest(values: (number | null)[], better: Better): number {
  return values.reduce<number>((best, v, i) => (v !== null && (best === -1 || better(v, values[best] as number)) ? i : best), -1);
}

function numericRow(
  label: string, cards: ListingCard[], get: (l: ListingCard) => number | null, text: (l: ListingCard) => string, better: Better,
  color: (l: ListingCard) => string = () => INK,
): CompareRow {
  const values = cards.map(get);
  const best = cards.length > 1 ? indexOfBest(values, better) : -1;
  return { label, cells: cards.map((l, i) => ({ text: text(l), color: color(l), best: i === best })) };
}

const textRow = (label: string, cards: ListingCard[], text: (l: ListingCard) => string): CompareRow =>
  ({ label, cells: cards.map((l) => ({ text: text(l), color: INK, best: false })) });

export function compareRows(cards: ListingCard[]): CompareRow[] {
  if (!cards.length) return [];
  return [
    numericRow("قیمت", cards, (l) => l.price, (l) => (l.price === null ? "توافقی" : formatToman(l.price)), lower),
    numericRow("نسبت به بازار", cards, (l) => l.diff_pct, (l) => diffText(l.diff_pct), lower, (l) => verdictStyle(l.verdict).color),
    numericRow("ارزش خرید", cards, (l) => l.deal_score, (l) => (l.deal_score === null ? DASH : `${fa(l.deal_score)}/۱۰۰`), higher, (l) => (l.deal_score === null ? INK : scoreColor(l.deal_score))),
    numericRow("سال ساخت", cards, (l) => l.year, (l) => (l.year === null ? DASH : fa(l.year)), higher),
    numericRow("کارکرد", cards, (l) => l.km, (l) => (l.km === null ? DASH : `${num(l.km)} کیلومتر`), lower),
    textRow("گیربکس", cards, (l) => (l.gearbox ? GEARBOX_NAMES[l.gearbox] : DASH)),
    textRow("وضعیت بدنه", cards, (l) => (l.body_condition ? BODY_NAMES[l.body_condition] : DASH)),
    numericRow("بیمه", cards, (l) => l.insurance_months, (l) => (l.insurance_months === null ? DASH : `${fa(l.insurance_months)} ماه`), higher),
    textRow("شهر", cards, (l) => (l.district ? `${l.city}، ${l.district}` : l.city)),
  ];
}
