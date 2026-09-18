import type { EstimateResult } from "@/lib/estimate";
import { fa, num } from "@/lib/format";
import { VerdictBadge } from "./VerdictBadge";
import styles from "./EstimateResultCard.module.css";

export function EstimateResultCard({ result }: { result: EstimateResult }) {
  return (
    <div className={styles.card}>
      <div className={styles.label}>تخمین ترب‌کار برای {result.title}</div>
      <div className={styles.est}>
        {num(result.est)} <span className={styles.unit}>میلیون تومان</span>
      </div>
      <div className={styles.range}>
        بازهٔ منطقی: {num(result.low)} تا {num(result.high)} میلیون · بر اساس {fa(result.similarCount)} آگهی فعال
      </div>
      {result.asking && (
        <div className={styles.asking}>
          <VerdictBadge verdict={result.asking.verdict} size="lg" />
          <span className={styles.askingText}>{result.asking.text}</span>
        </div>
      )}
    </div>
  );
}
