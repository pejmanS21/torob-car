import { notFound } from "next/navigation";
import { ListingScreen } from "@/components/ListingScreen";
import { LISTINGS, findListing } from "@/lib/listings";

export const generateStaticParams = () => LISTINGS.map((l) => ({ id: l.id }));

export default async function ListingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!findListing(id)) notFound();
  return <ListingScreen listingId={id} />;
}
