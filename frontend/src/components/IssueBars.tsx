import type { IssueBar } from "@/lib/modelStats";
import styles from "./IssueBars.module.css";

export function IssueBars({ issues }: { issues: IssueBar[] }) {
  return (
    <div className={styles.card}>
      <div className={styles.title}>نکات پرتکرار در توضیحات</div>
      <div className={styles.hint}>استخراج‌شده از متن آگهی‌ها با هوش مصنوعی</div>
      <div className={styles.list}>
        {issues.map((issue) => (
          <div key={issue.name} className={styles.row}>
            <span className={styles.name}>{issue.name}</span>
            <div className={styles.track}>
              <div className={styles.fill} style={{ width: `${issue.widthPct}%`, background: issue.neg ? "var(--red)" : "var(--green)" }} />
            </div>
            <span className={styles.pct}>{issue.pctText}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
