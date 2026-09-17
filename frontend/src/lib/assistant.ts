import { en, fa, num } from "./format";
import { CHEAP_THRESHOLD_PCT, diffText } from "./pricing";
import { chipsOf, hasCriteria, matchesParsed, parseQuery, sortListings } from "./search";
import type { Listing } from "./types";

export interface AssistantReply { text: string; cardIds?: string[]; }

const SUGGESTED_CARDS = 3;
const MIN_CARS_TO_COMPARE = 2;
const COMPARE_QUESTION = /کدوم|کدام|بهتر|به‌?صرفه|به صرفه/;
const BUDGET_QUESTION = /بودجه|چقدر|قیمت/;

function bestOfCompared(compared: Listing[]): AssistantReply {
  const best = sortListings(compared, "score")[0];
  return { text: `بین ${fa(compared.length)} ماشینی که توی مقایسه داری، ${best.modelName} مدل ${fa(best.year)} (${best.city}) بهترین ارزش خرید رو داره: ${diffText(best.diffPct)}، ${num(best.km)} کیلومتر و بدنه «${best.body.name}».`, cardIds: [best.id] };
}

export function scriptedReply(text: string, listings: Listing[], compareIds: string[]): AssistantReply {
  const parsed = parseQuery(text);
  const normalized = en(text);
  const compared = listings.filter((l) => compareIds.includes(l.id));
  if (COMPARE_QUESTION.test(normalized) && compared.length >= MIN_CARS_TO_COMPARE) return bestOfCompared(compared);
  if (!hasCriteria(parsed)) {
    return BUDGET_QUESTION.test(normalized)
      ? { text: "بودجه‌ت رو بگو (مثلاً «زیر ۸۰۰ میلیون») و اگه شهر یا مدل خاصی مدنظرته اضافه کن؛ بهترین گزینه‌ها رو نشونت می‌دم." }
      : { text: "من روی آگهی‌های پژو ۲۰۶، دنا پلاس، تارا و جک J4 در تهران، کرج و اصفهان کار می‌کنم. یه چیزی مثل «دنا اتومات زیر یک میلیارد کرج» بگو." };
  }
  const matches = listings.filter((l) => matchesParsed(l, parsed));
  if (!matches.length) return { text: "با این شرایط آگهی فعالی نداریم. سقف قیمت رو بالاتر ببر یا شهر رو حذف کن." };
  const below = matches.filter((l) => l.diffPct <= CHEAP_THRESHOLD_PCT).length;
  const median = sortListings(matches, "price")[Math.floor(matches.length / 2)].price;
  return {
    text: `${fa(matches.length)} آگهی پیدا کردم (${chipsOf(parsed).join("، ")}). میانهٔ قیمت‌شون ${num(median)} میلیونه و ${fa(below)} تاش زیر قیمت بازاره. سه‌تای اول از نظر ارزش خرید:`,
    cardIds: sortListings(matches, "score").slice(0, SUGGESTED_CARDS).map((l) => l.id),
  };
}
