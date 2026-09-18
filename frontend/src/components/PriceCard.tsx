"use client";

import { fa, num } from "@/lib/format";
import type { Listing } from "@/lib/types";
import type { CardView } from "@/lib/view";
import { useAppState } from "@/state/AppState";
import { Icon } from "./Icon";
import styles from "./PriceCard.module.css";

export function PriceCard({ listing, card }: { listing: Listing; card: CardView }) {
  const { compare, saved, toggleCompare, toggleSaved } = useAppState();
  const inCompare = compare.includes(listing.id);
  const isSaved = saved.includes(listing.id);
  const quick = [
    { k: "کارکرد", v: num(listing.km) },
    { k: "مدل (سال تولید)", v: fa(listing.year) },
    { k: "رنگ", v: listing.color },
  ];

  return (
    <div className={styles.card}>
      <div className={styles.headRow}>
        <h1 className={styles.title}>{card.title}</h1>
        <span className={styles.posted}>{card.posted}</span>
      </div>
      <div className={styles.meta}>{card.meta}</div>
      <div className={styles.price}>
        {card.priceFa} <span className={styles.unit}>میلیون تومان</span>
      </div>
      <div className={styles.actions}>
        <a href={`https://divar.ir/v/-/${listing.token}`} target="_blank" rel="noopener" className={styles.divar}>
          مشاهده در دیوار
        </a>
        <button
          type="button"
          onClick={() => toggleCompare(listing.id)}
          className={styles.compare}
          style={{
            borderColor: inCompare ? "var(--red)" : "var(--line)",
            background: inCompare ? "var(--red-soft)" : "var(--surface)",
            color: inCompare ? "var(--red-ink)" : "var(--ink)",
          }}
        >
          {inCompare ? "✓ در مقایسه" : "+ مقایسه"}
        </button>
        <button type="button" onClick={() => toggleSaved(listing.id)} title="نشان‌کردن" aria-pressed={isSaved} className={styles.bookmark}>
          <Icon name="bookmark" size={18} stroke="var(--ink)" fill={isSaved ? "#172033" : "none"} />
        </button>
      </div>
      <div className={styles.quick}>
        {quick.map((q) => (
          <div key={q.k} className={styles.quickItem}>
            <div className={styles.quickKey}>{q.k}</div>
            <div className={styles.quickVal}>{q.v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
