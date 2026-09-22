import type { EstimateResponse } from "@/lib/api/types";
import { fa, formatToman } from "@/lib/format";
import { diffText, verdictStyle } from "@/lib/pricing";
import { VerdictBadge } from "./VerdictBadge";
import styles from "./EstimateResultCard.module.css";

export function EstimateResultCard({ result, title, year }: Readonly<{ result: EstimateResponse; title: string; year: number | null }>) {
  return (
    <div className={styles.card}>
      <div className={styles.label}>تخمین ترب‌کار برای {title}{year === null ? "" : ` مدل ${fa(year)}`}</div>
      <div className={styles.est}>
        {formatToman(result.est_price)} <span className={styles.unit}>تومان</span>
      </div>
      <div className={styles.range}>
        بازهٔ منطقی: {formatToman(result.low)} تا {formatToman(result.high)} · بر اساس {fa(result.est_sample_size)} آگهی فعال
      </div>
      {result.asking_verdict && (
        <div className={styles.asking}>
          <VerdictBadge verdict={verdictStyle(result.asking_verdict)} size="lg" />
          <span className={styles.askingText}>{diffText(result.asking_diff_pct)}</span>
        </div>
      )}
    </div>
  );
}
