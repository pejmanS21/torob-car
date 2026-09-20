"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, apiGet } from "@/lib/api/client";
import type { Facets, ListingCard as ListingCardData, ModelStats, SearchParams, SearchResponse, SortKey } from "@/lib/api/types";
import { useApi } from "@/lib/api/useApi";
import { fa, formatToman } from "@/lib/format";
import { DEFAULT_PAGE_SIZE, activeFilterCount, paramsToQuery } from "@/lib/search";
import { cardOf } from "@/lib/view";
import { useAppState } from "@/state/AppState";
import { ErrorBanner } from "./ErrorBanner";
import { FiltersPanel } from "./FiltersPanel";
import { ListingCard } from "./ListingCard";
import { MapCard } from "./MapCard";
import { ModelCard } from "./ModelCard";
import { ParsedChips } from "./ParsedChips";
import { ResultsToolbar } from "./ResultsToolbar";
import { CardSkeletons } from "./Skeleton";
import styles from "./ResultsScreen.module.css";

const MAX_MODEL_CARDS = 4;
const RULES_HINT = "تفسیر: قواعد";
const ALERT_ROUNDING = 10_000_000;

const uniqueModels = (items: ListingCardData[]): string[] =>
  [...new Set(items.filter((l) => l.is_exact && l.model).map((l) => l.model as string))];

const medianPrice = (items: ListingCardData[]): number => {
  const prices = items.map((l) => l.price).filter((p): p is number => p !== null).sort((a, b) => a - b);
  return prices.length ? prices[Math.floor(prices.length / 2)] : 0;
};

interface Props {
  params: SearchParams;
  sheetOpen: boolean;
  onSheetOpenChange: (open: boolean) => void;
}

export function ResultsScreen({ params, sheetOpen, onSheetOpenChange }: Props) {
  const router = useRouter();
  const { addAlert } = useAppState();
  const [more, setMore] = useState<ListingCardData[]>([]);
  const [moreError, setMoreError] = useState<ApiError | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const query = paramsToQuery(params);
  const search = useApi(`search${query}`, (signal) => apiGet<SearchResponse>("/search", { ...params, page: 1, page_size: DEFAULT_PAGE_SIZE }, signal));
  const facets = useApi(`facets:${params.category ?? ""}`, (signal) => apiGet<Facets>("/facets", { category: params.category }, signal));

  const items = [...(search.data?.items ?? []), ...more];
  const modelsInResults = uniqueModels(items);
  const modelNames = params.models?.length ? params.models : modelsInResults.length <= MAX_MODEL_CARDS ? modelsInResults : [];
  const stats = useApi(modelNames.length ? `stats:${modelNames.join("|")}` : null, (signal) =>
    Promise.all(modelNames.map((model) => apiGet<ModelStats>(`/models/${encodeURIComponent(model)}/stats`, {}, signal))));

  useEffect(() => { document.body.style.overflow = sheetOpen ? "hidden" : ""; return () => { document.body.style.overflow = ""; }; }, [sheetOpen]);

  const navigate = (next: SearchParams) => router.replace(`/results${paramsToQuery(next)}`);
  const exact = items.filter((l) => l.is_exact);
  const nearMisses = items.filter((l) => !l.is_exact);
  const total = search.data?.total ?? 0;
  const hasMore = total > items.length;
  const dataAsOf = facets.data?.data_as_of ?? null;

  async function loadMore() {
    if (!search.data || loadingMore) return;
    setLoadingMore(true);
    setMoreError(null);
    const page = Math.floor(items.length / DEFAULT_PAGE_SIZE) + 1;
    try {
      const next = await apiGet<SearchResponse>("/search", { ...params, page, page_size: DEFAULT_PAGE_SIZE });
      setMore((loaded) => [...loaded, ...next.items]);
    } catch (error) {
      setMoreError(error instanceof ApiError ? error : new ApiError(0, "network_error", "network failure"));
    } finally {
      setLoadingMore(false);
    }
  }

  function retrySearch() {
    // Page 1 is about to be re-fetched; drop any already-loaded page 2+ so it
    // can't be duplicated once loadMore recomputes its page from items.length.
    setMore([]);
    setMoreError(null);
    search.retry();
  }

  function saveSearch() {
    const chips = search.data?.intent.chips ?? [];
    const threshold = params.price_max ?? Math.round(medianPrice(exact) / ALERT_ROUNDING) * ALERT_ROUNDING;
    if (!threshold) return;
    addAlert({ title: chips.length ? chips.slice(0, 2).join(" · ") : "جست‌وجوی فعلی", params, threshold });
  }

  const axisMin = Math.min(...(stats.data ?? []).map((s) => s.price_min ?? Infinity));
  const axisMax = Math.max(...(stats.data ?? []).map((s) => s.price_max ?? -Infinity));
  const cheaperCount = exact.filter((l) => l.verdict === "cheap").length;
  const activeCount = activeFilterCount(params);

  return (
    <section className={styles.layout}>
      <FiltersPanel params={params} facets={facets.data} onChange={navigate} onReset={() => navigate(params.q ? { q: params.q } : {})} open={sheetOpen} onClose={() => onSheetOpenChange(false)} resultCount={search.data ? total : null} />
      <div className={styles.main}>
        {search.data && search.data.intent.chips.length > 0 && (
          <ParsedChips chips={search.data.intent.chips} hint={search.data.parsed_by === "rules" ? RULES_HINT : undefined} />
        )}
        <ResultsToolbar countFa={search.data ? fa(total) : "…"} subtitle={search.data ? `${fa(cheaperCount)} آگهی ارزان‌تر از بازار` : ""} filtersLabel={activeCount ? `فیلترها (${fa(activeCount)})` : "فیلترها"} onOpenFilters={() => onSheetOpenChange(true)} sort={params.sort ?? "relevance"} onSort={(sort: SortKey) => navigate({ ...params, sort })} onSave={saveSearch} />
        {search.error && <ErrorBanner error={search.error} onRetry={retrySearch} />}
        {search.loading && <div className={styles.grid}><CardSkeletons count={6} /></div>}
        {stats.data && stats.data.length > 0 && (
          <div className={styles.modelCards}>{stats.data.map((s) => <ModelCard key={s.model} stats={s} axisMin={axisMin} axisMax={axisMax} />)}</div>
        )}
        {search.data && total === 0 && <div className={styles.empty}>با این شرایط چیزی پیدا نشد. سقف قیمت یا کارکرد رو بالا ببر یا شهر رو حذف کن.</div>}
        {exact.length > 0 && <div className={styles.grid}>{exact.map((l) => <ListingCard key={l.id} card={cardOf(l, dataAsOf)} />)}</div>}
        {nearMisses.length > 0 && (
          <>
            <div className={styles.divider}>آگهی‌های مشابه</div>
            <div className={styles.grid}>{nearMisses.map((l) => <ListingCard key={l.id} card={cardOf(l, dataAsOf)} />)}</div>
          </>
        )}
        {moreError && <ErrorBanner error={moreError} onRetry={loadMore} />}
        {hasMore && <button type="button" className={styles.more} onClick={loadMore} disabled={loadingMore}>{loadingMore ? "در حال بارگذاری…" : `بیشتر (${fa(total - items.length)} آگهی دیگر)`}</button>}
        {items.some((l) => l.lat !== null) && (
          <div className={styles.mapBlock}>
            <MapCard title="آگهی‌ها روی نقشه" hint={`${fa(items.length)} آگهی بارگذاری‌شده · قیمت میانه ${formatToman(medianPrice(items))}`} listings={items} />
          </div>
        )}
      </div>
    </section>
  );
}
