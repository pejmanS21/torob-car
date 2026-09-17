import { expect, test } from "bun:test";
import { scriptedReply } from "./assistant";
import { LISTINGS } from "./listings";

test("no criteria → explains coverage", () => {
  const r = scriptedReply("سلام", LISTINGS, []);
  expect(r.text).toContain("پژو ۲۰۶، دنا پلاس، تارا و جک J4");
  expect(r.cardIds).toBeUndefined();
});
test("budget question without criteria → asks for budget", () => {
  expect(scriptedReply("قیمت چقدره؟", LISTINGS, []).text).toContain("بودجه‌ت رو بگو");
});
test("impossible criteria → no-match message", () => {
  expect(scriptedReply("تارا زیر ۱۰۰ میلیون", LISTINGS, []).text).toContain("آگهی فعالی نداریم");
});
test("matching criteria → count, median and top-3 cards by score", () => {
  const r = scriptedReply("دنا پلاس", LISTINGS, []);
  const dena = LISTINGS.filter((l) => l.modelId === "dena").sort((a, b) => b.score - a.score);
  expect(r.text).toContain("آگهی پیدا کردم");
  expect(r.cardIds).toEqual(dena.slice(0, 3).map((l) => l.id));
});
test("compare question with two compared cars → picks the best score", () => {
  const [a, b] = LISTINGS;
  const best = a.score >= b.score ? a : b;
  const r = scriptedReply("کدوم به‌صرفه‌تره؟", LISTINGS, [a.id, b.id]);
  expect(r.cardIds).toEqual([best.id]);
});
