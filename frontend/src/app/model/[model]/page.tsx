import { connection } from "next/server";
import { notFound } from "next/navigation";
import { ModelScreen } from "@/components/ModelScreen";
import { ApiError, apiGet } from "@/lib/api/client";
import type { ModelStats } from "@/lib/api/types";
import { encodePathSegment } from "@/lib/url";

// Rendered on request (no generateStaticParams).
export default async function ModelPage({ params }: Readonly<{ params: Promise<{ model: string }> }>) {
  await connection();
  const { model } = await params;
  let stats: ModelStats;
  try {
    stats = await apiGet<ModelStats>(`/models/${encodePathSegment(model)}/stats`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error; // → app/error.tsx
  }
  return <ModelScreen stats={stats} />;
}
