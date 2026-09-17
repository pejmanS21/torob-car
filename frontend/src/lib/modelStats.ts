import { ISSUES, findModel } from "./catalog";
import { fa, num } from "./format";
import { sortListings } from "./search";
import type { CarModel, Listing } from "./types";

const BUCKET_COUNT = 8;
const MAX_BAR_HEIGHT_PCT = 90;
const MIN_BAR_HEIGHT_PCT = 4;
const MAX_ISSUES = 6;
export const ALERT_FRACTION_OF_MEDIAN = 0.9;
const ALERT_ROUNDING = 10;
const RANGE_AXIS_MIN = 400;
const RANGE_AXIS_MAX = 1350;

export interface HistogramBucket { countFa: string; heightPct: number; isMedian: boolean; tip: string; }
export interface IssueBar { name: string; widthPct: number; pctText: string; neg: boolean; }
export interface ModelStats { model: CarModel; listings: Listing[]; countFa: string; yearRange: string; median: number; min: number; max: number; alertThreshold: number; buckets: HistogramBucket[]; issues: IssueBar[]; }
export interface ModelRange { id: string; name: string; countFa: string; minFa: string; maxFa: string; barStartPct: number; barWidthPct: number; }

function requireModel(modelId: string): CarModel {
  const model = findModel(modelId);
  if (!model) throw new RangeError(`Unknown model: ${modelId}`);
  return model;
}

function priceBuckets(prices: number[], median: number): HistogramBucket[] {
  const min = prices[0];
  const width = (prices[prices.length - 1] - min) / BUCKET_COUNT || 1;
  const bucketOf = (price: number) => Math.min(BUCKET_COUNT - 1, Math.floor((price - min) / width));
  const counts = Array<number>(BUCKET_COUNT).fill(0);
  prices.forEach((p) => counts[bucketOf(p)]++);
  const tallest = Math.max(...counts);
  return counts.map((count, i) => ({
    countFa: count ? fa(count) : "", heightPct: Math.max(MIN_BAR_HEIGHT_PCT, (count / tallest) * MAX_BAR_HEIGHT_PCT),
    isMedian: i === bucketOf(median), tip: `${num(min + i * width)} تا ${num(min + (i + 1) * width)} میلیون`,
  }));
}

function issueBars(listings: Listing[]): IssueBar[] {
  return ISSUES.map((issue) => ({ issue, n: listings.filter((l) => l.tags.includes(issue.name)).length }))
    .filter((x) => x.n > 0).sort((a, b) => b.n - a.n).slice(0, MAX_ISSUES)
    .map(({ issue, n }) => { const pct = Math.round((n / listings.length) * 100); return { name: issue.name, widthPct: pct, pctText: `${fa(pct)}٪ آگهی‌ها`, neg: issue.neg }; });
}

export function modelStats(modelId: string, all: Listing[]): ModelStats {
  const model = requireModel(modelId);
  const listings = sortListings(all.filter((l) => l.modelId === modelId), "score");
  const prices = listings.map((l) => l.price).sort((a, b) => a - b);
  const years = listings.map((l) => l.year);
  const median = prices[Math.floor(prices.length / 2)];
  return {
    model, listings, countFa: fa(listings.length), yearRange: `${fa(Math.min(...years))} تا ${fa(Math.max(...years))}`,
    median, min: prices[0], max: prices[prices.length - 1],
    alertThreshold: Math.round((median * ALERT_FRACTION_OF_MEDIAN) / ALERT_ROUNDING) * ALERT_ROUNDING,
    buckets: priceBuckets(prices, median), issues: issueBars(listings),
  };
}

export function modelRange(modelId: string, all: Listing[]): ModelRange {
  const model = requireModel(modelId);
  const prices = all.filter((l) => l.modelId === modelId).map((l) => l.price);
  const min = Math.min(...prices), max = Math.max(...prices);
  const span = RANGE_AXIS_MAX - RANGE_AXIS_MIN;
  const clampPct = (v: number) => Math.max(0, Math.min(100, v));
  const start = clampPct(((min - RANGE_AXIS_MIN) / span) * 100);
  return { id: model.id, name: model.name, countFa: fa(prices.length), minFa: num(min), maxFa: num(max), barStartPct: start, barWidthPct: Math.min(100 - start, ((max - min) / span) * 100) };
}
