import Link from "next/link";
import type { ModelRange } from "@/lib/modelStats";
import styles from "./ModelCard.module.css";

export function ModelCard({ range }: { range: ModelRange }) {
  return (
    <Link href={`/model/${range.id}`} className={styles.card}>
      <div className={styles.head}>
        <span className={styles.name}>{range.name}</span>
        <span className={styles.count}>{range.countFa} آگهی</span>
      </div>
      <div className={styles.range}>از <b className={styles.bold}>{range.minFa}</b> تا <b className={styles.bold}>{range.maxFa}</b> میلیون</div>
      <div className={styles.bar}>
        <div className={styles.barFill} style={{ right: `${range.barStartPct}%`, width: `${range.barWidthPct}%` }} />
      </div>
      <div className={styles.cta}>مشاهده صفحهٔ مدل ←</div>
    </Link>
  );
}
