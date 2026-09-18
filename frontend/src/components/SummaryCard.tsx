import { isNegativeIssue } from "@/lib/catalog";
import { Icon } from "./Icon";
import styles from "./SummaryCard.module.css";

export function SummaryCard({ summary, tags }: { summary: string; tags: string[] }) {
  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <Icon name="sparkles" size={18} stroke="var(--red)" />
        <span className={styles.title}>خلاصهٔ وضعیت خودرو</span>
        <span className={styles.hint}>از متن آگهی و مشخصات</span>
      </div>
      <p className={styles.summary}>{summary}</p>
      <div className={styles.tags}>
        {tags.map((tag) => {
          const neg = isNegativeIssue(tag);
          return (
            <span key={tag} className={styles.tag} style={{ background: neg ? "var(--red-soft)" : "var(--green-soft)", color: neg ? "var(--red-ink)" : "var(--green)" }}>
              {tag}
            </span>
          );
        })}
      </div>
    </div>
  );
}
