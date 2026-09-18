"use client";

import { useMemo } from "react";
import { fa, num } from "@/lib/format";
import { LISTINGS, findListing } from "@/lib/listings";
import { breakdownRows, summaryOf, verdictNote } from "@/lib/pricing";
import type { Listing } from "@/lib/types";
import { cardOf } from "@/lib/view";
import { Breadcrumbs } from "./Breadcrumbs";
import { BreakdownCard } from "./BreakdownCard";
import { Gallery } from "./Gallery";
import { MapCard } from "./MapCard";
import { PriceCard } from "./PriceCard";
import { SellerAssessmentCard } from "./SellerAssessmentCard";
import { SellerText } from "./SellerText";
import { SimilarListings } from "./SimilarListings";
import { SpecsGrid } from "./SpecsGrid";
import { SummaryCard } from "./SummaryCard";
import styles from "./ListingScreen.module.css";

const SIMILAR_COUNT = 3;
const TOMAN_PER_MILLION = 1e6;

function similarTo(listing: Listing): Listing[] {
  return LISTINGS.filter((x) => x.modelId === listing.modelId && x.id !== listing.id)
    .sort((a, b) => Math.abs(a.price - listing.price) - Math.abs(b.price - listing.price))
    .slice(0, SIMILAR_COUNT);
}

function specsOf(l: Listing): { k: string; v: string }[] {
  return [
    ["برند و مدل", l.modelName], ["سال ساخت", fa(l.year)], ["کارکرد", `${num(l.km)} کیلومتر`], ["رنگ", l.color], ["گیربکس", l.gear], ["نوع سوخت", "بنزین"],
    ["وضعیت بدنه", l.body.name], ["قیمت پایه (فروشنده)", `${num(l.price * TOMAN_PER_MILLION)} تومان`], ["مهلت بیمهٔ شخص ثالث", `${fa(l.ins)} ماه`], ["محل", `${l.city}، ${l.district}`], ["منبع", "دیوار"],
  ].map(([k, v]) => ({ k, v }));
}

export function ListingScreen({ listingId }: { listingId: string }) {
  const listing = useMemo(() => findListing(listingId), [listingId]);
  const mapListings = useMemo(() => (listing ? [listing] : []), [listing]);
  if (!listing) throw new Error(`Listing ${listingId} not found`); // page.tsx already 404s unknown ids

  const card = cardOf(listing);
  const modelHref = `/model/${listing.modelId}`;
  const cityQuery = `${listing.modelName} ${listing.city}`;

  return (
    <section className={styles.screen}>
      <Breadcrumbs items={[{ label: "خانه", href: "/" }, { label: listing.modelName, href: modelHref }, { label: card.title }]} />
      <div className={styles.grid}>
        <div className={styles.mainCol}>
          <Gallery key={listing.id} photos={listing.photos} title={card.title} />
          <SummaryCard summary={summaryOf(listing)} tags={listing.tags} />
          <SpecsGrid specs={specsOf(listing)} />
          <SellerText
            desc={listing.desc}
            links={[
              { text: listing.modelName, href: modelHref },
              { text: `${listing.modelName} در ${listing.city}`, href: `/results?q=${encodeURIComponent(cityQuery)}` },
            ]}
          />
          <MapCard title="محل خودرو" hint={`${listing.city}، ${listing.district} · محدودهٔ تقریبی`} listings={mapListings} single />
        </div>
        <div className={styles.sideCol}>
          <PriceCard listing={listing} card={card} />
          <SellerAssessmentCard assess={listing.assess} />
          <BreakdownCard verdict={card.verdict} diffText={card.diffText} rows={breakdownRows(listing)} estFa={num(listing.est)} priceFa={card.priceFa} note={verdictNote(listing)} />
          <SimilarListings title="آگهی‌های مشابه" cards={similarTo(listing).map(cardOf)} />
        </div>
      </div>
    </section>
  );
}
