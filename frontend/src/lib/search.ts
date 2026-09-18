// Filter-sheet state only. The URL is the single source of truth: every filter change
// becomes new query params and a new /search request.
import type { Category, Gearbox, SearchParams, SortKey } from "./api/types";
import { buildQuery } from "./api/client";

export const CATEGORIES: Category[] = ["light", "heavy", "motorcycle", "rental", "classic"];
export const GEARBOXES: Gearbox[] = ["manual", "automatic"];
export const SORTS: SortKey[] = ["relevance", "deal", "price", "km", "newest"];
export const DEFAULT_PAGE_SIZE = 20;

const isCategory = (v: string | null): v is Category => v !== null && (CATEGORIES as string[]).includes(v);
const isGearbox = (v: string | null): v is Gearbox => v !== null && (GEARBOXES as string[]).includes(v);
const isSort = (v: string | null): v is SortKey => v !== null && (SORTS as string[]).includes(v);
const positive = (v: string | null): number | undefined => (v && /^\d+$/.test(v) && Number(v) > 0 ? Number(v) : undefined);

/** Everything the filter sheet can set, i.e. SearchParams without paging. */
export type SearchOverrides = Omit<SearchParams, "page" | "page_size">;

export const activeFilterCount = (o: SearchOverrides): number =>
  (o.category ? 1 : 0) + (o.models?.length ?? 0) + (o.cities?.length ?? 0) + (o.year ? 1 : 0) + (o.price_max ? 1 : 0) +
  (o.km_max ? 1 : 0) + (o.gearbox ? 1 : 0) + (o.only_below ? 1 : 0);

/** SearchParams → the query string of /results (and of GET /search), without paging. */
export const paramsToQuery = (params: SearchParams): string =>
  buildQuery({
    q: params.q, category: params.category, models: params.models, cities: params.cities, year: params.year,
    price_max: params.price_max, km_max: params.km_max, gearbox: params.gearbox, only_below: params.only_below || undefined,
    sort: params.sort === "relevance" ? undefined : params.sort,
  });

/** URL search params → SearchParams. Unknown or malformed values are dropped, never guessed. */
export function queryToParams(query: URLSearchParams): SearchParams {
  const q = query.get("q")?.trim();
  const category = query.get("category");
  const gearbox = query.get("gearbox");
  const sort = query.get("sort");
  const models = query.getAll("models").filter(Boolean);
  const cities = query.getAll("cities").filter(Boolean);
  const params: SearchParams = {};
  if (q) params.q = q;
  if (isCategory(category)) params.category = category;
  if (models.length) params.models = models;
  if (cities.length) params.cities = cities;
  if (positive(query.get("year"))) params.year = positive(query.get("year"));
  if (positive(query.get("price_max"))) params.price_max = positive(query.get("price_max"));
  if (positive(query.get("km_max"))) params.km_max = positive(query.get("km_max"));
  if (isGearbox(gearbox)) params.gearbox = gearbox;
  if (query.get("only_below") === "true") params.only_below = true;
  if (isSort(sort)) params.sort = sort;
  return params;
}
