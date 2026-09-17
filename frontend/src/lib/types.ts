export type Gear = "دنده‌ای" | "اتوماتیک";
export type GearFilter = Gear | "همه";
export type SortKey = "score" | "price" | "km" | "new";

export interface CarModel { id: string; name: string; aliases: string[]; base: Record<number, number>; gears: Gear[]; }
export interface BodyCondition { name: string; f: number; }
export interface City { name: string; lat: number; lng: number; districts: string[]; }
export interface Issue { name: string; neg: boolean; }

export interface PriceParts { km: number; body: number; ins: number; gear: number; }
export interface PriceModelResult { base: number; expKm: number; kmF: number; insF: number; gearF: number; est: number; parts: PriceParts; }

export interface SellerAssessment { engine: string; chassis: string; bodyA: string; gearbox: string; }

export interface Listing {
  id: string; modelId: string; modelName: string; year: number; km: number; body: BodyCondition;
  city: string; district: string; gear: Gear; ins: number; color: string;
  price: number; est: number; diffPct: number; score: number; tags: string[]; desc: string;
  pm: PriceModelResult; extra: number; img: string; posted: string; postedIdx: number;
  photos: string[]; assess: SellerAssessment; lat: number; lng: number; token: string;
}

export interface Verdict { label: string; color: string; bg: string; icon: string; }
export interface BreakdownRow { label: string; note: string; val: string; color: string; }

export interface ParsedQuery { models: string[]; city: string | null; maxPrice: number | null; maxKm: number | null; gear: Gear | null; year: number | null; onlyBelow: boolean; }
export interface Filters { models: string[]; cities: string[]; maxPrice: number; maxKm: number; gear: GearFilter; onlyBelow: boolean; year: number | null; }

export interface ChatMessage { role: "user" | "assistant"; text: string; cardIds?: string[]; }
export interface PriceAlert { title: string; threshold: number; matches: number; }
