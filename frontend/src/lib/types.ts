import type { ListingCard, SearchParams } from "./api/types";

/** How a verdict is drawn (label, colours, badge icon path). */
export interface VerdictStyle { label: string; color: string; bg: string; icon: string; }
export interface BreakdownRow { label: string; note: string; val: string; color: string; }

export interface ChatMessage { role: "user" | "assistant"; text: string; listings: ListingCard[]; status?: "streaming" | "failed"; }
/** `id` is present once the server has stored the alert; an optimistic one has none yet. */
export interface PriceAlert { id?: string; title: string; params: SearchParams; threshold: number; }
