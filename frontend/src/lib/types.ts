import type { ListingCard, SearchParams } from "./api/types";

/** How a verdict is drawn (label, colours, badge icon path). */
export interface VerdictStyle { label: string; color: string; bg: string; icon: string; }
export interface BreakdownRow { label: string; note: string; val: string; color: string; }

export interface ChatMessage { role: "user" | "assistant"; text: string; listings: ListingCard[]; }
export interface PriceAlert { title: string; params: SearchParams; threshold: number; }
