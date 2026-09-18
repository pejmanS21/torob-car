"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo } from "react";
import { ResultsScreen } from "@/components/ResultsScreen";
import { CardSkeletons } from "@/components/Skeleton";
import { queryToParams } from "@/lib/search";

function Results() {
  const query = useSearchParams();
  const params = useMemo(() => queryToParams(query), [query]);
  // The URL is the single source of truth: a new query string is a new screen.
  return <ResultsScreen key={query.toString()} params={params} />;
}

export default function ResultsPage() {
  return <Suspense fallback={<CardSkeletons count={4} />}><Results /></Suspense>;
}
