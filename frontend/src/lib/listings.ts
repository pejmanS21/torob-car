import { BODIES, CITIES, COLORS, IMAGES, ISSUES, MODELS, NOW_YEAR, POSTED, SNIPS } from "./catalog";
import { fa, num } from "./format";
import { priceModel } from "./pricing";
import type { CarModel, Listing } from "./types";

const LISTINGS_SEED = 20240917;
const TOKEN_SEED = 7919;
const ENGINE_SWAP_TAG = "تعویض موتور";
const ENGINE_SWAP_DISCOUNT = -0.08;

type Random = () => number;

function createRandom(seed: number): Random {
  let state = seed;
  return () => (state = (state * 1664525 + 1013904223) % 4294967296) / 4294967296;
}

function createToken(random: Random): string {
  return "g" + Math.floor(random() * 36 ** 7).toString(36).padStart(7, "0");
}

function generateListing(model: CarModel, index: number, serial: number, random: Random, tokenRandom: Random): Listing {
  const years = Object.keys(model.base).map(Number);
  const year = years[Math.floor(random() * years.length)];
  const age = Math.max(0.5, NOW_YEAR - year);
  const km = Math.round((age * 16000 * (0.4 + random() * 1.4) + random() * 15000) / 1000) * 1000;
  const body = BODIES[Math.min(5, Math.floor(Math.pow(random(), 1.6) * 6))];
  const city = CITIES[Math.floor(Math.pow(random(), 1.4) * 3)];
  const gear = model.gears[Math.floor(random() * model.gears.length)];
  const ins = Math.floor(random() * 13);
  const pm = priceModel(model, year, km, body, gear, ins);

  const tags: string[] = [];
  if (body.f <= 0.94) tags.push("رنگ‌شدگی");
  if (body.f <= 0.72) tags.push("تصادف جزئی");
  if (random() < 0.12) tags.push(ENGINE_SWAP_TAG);
  ISSUES.filter((i) => !i.neg).forEach((i) => { if (random() < 0.32 && !tags.includes(i.name)) tags.push(i.name); });

  const engineSwapped = tags.includes(ENGINE_SWAP_TAG);
  const extra = engineSwapped ? ENGINE_SWAP_DISCOUNT : 0;
  const noise = -0.13 + random() * 0.28 + extra;
  const price = Math.round((pm.est * (1 + noise)) / 5) * 5;
  const est = Math.round(pm.est * (1 + extra));
  const diffPct = ((price - est) / est) * 100;
  const score = Math.max(5, Math.min(99, Math.round(72 - diffPct * 2.4 + (body.f - 0.92) * 90 + (pm.kmF - 1) * 120)));
  const color = COLORS[Math.floor(random() * COLORS.length)];
  const desc = [
    `${model.name} مدل ${fa(year)}، ${gear}، رنگ ${color}.`,
    `کارکرد ${num(km)} کیلومتر واقعی.`,
    body === BODIES[0] ? "بدنه کاملاً بی‌رنگ و فابریک." : `وضعیت بدنه: ${body.name}.`,
    ...tags.map((t) => SNIPS[t]),
    ins ? `بیمه ${fa(ins)} ماه.` : "بیمه تمام شده.",
    "بازدید فقط حضوری، لطفاً پیام ندید تماس بگیرید.",
  ].join("\n");

  // Order of random() calls from here on matches the prototype's object literal.
  const imageOffset = serial + 1 + index;
  const district = city.districts[Math.floor(random() * city.districts.length)];
  const posted = POSTED[Math.floor(random() * POSTED.length)];
  const photos = Array.from({ length: 3 + Math.floor(random() * 3) }, (_, k) => IMAGES[(imageOffset + k * 3) % IMAGES.length]);
  const engine = engineSwapped ? "تعویض شده" : random() < 0.1 ? "نیاز به تعمیر" : "سالم";
  const gearbox = random() < 0.08 ? "نیاز به تعمیر" : "سالم و پلمپ";
  const lat = city.lat + (random() - 0.5) * 0.12;
  const lng = city.lng + (random() - 0.5) * 0.14;

  return {
    id: `l${serial}`, modelId: model.id, modelName: model.name, year, km, body, city: city.name, district, gear, ins, color,
    price, est, diffPct, score, tags, desc, pm, extra, img: IMAGES[imageOffset % IMAGES.length], posted, postedIdx: POSTED.indexOf(posted),
    photos, assess: { engine, chassis: body.f <= 0.72 ? "ضربه‌خورده" : "سالم و پلمپ", bodyA: body.name, gearbox }, lat, lng, token: createToken(tokenRandom),
  };
}

export function generateListings(): Listing[] {
  const random = createRandom(LISTINGS_SEED);
  const tokenRandom = createRandom(TOKEN_SEED);
  const listings: Listing[] = [];
  let serial = 1;
  for (const model of MODELS) {
    const count = 12 + Math.floor(random() * 4);
    for (let index = 0; index < count; index++) listings.push(generateListing(model, index, serial++, random, tokenRandom));
  }
  return listings;
}

export const LISTINGS: Listing[] = generateListings();
export const findListing = (id: string): Listing | undefined => LISTINGS.find((l) => l.id === id);
export const listingsOfModel = (modelId: string): Listing[] => LISTINGS.filter((l) => l.modelId === modelId);
