import type { BreakdownRow, VerdictStyle } from "@/lib/types";
import { BreakdownRows } from "./BreakdownList";
import { VerdictBadge } from "./VerdictBadge";
import styles from "./BreakdownCard.module.css";

interface Props { verdict: VerdictStyle; diffText: string; rows: BreakdownRow[]; estText: string; priceText: string; note: string; }

export function BreakdownCard({ verdict, diffText, rows, estText, priceText, note }: Props) {
  return (
    <div className={styles.card}>
      <div className={styles.head} style={{ background: verdict.bg }}>
        <VerdictBadge verdict={verdict} size="lg" />
        <span className={styles.diff} style={{ color: verdict.color }}>
          {diffText}
        </span>
      </div>
      <div className={styles.body}>
        <BreakdownRows rows={rows} />
        <div className={styles.total}>
          <span>تخمین قیمت بازار</span>
          <span>{estText}</span>
        </div>
        <div className={styles.totalLast}>
          <span>قیمت آگهی</span>
          <span>{priceText}</span>
        </div>
        <div className={styles.summary}>{note}</div>
      </div>
    </div>
  );
}
