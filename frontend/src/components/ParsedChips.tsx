import { Icon } from "./Icon";
import styles from "./ParsedChips.module.css";

export function ParsedChips({ chips, hint }: { chips: string[]; hint?: string }) {
  return (
    <div className={styles.row}>
      <span className={styles.label}>
        <Icon name="sparkles" stroke="#d9232e" size={16} />
        از جست‌وجوت فهمیدم:
      </span>
      {chips.map((chip) => (
        <span key={chip} className={styles.chip}>{chip}</span>
      ))}
      {hint && <span className={styles.hint}>{hint}</span>}
    </div>
  );
}
