import { CITIES, MODELS, findModel } from "./catalog";
import { en, fa, num } from "./format";
import { CHEAP_THRESHOLD_PCT } from "./pricing";
import type { Filters, Listing, ParsedQuery, SortKey } from "./types";

export const DEFAULT_MAX_PRICE = 1400;
export const DEFAULT_MAX_KM = 250;
const LOW_MILEAGE_KM = 90;
const BILLION_TO_MILLION = 1000;
const IMPLICIT_BILLION_BELOW = 5; // "زیر ۱.۲" means billions

export const DEFAULT_FILTERS: Filters = { models: [], cities: [], maxPrice: DEFAULT_MAX_PRICE, maxKm: DEFAULT_MAX_KM, gear: "همه", onlyBelow: false, year: null };

const normalize = (q: string): string => en(q).toLowerCase().replace(/ي/g, "ی").replace(/ك/g, "ک");

function parseMaxPrice(text: string): number | null {
  const match = text.match(/(?:زیر|کمتر از|تا|حداکثر)\s*(\d+(?:\.\d+)?)\s*(میلیارد|میلیون)?/);
  if (match) {
    const value = parseFloat(match[1]);
    const inBillions = match[2] === "میلیارد" || value < IMPLICIT_BILLION_BELOW;
    return Math.round(value * (inBillions ? BILLION_TO_MILLION : 1));
  }
  return /یک میلیارد/.test(text) ? BILLION_TO_MILLION : null;
}

function parseMaxKm(text: string): number | null {
  const explicit = text.match(/(?:کارکرد\s*)?(?:زیر|کمتر از)\s*(\d+)\s*(?:هزار)?\s*(?:کیلومتر|تا کارکرد|کارکرد)/);
  if (explicit) return parseInt(explicit[1], 10);
  return /کم[\s‌]?کارکرد|کم کار/.test(text) ? LOW_MILEAGE_KM : null;
}

export function parseQuery(q: string): ParsedQuery {
  const text = normalize(q);
  const year = text.match(/(?:مدل|سال)\s*(1[34]\d\d)/);
  return {
    models: MODELS.filter((m) => [m.name, ...m.aliases].some((a) => text.includes(normalize(a)))).map((m) => m.id),
    city: CITIES.find((c) => text.includes(c.name))?.name ?? null,
    maxPrice: parseMaxPrice(text),
    maxKm: parseMaxKm(text),
    gear: /اتومات/.test(text) ? "اتوماتیک" : /دنده/.test(text) ? "دنده‌ای" : null,
    year: year ? parseInt(year[1], 10) : null,
    onlyBelow: /ارزان|زیر قیمت|به‌?صرفه|به صرفه/.test(text),
  };
}

export const hasCriteria = (p: ParsedQuery): boolean => p.models.length > 0 || p.maxPrice !== null || p.city !== null || p.maxKm !== null;

export function chipsOf(p: ParsedQuery): string[] {
  const chips = p.models.map((id) => findModel(id)!.name);
  if (p.year) chips.push(`مدل ${fa(p.year)}`);
  if (p.maxPrice) chips.push(`زیر ${num(p.maxPrice)} میلیون`);
  if (p.maxKm) chips.push(`کارکرد زیر ${fa(p.maxKm)} هزار`);
  if (p.city) chips.push(p.city);
  if (p.gear) chips.push(p.gear);
  if (p.onlyBelow) chips.push("فقط ارزان‌تر از بازار");
  return chips;
}

export const filtersFromQuery = (p: ParsedQuery): Filters => ({
  models: p.models, cities: p.city ? [p.city] : [], maxPrice: p.maxPrice ?? DEFAULT_MAX_PRICE, maxKm: p.maxKm ?? DEFAULT_MAX_KM,
  gear: p.gear ?? "همه", onlyBelow: p.onlyBelow, year: p.year,
});

export const matchesParsed = (l: Listing, p: ParsedQuery): boolean =>
  (!p.models.length || p.models.includes(l.modelId)) && (!p.city || l.city === p.city) && (!p.maxPrice || l.price <= p.maxPrice) &&
  (!p.maxKm || l.km <= p.maxKm * 1000) && (!p.gear || l.gear === p.gear) && (!p.year || l.year === p.year);

export const filterListings = (list: Listing[], f: Filters): Listing[] =>
  list.filter((l) =>
    (!f.models.length || f.models.includes(l.modelId)) && (!f.cities.length || f.cities.includes(l.city)) &&
    l.price <= f.maxPrice && l.km <= f.maxKm * 1000 && (f.gear === "همه" || l.gear === f.gear) &&
    (!f.onlyBelow || l.diffPct <= CHEAP_THRESHOLD_PCT) && (!f.year || l.year === f.year));

const COMPARATORS: Record<SortKey, (a: Listing, b: Listing) => number> = {
  price: (a, b) => a.price - b.price, km: (a, b) => a.km - b.km, new: (a, b) => a.postedIdx - b.postedIdx, score: (a, b) => b.score - a.score,
};
export const sortListings = (list: Listing[], sort: SortKey): Listing[] => [...list].sort(COMPARATORS[sort]);

export const activeFilterCount = (f: Filters): number =>
  f.models.length + f.cities.length + Number(f.maxPrice < DEFAULT_MAX_PRICE) + Number(f.maxKm < DEFAULT_MAX_KM) + Number(f.gear !== "همه") + Number(f.onlyBelow);
