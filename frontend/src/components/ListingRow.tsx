import Link from "next/link";
import type { CardView } from "@/lib/view";
import { VerdictBadge } from "./VerdictBadge";
import styles from "./ListingRow.module.css";

export function ListingRow({ card }: { card: CardView }) {
  return (
    <Link href={card.href} className={styles.row}>
      <div role="img" aria-label={card.title} className={styles.thumb} style={{ backgroundImage: `url(${card.img})` }} />
      <div className={styles.text}>
        <div className={styles.titleRow}>
          <span className={styles.title}>{card.title}</span>
          <VerdictBadge verdict={card.verdict} size="sm" />
        </div>
        <div className={styles.meta}>{card.meta}</div>
        <div className={styles.meta}>بدنه {card.body} · بیمه {card.insFa} ماه</div>
      </div>
      <div className={styles.price}>
        <div className={styles.amount}>{card.priceText}</div>
        <div className={styles.diff} style={{ color: card.verdict.color }}>{card.diffText}</div>
        <div className={styles.score}>ارزش خرید <b className={styles.scoreVal}>{card.scoreFa}</b>/۱۰۰</div>
      </div>
    </Link>
  );
}
