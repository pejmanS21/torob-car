import type { HistogramBucket } from "@/lib/api/types";
import { fa, formatToman } from "@/lib/format";
import styles from "./PriceHistogram.module.css";

const MAX_BAR_HEIGHT_PCT = 90;
const MIN_BAR_HEIGHT_PCT = 4;

export function PriceHistogram({ buckets, median }: Readonly<{ buckets: HistogramBucket[]; median: number | null }>) {
  const tallest = Math.max(1, ...buckets.map((b) => b.count));
  const medianIndex = median === null ? -1 : buckets.findIndex((b, i) => median >= b.low && (median < b.high || i === buckets.length - 1));
  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <span className={styles.title}>پراکندگی قیمت آگهی‌ها</span>
        <span className={styles.unit}>تومان</span>
      </div>
      <div className={styles.hint}>هر ستون تعداد آگهی در آن بازهٔ قیمتی است؛ ستون پررنگ میانهٔ بازار.</div>
      <div className={styles.bars}>
        {buckets.map((bucket, i) => (
          <div key={bucket.low} className={styles.bucket} title={`${formatToman(bucket.low)} تا ${formatToman(bucket.high)}`}>
            <span className={styles.count}>{bucket.count ? fa(bucket.count) : ""}</span>
            <div className={styles.bar} style={{ height: `${Math.max(MIN_BAR_HEIGHT_PCT, (bucket.count / tallest) * MAX_BAR_HEIGHT_PCT)}%`, background: i === medianIndex ? "var(--red)" : "var(--line)" }} />
          </div>
        ))}
      </div>
      <div className={styles.range}>
        <span>{buckets.length ? formatToman(buckets[0].low) : ""}</span>
        <span>{buckets.length ? formatToman(buckets.at(-1)!.high) : ""}</span>
      </div>
    </div>
  );
}
