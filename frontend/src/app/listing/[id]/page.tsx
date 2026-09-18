import { notFound } from "next/navigation";
import { ListingScreen } from "@/components/ListingScreen";
import { ApiError, apiGet } from "@/lib/api/client";
import type { ListingCard, ListingDetail } from "@/lib/api/types";

const SIMILAR_LIMIT = 3;
const NOT_FOUND_STATUSES = [404, 422]; // 422 = not even a UUID

// Rendered on request (no generateStaticParams): detail and similar in parallel.
export default async function ListingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let detail: ListingDetail;
  let similar: ListingCard[];
  try {
    [detail, similar] = await Promise.all([
      apiGet<ListingDetail>(`/listings/${id}`),
      apiGet<ListingCard[]>(`/listings/${id}/similar`, { limit: SIMILAR_LIMIT }),
    ]);
  } catch (error) {
    if (error instanceof ApiError && NOT_FOUND_STATUSES.includes(error.status)) notFound();
    throw error; // → app/error.tsx
  }
  return <ListingScreen detail={detail} similar={similar} />;
}
