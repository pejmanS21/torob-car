"use client";

import type { ListingDetail } from "@/lib/api/types";
import { fa, num } from "@/lib/format";
import type { CardView } from "@/lib/view";
import { useAppState } from "@/state/AppState";
import { Icon } from "./Icon";
import styles from "./PriceCard.module.css";

export function PriceCard({ detail, card }: { detail: ListingDetail; card: CardView }) {
  const { compare, saved, toggleCompare, toggleSaved } = useAppState();
  const inCompare = compare.includes(detail.id);
  const isSaved = saved.includes(detail.id);
  const quick = [
    { k: "کارکرد", v: detail.km === null ? "—" : num(detail.km) },
    { k: "مدل (سال تولید)", v: detail.year === null ? "—" : fa(detail.year) },
    { k: "رنگ", v: detail.color ?? "—" },
  ];

  return (
    <div className={styles.card}>
      <div className={styles.headRow}>
        <h1 className={styles.title}>{card.title}</h1>
        <span className={styles.posted} suppressHydrationWarning>{card.posted}</span>
      </div>
      <div className={styles.meta}>{card.meta}</div>
      <div className={styles.price}>
        {card.priceText}{detail.price !== null && <span className={styles.unit}> تومان</span>}
      </div>
      <div className={styles.actions}>
        <a href={detail.url} target="_blank" rel="noopener" className={styles.divar}>
          مشاهده در دیوار
        </a>
        <button
          type="button"
          onClick={() => toggleCompare(detail.id)}
          className={styles.compare}
          style={{
            borderColor: inCompare ? "var(--red)" : "var(--line)",
            background: inCompare ? "var(--red-soft)" : "var(--surface)",
            color: inCompare ? "var(--red-ink)" : "var(--ink)",
          }}
        >
          {inCompare ? "✓ در مقایسه" : "+ مقایسه"}
        </button>
        <button type="button" onClick={() => toggleSaved(detail.id)} title="نشان‌کردن" aria-pressed={isSaved} className={styles.bookmark}>
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
