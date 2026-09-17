"use client";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ResultsScreen } from "@/components/ResultsScreen";

function Results() {
  const query = useSearchParams().get("q") ?? "";
  return <ResultsScreen key={query} query={query} />; // key resets filters when the query changes
}

export default function ResultsPage() {
  return <Suspense fallback={null}><Results /></Suspense>;
}
