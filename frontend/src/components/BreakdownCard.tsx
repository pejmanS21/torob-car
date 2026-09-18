import type { BreakdownRow, Verdict } from "@/lib/types";
import { VerdictBadge } from "./VerdictBadge";
import styles from "./BreakdownCard.module.css";

interface Props { verdict: Verdict; diffText: string; rows: BreakdownRow[]; estFa: string; priceFa: string; note: string; }

export function BreakdownCard({ verdict, diffText, rows, estFa, priceFa, note }: Props) {
  return (
    <div className={styles.card}>
      <div className={styles.head} style={{ background: verdict.bg }}>
        <VerdictBadge verdict={verdict} size="lg" />
        <span className={styles.diff} style={{ color: verdict.color }}>
          {diffText}
        </span>
      </div>
      <div className={styles.body}>
        {rows.map((row) => (
          <div key={row.label} className={styles.row}>
            <div>
              <div>{row.label}</div>
              <div className={styles.note}>{row.note}</div>
            </div>
            <span className={styles.val} style={{ color: row.color }}>
              {row.val}
            </span>
          </div>
        ))}
        <div className={styles.total}>
          <span>تخمین قیمت بازار</span>
          <span>{estFa} میلیون</span>
        </div>
        <div className={styles.totalLast}>
          <span>قیمت آگهی</span>
          <span>{priceFa} میلیون</span>
        </div>
        <div className={styles.summary}>{note}</div>
      </div>
    </div>
  );
}
