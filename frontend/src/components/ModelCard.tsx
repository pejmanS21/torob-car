import Link from "next/link";
import type { ModelStats } from "@/lib/api/types";
import { fa, formatToman } from "@/lib/format";
import styles from "./ModelCard.module.css";

interface Props { stats: ModelStats; axisMin: number; axisMax: number; }

/** Price range bar on an axis shared by every model card shown (lowest min → highest max). */
export function ModelCard({ stats, axisMin, axisMax }: Readonly<Props>) {
  // No range to plot: this model's own min/max, or the whole shared axis
  // (every card's min/max null), is missing — skip the bar instead of NaN%.
  const hasRange = stats.price_min !== null && stats.price_max !== null && Number.isFinite(axisMin) && Number.isFinite(axisMax);
  const span = Math.max(1, axisMax - axisMin);
  const min = stats.price_min ?? axisMin;
  const max = stats.price_max ?? min;
  const start = Math.max(0, Math.min(100, ((min - axisMin) / span) * 100));
  const width = Math.max(1, Math.min(100 - start, ((max - min) / span) * 100));
  return (
    <Link href={`/model/${encodeURIComponent(stats.model)}`} className={styles.card}>
      <div className={styles.head}>
        <span className={styles.name}>{stats.model}</span>
        <span className={styles.count}>{fa(stats.count)} آگهی</span>
      </div>
      <div className={styles.range}>
        {stats.price_min === null || stats.price_max === null ? "بدون قیمت" : <>از <b className={styles.bold}>{formatToman(stats.price_min)}</b> تا <b className={styles.bold}>{formatToman(stats.price_max)}</b></>}
      </div>
      {hasRange && (
        <div className={styles.bar}>
          <div className={styles.barFill} style={{ right: `${start}%`, width: `${width}%` }} />
        </div>
      )}
      <div className={styles.cta}>مشاهده صفحهٔ مدل ←</div>
    </Link>
  );
}
