import Link from "next/link";
import type { CardView } from "@/lib/view";
import { ScoreBar } from "./ScoreBar";
import { VerdictBadge } from "./VerdictBadge";
import styles from "./ListingCard.module.css";

export function ListingCard({ card }: { card: CardView }) {
  return (
    <Link href={card.href} className={styles.card}>
      <div className={styles.photoWrap}>
        <div role="img" aria-label={card.title} className={styles.photo} style={{ backgroundImage: `url(${card.img})` }} />
        <span className={styles.badge}><VerdictBadge verdict={card.verdict} /></span>
      </div>
      <div className={styles.body}>
        <div className={styles.titleRow}><span className={styles.title}>{card.title}</span><span className={styles.posted}>{card.posted}</span></div>
        <div className={styles.meta}>{card.meta}</div>
        <div className={styles.priceRow}>
          <span className={styles.price}>{card.priceFa} <span className={styles.unit}>میلیون</span></span>
          <span className={styles.diff} style={{ color: card.verdict.color }}>{card.diffText}</span>
        </div>
        <ScoreBar score={card.score} scoreFa={card.scoreFa} color={card.scoreColor} />
      </div>
    </Link>
  );
}
