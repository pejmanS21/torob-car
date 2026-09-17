import Link from "next/link";
import type { CardView } from "@/lib/view";
import styles from "./MiniListing.module.css";

export function MiniListing({ card, bordered = false }: { card: CardView; bordered?: boolean }) {
  return (
    <Link href={card.href} className={`${styles.row} ${bordered ? styles.bordered : ""}`}>
      <div role="img" aria-label={card.title} className={styles.thumb} style={{ backgroundImage: `url(${card.img})` }} />
      <div className={styles.text}>
        <div className={styles.title}>{card.title}</div>
        <div className={styles.meta}>{card.meta}</div>
      </div>
      <div className={styles.price}>
        <div className={styles.amount}>{card.priceFa}</div>
        <div className={styles.verdict} style={{ color: card.verdict.color }}>{card.verdict.label}</div>
      </div>
    </Link>
  );
}
