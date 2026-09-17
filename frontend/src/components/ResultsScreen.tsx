"use client";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { fa } from "@/lib/format";
import { LISTINGS } from "@/lib/listings";
import { modelRange } from "@/lib/modelStats";
import { CHEAP_THRESHOLD_PCT } from "@/lib/pricing";
import { DEFAULT_FILTERS, activeFilterCount, chipsOf, filterListings, filtersFromQuery, parseQuery, sortListings } from "@/lib/search";
import type { Filters, SortKey } from "@/lib/types";
import { cardOf } from "@/lib/view";
import { useAppState } from "@/state/AppState";
import { FiltersPanel } from "./FiltersPanel";
import { ListingCard } from "./ListingCard";
import { ModelCard } from "./ModelCard";
import { ParsedChips } from "./ParsedChips";
import { ResultsToolbar } from "./ResultsToolbar";
import styles from "./ResultsScreen.module.css";

const MAX_MODEL_CARDS = 4;

export function ResultsScreen({ query }: { query: string }) {
  const router = useRouter();
  const { addAlert } = useAppState();
  const parsed = useMemo(() => (query ? parseQuery(query) : null), [query]);
  const [filters, setFilters] = useState<Filters>(() => (parsed ? filtersFromQuery(parsed) : DEFAULT_FILTERS));
  const [sort, setSort] = useState<SortKey>("score");
  const [sheetOpen, setSheetOpen] = useState(false);

  useEffect(() => { document.body.style.overflow = sheetOpen ? "hidden" : ""; return () => { document.body.style.overflow = ""; }; }, [sheetOpen]);

  const filtered = useMemo(() => filterListings(LISTINGS, filters), [filters]);
  const results = useMemo(() => sortListings(filtered, sort), [filtered, sort]);
  const chips = parsed ? chipsOf(parsed) : [];
  const modelsInResults = [...new Set(filtered.map((l) => l.modelId))];
  const modelCardIds = filters.models.length ? filters.models : modelsInResults.length <= MAX_MODEL_CARDS ? modelsInResults : [];
  const cheaperCount = filtered.filter((l) => l.diffPct <= CHEAP_THRESHOLD_PCT).length;
  const activeCount = activeFilterCount(filters);

  function resetFilters() { setFilters(DEFAULT_FILTERS); if (query) router.replace("/results"); }
  function saveSearch() {
    addAlert({ title: chips.length ? chips.slice(0, 2).join(" · ") : "جست‌وجوی فعلی", threshold: filters.maxPrice, matches: filtered.filter((l) => l.price < filters.maxPrice).length });
  }

  return (
    <section className={styles.layout}>
      <FiltersPanel filters={filters} onChange={setFilters} onReset={resetFilters} open={sheetOpen} onClose={() => setSheetOpen(false)} resultCount={results.length} />
      <div className={styles.main}>
        {chips.length > 0 && <ParsedChips chips={chips} />}
        <ResultsToolbar countFa={fa(results.length)} subtitle={`${fa(cheaperCount)} آگهی ارزان‌تر از بازار`} filtersLabel={activeCount ? `فیلترها (${fa(activeCount)})` : "فیلترها"} onOpenFilters={() => setSheetOpen(true)} sort={sort} onSort={setSort} onSave={saveSearch} />
        {modelCardIds.length > 0 && <div className={styles.modelCards}>{modelCardIds.map((id) => <ModelCard key={id} range={modelRange(id, LISTINGS)} />)}</div>}
        <div className={styles.grid}>{results.map((l) => <ListingCard key={l.id} card={cardOf(l)} />)}</div>
        {results.length === 0 && <div className={styles.empty}>با این فیلترها چیزی پیدا نشد. سقف قیمت یا کارکرد رو بالا ببر.</div>}
      </div>
    </section>
  );
}
