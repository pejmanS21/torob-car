// Filter-sheet state only. The URL is the single source of truth: every filter change
// becomes new query params and a new /search request.
import type { Category, DocumentStatus, Gearbox, PriceType, SearchParams, Source, SortKey } from "./api/types";
import { buildQuery } from "./api/client";

export const CATEGORIES: Category[] = ["light", "heavy", "motorcycle", "rental", "classic"];
export const GEARBOXES: Gearbox[] = ["manual", "automatic"];
export const SORTS: SortKey[] = ["relevance", "deal", "price", "km", "newest"];
export const SOURCES: Source[] = ["divar", "bama", "karnameh", "hamrah_mechanic"];
export const PRICE_TYPES: PriceType[] = ["lumpsum", "negotiable", "installment"];
export const DOCUMENT_STATUSES: DocumentStatus[] = [
  "title_in_name", "ready_to_transfer", "white_title", "no_title", "mortgaged", "single_page", "two_page", "multi_page",
];
export const DEFAULT_PAGE_SIZE = 20;

const isCategory = (v: string | null): v is Category => v !== null && (CATEGORIES as string[]).includes(v);
const isGearbox = (v: string | null): v is Gearbox => v !== null && (GEARBOXES as string[]).includes(v);
const isSort = (v: string | null): v is SortKey => v !== null && (SORTS as string[]).includes(v);
const isSource = (v: string): v is Source => (SOURCES as string[]).includes(v);
const isPriceType = (v: string): v is PriceType => (PRICE_TYPES as string[]).includes(v);
const isDocumentStatus = (v: string): v is DocumentStatus => (DOCUMENT_STATUSES as string[]).includes(v);
const positive = (v: string | null): number | undefined => (v && /^\d+$/.test(v) && Number(v) > 0 ? Number(v) : undefined);

/** Everything the filter sheet can set, i.e. SearchParams without paging. */
export type SearchOverrides = Omit<SearchParams, "page" | "page_size">;

export const activeFilterCount = (o: SearchOverrides): number =>
  (o.category ? 1 : 0) + (o.models?.length ?? 0) + (o.cities?.length ?? 0) +
  // A range is one filter, whether one end is set or both.
  (o.year_min || o.year_max ? 1 : 0) + (o.price_min || o.price_max ? 1 : 0) + (o.km_min || o.km_max ? 1 : 0) + (o.gearbox ? 1 : 0) + (o.only_below ? 1 : 0) +
  (o.sources?.length ?? 0) + (o.price_types?.length ?? 0) + (o.document_statuses?.length ?? 0);

/** SearchParams → the query string of /results (and of GET /search), without paging. */
export const paramsToQuery = (params: SearchParams): string =>
  buildQuery({
    q: params.q, category: params.category, models: params.models, cities: params.cities,
    year_min: params.year_min, year_max: params.year_max, price_min: params.price_min, price_max: params.price_max,
    km_min: params.km_min, km_max: params.km_max, gearbox: params.gearbox, only_below: params.only_below || undefined,
    sort: params.sort === "relevance" ? undefined : params.sort,
    sources: params.sources, price_types: params.price_types, document_statuses: params.document_statuses,
  });

/** URL search params → SearchParams. Unknown or malformed values are dropped, never guessed. */
export function queryToParams(query: URLSearchParams): SearchParams {
  const q = query.get("q")?.trim();
  const category = query.get("category");
  const gearbox = query.get("gearbox");
  const sort = query.get("sort");
  const models = query.getAll("models").filter(Boolean);
  const cities = query.getAll("cities").filter(Boolean);
  const sources = query.getAll("sources").filter(isSource);
  const priceTypes = query.getAll("price_types").filter(isPriceType);
  const documentStatuses = query.getAll("document_statuses").filter(isDocumentStatus);
  const params: SearchParams = {};
  if (q) params.q = q;
  if (isCategory(category)) params.category = category;
  if (models.length) params.models = models;
  if (cities.length) params.cities = cities;
  // `year` is the old single-year link format: it still opens, as a one-year range.
  const year = positive(query.get("year"));
  for (const name of ["year_min", "year_max", "price_min", "price_max", "km_min", "km_max"] as const) {
    const value = positive(query.get(name)) ?? (name.startsWith("year") ? year : undefined);
    if (value) params[name] = value;
  }
  if (isGearbox(gearbox)) params.gearbox = gearbox;
  if (query.get("only_below") === "true") params.only_below = true;
  if (isSort(sort)) params.sort = sort;
  if (sources.length) params.sources = sources;
  if (priceTypes.length) params.price_types = priceTypes;
  if (documentStatuses.length) params.document_statuses = documentStatuses;
  return params;
}
