import type { ListingCard, Source } from "./api/types";
import { fa, formatToman, num, relativeTime } from "./format";
import { BODY_NAMES, GEARBOX_NAMES } from "./labels";
import { diffText, scoreColor, verdictStyle } from "./pricing";
import type { VerdictStyle } from "./types";

export interface CardView {
  id: string; href: string; img: string; title: string; posted: string; meta: string; priceText: string;
  verdict: VerdictStyle; diffText: string; score: number; scoreFa: string; scoreColor: string; body: string; insFa: string;
  isExact: boolean; nearMissLabels: string[]; source: Source;
}

export const PRICE_UNKNOWN = "توافقی";
const PLACEHOLDER_IMAGE = "/icons/icon-192.png";

export const metaOf = (l: ListingCard): string =>
  [
    l.year === null ? "" : `مدل ${fa(l.year)}`,
    l.km === null ? "" : `${num(l.km)} کیلومتر`,
    l.district ? `${l.city}، ${l.district}` : l.city,
    l.gearbox ? GEARBOX_NAMES[l.gearbox] : "",
  ].filter(Boolean).join(" · ");

/** `dataAsOf` is the snapshot time from /facets; without it, "posted" is relative to now. */
export const cardOf = (l: ListingCard, dataAsOf: string | null = null): CardView => ({
  id: l.id, href: `/listing/${l.id}`, img: l.thumbnail_url ?? PLACEHOLDER_IMAGE, title: l.trim ?? l.title,
  posted: relativeTime(l.posted_at, dataAsOf ?? new Date()), meta: metaOf(l),
  priceText: l.price === null ? PRICE_UNKNOWN : formatToman(l.price), verdict: verdictStyle(l.verdict), diffText: diffText(l.diff_pct),
  score: l.deal_score ?? 0, scoreFa: l.deal_score === null ? "—" : fa(l.deal_score), scoreColor: scoreColor(l.deal_score ?? 0),
  body: l.body_condition ? BODY_NAMES[l.body_condition] : "—", insFa: l.insurance_months === null ? "—" : fa(l.insurance_months),
  isExact: l.is_exact, nearMissLabels: l.near_miss_labels, source: l.source,
});
