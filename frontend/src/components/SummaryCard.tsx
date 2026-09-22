import { Icon } from "./Icon";
import styles from "./SummaryCard.module.css";

export function SummaryCard({ summary }: Readonly<{ summary: string }>) {
  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <Icon name="sparkles" size={18} stroke="var(--red)" />
        <span className={styles.title}>خلاصهٔ وضعیت خودرو</span>
        <span className={styles.hint}>از مشخصات و تخمین قیمت</span>
      </div>
      <p className={styles.summary}>{summary}</p>
    </div>
  );
}
