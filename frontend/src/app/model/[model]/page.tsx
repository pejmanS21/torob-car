import { notFound } from "next/navigation";
import { ModelScreen } from "@/components/ModelScreen";
import { ApiError, apiGet } from "@/lib/api/client";
import type { ModelStats } from "@/lib/api/types";

// Rendered on request (no generateStaticParams); `model` is the URL-encoded model name.
export default async function ModelPage({ params }: { params: Promise<{ model: string }> }) {
  const { model } = await params;
  let stats: ModelStats;
  try {
    stats = await apiGet<ModelStats>(`/models/${encodeURIComponent(decodeURIComponent(model))}/stats`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error; // → app/error.tsx
  }
  return <ModelScreen stats={stats} />;
}
