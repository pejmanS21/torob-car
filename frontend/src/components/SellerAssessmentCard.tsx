import type { SellerAssessment } from "@/lib/types";
import styles from "./SellerAssessmentCard.module.css";

const OK_PREFIX = "سالم";

function rowsOf(assess: SellerAssessment): { k: string; v: string }[] {
  return [
    { k: "موتور", v: assess.engine },
    { k: "وضعیت شاسی‌ها", v: assess.chassis },
    { k: "بدنه", v: assess.bodyA },
    { k: "گیربکس", v: assess.gearbox },
  ];
}

export function SellerAssessmentCard({ assess }: { assess: SellerAssessment }) {
  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <span className={styles.title}>ارزیابی فروشنده</span>
        <span className={styles.hint}>اظهار فروشنده در دیوار</span>
      </div>
      {rowsOf(assess).map((row) => {
        const ok = row.v.startsWith(OK_PREFIX);
        const color = ok ? "var(--green)" : "var(--orange)";
        return (
          <div key={row.k} className={styles.row}>
            <span className={styles.badge} style={{ background: ok ? "var(--green-soft)" : "var(--orange-soft)", color }}>
              {ok ? "✓" : "!"}
            </span>
            <span className={styles.key}>{row.k}</span>
            <span className={styles.val} style={{ color }}>
              {row.v}
            </span>
          </div>
        );
      })}
    </div>
  );
}
