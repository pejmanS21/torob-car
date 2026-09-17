import { fa, num } from "./format";
import { diffText, scoreColor, verdictOf } from "./pricing";
import type { Listing, Verdict } from "./types";

export interface CardView { id: string; href: string; img: string; title: string; posted: string; meta: string; priceFa: string; verdict: Verdict; diffText: string; score: number; scoreFa: string; scoreColor: string; body: string; insFa: string; }

export const cardOf = (l: Listing): CardView => ({
  id: l.id, href: `/listing/${l.id}`, img: l.img, title: `${l.modelName} مدل ${fa(l.year)}`, posted: l.posted,
  meta: `${num(l.km)} کیلومتر · ${l.city}، ${l.district} · ${l.gear}`, priceFa: num(l.price), verdict: verdictOf(l.diffPct),
  diffText: diffText(l.diffPct), score: l.score, scoreFa: fa(l.score), scoreColor: scoreColor(l.score), body: l.body.name, insFa: fa(l.ins),
});
