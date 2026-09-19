import type { CSSProperties } from "react";
import Link from "next/link";
import type { ListingCard } from "@/lib/api/types";
import { compareRows } from "@/lib/compare";
import { cardOf } from "@/lib/view";
import styles from "./CompareTable.module.css";

interface Props { cards: ListingCard[]; onRemove(id: string): void; }

export function CompareTable({ cards, onRemove }: Props) {
  const rows = compareRows(cards);
  const wrapStyle = { "--cols": cards.length } as CSSProperties;
  return (
    <div className={styles.wrap} style={wrapStyle}>
      <div className={styles.table}>
        <div className={styles.headRow}>
          <div className={styles.feature}>ویژگی</div>
          {cards.map((listing) => {
            const card = cardOf(listing);
            return (
              <div key={listing.id} className={styles.carCell}>
                <div role="img" aria-label={card.title} className={styles.photo} style={{ backgroundImage: `url(${card.img})` }} />
                <Link href={card.href} className={styles.title}>{card.title}</Link>
                <div className={styles.meta}>{card.meta}</div>
                <button onClick={() => onRemove(listing.id)} className={styles.remove} aria-label="حذف از مقایسه">×</button>
              </div>
            );
          })}
        </div>
        {rows.map((row) => (
          <div key={row.label} className={styles.row}>
            <div className={styles.label}>{row.label}</div>
            {row.cells.map((cell, index) => (
              <div key={cards[index].id} className={styles.cell} style={{ color: cell.color, background: cell.best ? "var(--green-soft)" : "transparent" }}>
                {cell.text}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
