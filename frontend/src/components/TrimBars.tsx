import type { TrimStat } from "@/lib/api/types";
import { fa, formatToman } from "@/lib/format";
import styles from "./TrimBars.module.css";

const MAX_TRIMS = 6;

/** Share of the model's listings per trim, with each trim's median price. */
export function TrimBars({ trims, total }: Readonly<{ trims: TrimStat[]; total: number }>) {
  return (
    <div className={styles.card}>
      <div className={styles.title}>تیپ‌های این مدل</div>
      <div className={styles.hint}>سهم هر تیپ از آگهی‌ها و میانهٔ قیمت آن</div>
      <div className={styles.list}>
        {trims.slice(0, MAX_TRIMS).map((trim) => {
          const pct = total ? Math.round((trim.count / total) * 100) : 0;
          return (
            <div key={trim.trim} className={styles.row}>
              <span className={styles.name} title={trim.trim}>{trim.trim}</span>
              <div className={styles.track}>
                <div className={styles.fill} style={{ width: `${pct}%`, background: "var(--red)" }} />
              </div>
              <span className={styles.pct}>{fa(pct)}٪ · {trim.price_median === null ? "—" : formatToman(trim.price_median)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
