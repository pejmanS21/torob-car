import type { BreakdownRow } from "@/lib/types";
import styles from "./BreakdownList.module.css";

export function BreakdownRows({ rows }: { rows: BreakdownRow[] }) {
  return (
    <>
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
    </>
  );
}

export function BreakdownList({ title, rows }: { title: string; rows: BreakdownRow[] }) {
  return (
    <div className={styles.card}>
      <div className={styles.title}>{title}</div>
      <BreakdownRows rows={rows} />
    </div>
  );
}
