import styles from "./Skeleton.module.css";

/** Pulsing placeholder blocks; `lines` rows of the given heights (px). */
export function Skeleton({ lines = [24, 16, 16], width = "100%" }: { lines?: number[]; width?: string }) {
  return (
    <div className={styles.stack} style={{ width }} aria-busy="true" aria-label="در حال بارگذاری">
      {lines.map((height, i) => <div key={i} className={styles.block} style={{ height }} />)}
    </div>
  );
}

export function CardSkeletons({ count }: { count: number }) {
  return <>{Array.from({ length: count }, (_, i) => <Skeleton key={i} lines={[150, 18, 14, 14]} />)}</>;
}
