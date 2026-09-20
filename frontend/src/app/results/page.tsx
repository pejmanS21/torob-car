"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { ResultsScreen } from "@/components/ResultsScreen";
import { CardSkeletons } from "@/components/Skeleton";
import { apiGet } from "@/lib/api/client";
import type { Facets } from "@/lib/api/types";
import { useApi } from "@/lib/api/useApi";
import { paramsToQuery, queryToParams } from "@/lib/search";

function Results() {
  const query = useSearchParams();
  const params = useMemo(() => queryToParams(query), [query]);
  // Lifted above the keyed component so a filter change (which changes the
  // query string, remounting ResultsScreen) doesn't close the mobile sheet.
  const [sheetOpen, setSheetOpen] = useState(false);
  // Fetched up here for the same reason, and the last answer stays on screen while
  // the next one loads — otherwise the whole filter column blanks on every click.
  const facetParams = { ...params, sort: undefined };
  const facets = useApi(`facets${paramsToQuery(facetParams)}`, (signal) => apiGet<Facets>("/facets", facetParams, signal));
  const [shownFacets, setShownFacets] = useState<Facets | null>(null);
  if (facets.data && facets.data !== shownFacets) setShownFacets(facets.data);
  // The URL is the single source of truth: a new query string is a new screen.
  return <ResultsScreen key={query.toString()} params={params} facets={shownFacets} sheetOpen={sheetOpen} onSheetOpenChange={setSheetOpen} />;
}

export default function ResultsPage() {
  return <Suspense fallback={<CardSkeletons count={4} />}><Results /></Suspense>;
}
