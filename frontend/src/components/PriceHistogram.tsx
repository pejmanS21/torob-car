import type { HistogramBucket } from "@/lib/modelStats";
import styles from "./PriceHistogram.module.css";

export function PriceHistogram({ buckets, minFa, maxFa }: { buckets: HistogramBucket[]; minFa: string; maxFa: string }) {
  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <span className={styles.title}>پراکندگی قیمت آگهی‌ها</span>
        <span className={styles.unit}>میلیون تومان</span>
      </div>
      <div className={styles.hint}>هر ستون تعداد آگهی در آن بازهٔ قیمتی است؛ ستون پررنگ میانهٔ بازار.</div>
      <div className={styles.bars}>
        {buckets.map((bucket, i) => (
          <div key={i} className={styles.bucket} title={bucket.tip}>
            <span className={styles.count}>{bucket.countFa}</span>
            <div className={styles.bar} style={{ height: `${bucket.heightPct}%`, background: bucket.isMedian ? "var(--red)" : "var(--line)" }} />
          </div>
        ))}
      </div>
      <div className={styles.range}>
        <span>{minFa}</span>
        <span>{maxFa}</span>
      </div>
    </div>
  );
}
