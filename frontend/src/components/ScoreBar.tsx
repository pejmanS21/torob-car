import styles from "./ScoreBar.module.css";

interface ScoreBarProps {
  score: number;
  scoreFa: string;
  color: string;
}

export function ScoreBar({ score, scoreFa, color }: Readonly<ScoreBarProps>) {
  return (
    <div className={styles.row}>
      <div className={styles.track}>
        <div className={styles.fill} style={{ width: `${score}%`, background: color }} />
      </div>
      <span className={styles.label}>ارزش خرید {scoreFa}</span>
    </div>
  );
}
