import styles from "./SpecsGrid.module.css";

export function SpecsGrid({ specs }: Readonly<{ specs: { k: string; v: string }[] }>) {
  return (
    <div className={styles.card}>
      <div className={styles.title}>مشخصات</div>
      <div className={styles.grid}>
        {specs.map((s) => (
          <div key={s.k} className={styles.row}>
            <span className={styles.key}>{s.k}</span>
            <span className={styles.val}>{s.v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
