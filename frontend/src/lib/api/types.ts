// Hand-written mirrors of the backend Pydantic schemas (backend/schemas/*.py).
// Money is integer toman; years are Jalali; dates are ISO strings.

export type Category = "light" | "heavy" | "motorcycle" | "rental" | "classic";
export type Source = "divar" | "bama" | "karnameh" | "hamrah_mechanic";
export type PriceType = "lumpsum" | "negotiable" | "installment";
export type DocumentStatus =
  | "title_in_name" | "ready_to_transfer" | "white_title" | "no_title" | "mortgaged" // Divar vocabulary
  | "single_page" | "two_page" | "multi_page"; // Hamrah Mechanic vocabulary
export type Gearbox = "manual" | "automatic";
export type Fuel = "petrol" | "dual_factory" | "dual_aftermarket" | "hybrid" | "plugin_hybrid" | "electric" | "diesel";
export type BodyCondition =
  | "intact" | "no_paint" | "minor_scratches" | "partial_paint" | "heavy_paint" | "dropped" | "accident" | "original" | "restored";
export type EstimateBasis = "trim_year" | "trim_near_year" | "model_year" | "model_near_year" | "none";
export type SortKey = "relevance" | "deal" | "price" | "km" | "newest";
export type Verdict = "cheap" | "fair" | "expensive" | "unknown";
export type ParsedBy = "llm" | "rules";
export type ChatRole = "user" | "assistant";

export interface ListingCard {
  id: string; token: string; title: string; category: Category; source: Source;
  brand: string | null; model: string | null; trim: string | null;
  year: number | null; km: number | null; price: number | null;
  city: string; district: string | null; lat: number | null; lng: number | null;
  gearbox: Gearbox | null; fuel: Fuel | null; body_condition: BodyCondition | null; insurance_months: number | null;
  thumbnail_url: string | null; posted_at: string | null;
  est_price: number | null; diff_pct: number | null; deal_score: number | null; verdict: Verdict;
  match_score: number | null; is_exact: boolean; near_miss_labels: string[];
}

export interface PriceBreakdown {
  base: number | null; km_adjustment: number | null; insurance_adjustment: number | null;
  est_basis: EstimateBasis; est_sample_size: number;
}

export interface ListingDetail extends ListingCard {
  url: string; description: string; image_urls: string[]; color: string | null; is_dealer: boolean;
  attributes: Record<string, string>; price_breakdown: PriceBreakdown;
  price_type: PriceType | null; document_status: DocumentStatus | null;
}

export interface VehicleMention { brand: string | null; model: string | null; trim: string | null; }

export interface SearchIntent {
  category: Category | null; vehicles: VehicleMention[]; year_min: number | null; year_max: number | null;
  price_min: number | null; price_max: number | null; km_min: number | null; km_max: number | null; cities: string[];
  gearbox: Gearbox | null; fuel: Fuel | null; colors: string[]; only_below_market: boolean; text: string | null; sort: SortKey;
}
export interface IntentRead extends SearchIntent { chips: string[]; }

export interface SearchResponse {
  intent: IntentRead; parsed_by: ParsedBy; total: number; exact_count: number; page: number; page_size: number; items: ListingCard[];
}

/** Query parameters of GET /search (backend `SearchParams`). Arrays repeat the key. */
export interface SearchParams {
  q?: string; category?: Category; models?: string[]; cities?: string[]; year_min?: number; year_max?: number;
  price_min?: number; price_max?: number; km_min?: number; km_max?: number; gearbox?: Gearbox; only_below?: boolean; sort?: SortKey; page?: number; page_size?: number;
  sources?: Source[]; price_types?: PriceType[]; document_statuses?: DocumentStatus[];
}

export interface FacetCount { value: string; count: number; }
export interface ModelFacet { brand: string; model: string; count: number; }
/** What the current search can still reach — hints for the range inputs. */
export interface FacetRanges {
  price_min: number | null; price_max: number | null; km_min: number | null; km_max: number | null;
  year_min: number | null; year_max: number | null;
}
/** Every filter in force, typed into the query or ticked, in the panel's own vocabulary. */
export interface AppliedFilters {
  category: Category | null; models: string[]; cities: string[]; gearbox: Gearbox | null; sources: Source[];
  price_types: PriceType[]; document_statuses: DocumentStatus[]; price_min: number | null; price_max: number | null;
  km_min: number | null; km_max: number | null; year_min: number | null; year_max: number | null; only_below_market: boolean;
}
export interface Facets {
  categories: Partial<Record<Category, number>>; models: ModelFacet[]; cities: FacetCount[]; sources: FacetCount[];
  gearboxes: FacetCount[]; ranges: FacetRanges; applied: AppliedFilters;
  model_count: number; data_as_of: string | null;
}

export interface HistogramBucket { low: number; high: number; count: number; }
export interface TrimStat { trim: string; count: number; price_median: number | null; }
export interface ModelStats {
  model: string; brand: string; category: Category; count: number; year_min: number | null; year_max: number | null;
  price_median: number | null; price_min: number | null; price_max: number | null;
  histogram: HistogramBucket[]; trims: TrimStat[]; top_deals: ListingCard[];
}

export interface CatalogSuggestion { brand: string; model: string; trim: string; category: Category; count: number; }

export interface EstimateRequest {
  category: Category; trim: string; year: number; km: number | null; insurance_months: number | null;
  body_condition: BodyCondition | null; asking_price: number | null;
}
export interface EstimateBreakdown { base: number; km_adjustment: number; insurance_adjustment: number; }
export interface EstimateResponse {
  est_price: number; low: number; high: number; est_basis: EstimateBasis; est_sample_size: number; breakdown: EstimateBreakdown;
  asking_verdict: Verdict | null; asking_diff_pct: number | null; similar: ListingCard[];
}

export interface AssistantMessage { role: ChatRole; text: string; }
export interface AssistantRequest { messages: AssistantMessage[]; compare_ids: string[]; }
export interface AssistantResponse { text: string; listings: ListingCard[]; answered_by: ParsedBy; }

export interface ApiErrorBody { error: { code: string; message: string; details: unknown }; }
