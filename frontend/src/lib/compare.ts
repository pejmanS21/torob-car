import { fa, num } from "./format";
import { diffText, scoreColor, verdictOf } from "./pricing";
import type { Listing } from "./types";

export interface CompareCell { text: string; color: string; best: boolean; }
export interface CompareRow { label: string; cells: CompareCell[]; }

const INK = "#172033";
type Better = (a: number, b: number) => boolean;
const lower: Better = (a, b) => a < b;
const higher: Better = (a, b) => a > b;

function indexOfBest(values: number[], better: Better): number {
  return values.reduce((best, v, i) => (best === -1 || better(v, values[best]) ? i : best), -1);
}

function numericRow(label: string, cars: Listing[], get: (l: Listing) => number, text: (l: Listing) => string, better: Better, color: (v: number) => string = () => INK): CompareRow {
  const values = cars.map(get);
  const best = cars.length > 1 ? indexOfBest(values, better) : -1;
  return { label, cells: cars.map((l, i) => ({ text: text(l), color: color(values[i]), best: i === best })) };
}

const textRow = (label: string, cars: Listing[], text: (l: Listing) => string): CompareRow =>
  ({ label, cells: cars.map((l) => ({ text: text(l), color: INK, best: false })) });

export function compareRows(cars: Listing[]): CompareRow[] {
  if (!cars.length) return [];
  return [
    numericRow("قیمت", cars, (l) => l.price, (l) => `${num(l.price)} میلیون`, lower),
    numericRow("نسبت به بازار", cars, (l) => l.diffPct, (l) => diffText(l.diffPct), lower, (v) => verdictOf(v).color),
    numericRow("ارزش خرید", cars, (l) => l.score, (l) => `${fa(l.score)}/۱۰۰`, higher, scoreColor),
    numericRow("سال ساخت", cars, (l) => l.year, (l) => fa(l.year), higher),
    numericRow("کارکرد", cars, (l) => l.km, (l) => `${num(l.km)} کیلومتر`, lower),
    textRow("گیربکس", cars, (l) => l.gear),
    numericRow("وضعیت بدنه", cars, (l) => l.body.f, (l) => l.body.name, higher),
    numericRow("بیمه", cars, (l) => l.ins, (l) => `${fa(l.ins)} ماه`, higher),
    textRow("شهر", cars, (l) => l.city),
    textRow("نکات آگهی", cars, (l) => l.tags.join("، ") || "—"),
  ];
}
