import { BODIES, GREEN, MODELS, findModel } from "./catalog";
import { en, fa, num } from "./format";
import { deltaColor, diffText, priceModel, signedMillions, verdictOf } from "./pricing";
import { sortListings } from "./search";
import type { BreakdownRow, CarModel, Gear, Listing, Verdict } from "./types";

export interface EstimateInput { modelId: string; year: number; kmThousands: number; bodyIndex: number; gear: Gear; asking: string; }
export interface EstimateResult { model: CarModel; year: number; years: number[]; gear: Gear; title: string; est: number; low: number; high: number; similar: Listing[]; similarCount: number; breakdown: BreakdownRow[]; asking: { value: number; verdict: Verdict; text: string } | null; }

const NEUTRAL_INSURANCE_MONTHS = 6;
const RANGE_MARGIN = 0.05;
const SIMILAR_YEAR_WINDOW = 1;
const MAX_SIMILAR = 4;
const INK = "#172033";

export function estimate(input: EstimateInput, all: Listing[]): EstimateResult {
  const model = findModel(input.modelId) ?? MODELS[0];
  const years = Object.keys(model.base).map(Number).sort((a, b) => b - a);
  const year = model.base[input.year] !== undefined ? input.year : years[0];
  const body = BODIES[input.bodyIndex] ?? BODIES[0];
  const gear = model.gears.includes(input.gear) ? input.gear : model.gears[0];
  const km = input.kmThousands * 1000;
  const pm = priceModel(model, year, km, body, gear, NEUTRAL_INSURANCE_MONTHS);
  const est = Math.round(pm.est);
  const similarAll = all.filter((l) => l.modelId === model.id && Math.abs(l.year - year) <= SIMILAR_YEAR_WINDOW);
  const askingValue = parseFloat(en(input.asking));
  const hasAsking = !Number.isNaN(askingValue) && askingValue > 0;
  const askingDiff = hasAsking ? ((askingValue - est) / est) * 100 : 0;
  const breakdown: BreakdownRow[] = [
    { label: "قیمت پایهٔ مدل و سال", note: `میانهٔ آگهی‌های ${model.name} مدل ${fa(year)}`, val: `${num(pm.base)} میلیون`, color: INK },
    { label: "کارکرد", note: `${num(km)} در برابر انتظار ${num(pm.expKm)} کیلومتر`, val: signedMillions(pm.parts.km), color: deltaColor(pm.parts.km) },
    { label: "وضعیت بدنه", note: body.name, val: signedMillions(pm.parts.body), color: deltaColor(pm.parts.body) },
    ...(pm.gearF !== 1 ? [{ label: "گیربکس اتوماتیک", note: "نسبت به نسخهٔ دنده‌ای", val: signedMillions(pm.parts.gear), color: GREEN }] : []),
  ];
  return {
    model, year, years, gear, title: `${model.name} مدل ${fa(year)}`, est, low: est * (1 - RANGE_MARGIN), high: est * (1 + RANGE_MARGIN),
    similar: sortListings(similarAll, "score").slice(0, MAX_SIMILAR), similarCount: similarAll.length, breakdown,
    asking: hasAsking ? { value: askingValue, verdict: verdictOf(askingDiff), text: `قیمت ${num(askingValue)} میلیون، ${diffText(askingDiff)}` } : null,
  };
}
