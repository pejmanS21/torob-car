import type { ListingCard, ListingDetail } from "@/lib/api/types";
import { formatToman } from "@/lib/format";
import { breakdownRows, summaryOf, verdictNote } from "@/lib/pricing";
import { specsOf } from "@/lib/specs";
import { cardOf } from "@/lib/view";
import { Breadcrumbs } from "./Breadcrumbs";
import { BreakdownCard } from "./BreakdownCard";
import { Gallery } from "./Gallery";
import { MapCard } from "./MapCard";
import { PriceCard } from "./PriceCard";
import { SellerText } from "./SellerText";
import { SimilarListings } from "./SimilarListings";
import { SpecsGrid } from "./SpecsGrid";
import { SummaryCard } from "./SummaryCard";
import styles from "./ListingScreen.module.css";

const NO_ESTIMATE = "بدون تخمین";

export function ListingScreen({ detail, similar }: Readonly<{ detail: ListingDetail; similar: ListingCard[] }>) {
  const card = cardOf(detail);
  const modelHref = detail.model ? `/model/${encodeURIComponent(detail.model)}` : "/results";
  const modelLabel = detail.model ?? detail.title;
  const cityQuery = `${modelLabel} ${detail.city}`;
  const photos = detail.image_urls.length ? detail.image_urls : [card.img];
  const location = detail.district ? `${detail.city}، ${detail.district}` : detail.city;

  return (
    <section className={styles.screen}>
      <Breadcrumbs items={[{ label: "خانه", href: "/" }, { label: modelLabel, href: modelHref }, { label: card.title }]} />
      <div className={styles.grid}>
        <div className={styles.mainCol}>
          <Gallery key={detail.id} photos={photos} title={card.title} />
          <SummaryCard summary={summaryOf(detail)} />
          <SpecsGrid specs={specsOf(detail)} />
          <SellerText
            desc={detail.description}
            links={[
              { text: modelLabel, href: modelHref },
              { text: `${modelLabel} در ${detail.city}`, href: `/results?q=${encodeURIComponent(cityQuery)}` },
            ]}
          />
          {detail.lat !== null && (
            <MapCard title="محل خودرو" hint={`${location} · محدودهٔ تقریبی`} listings={[detail]} single />
          )}
        </div>
        <div className={styles.sideCol}>
          <PriceCard detail={detail} card={card} />
          <BreakdownCard verdict={card.verdict} diffText={card.diffText} rows={breakdownRows(detail)} estText={detail.est_price === null ? NO_ESTIMATE : formatToman(detail.est_price)} priceText={card.priceText} note={verdictNote(detail)} />
          <SimilarListings title="آگهی‌های مشابه" cards={similar.map((l) => cardOf(l))} />
        </div>
      </div>
    </section>
  );
}
