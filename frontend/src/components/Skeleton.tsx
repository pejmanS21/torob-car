import styles from "./Skeleton.module.css";

/** Pulsing placeholder blocks; `lines` rows of the given heights (px). */
export function Skeleton({ lines = [24, 16, 16], width = "100%" }: Readonly<{ lines?: number[]; width?: string }>) {
  const occurrences = new Map<number, number>();
  const rows = lines.map((height) => {
    const occurrence = (occurrences.get(height) ?? 0) + 1;
    occurrences.set(height, occurrence);
    return { height, id: `${height}:${occurrence}` };
  });
  return (
    <div className={styles.stack} style={{ width }} aria-busy="true" aria-label="در حال بارگذاری">
      {rows.map(({ height, id }) => <div key={id} className={styles.block} style={{ height }} />)}
    </div>
  );
}

export function CardSkeletons({ count }: Readonly<{ count: number }>) {
  const cards = Array.from({ length: count }, (_, position) => `card:${position}`);
  return <>{cards.map((id) => <Skeleton key={id} lines={[150, 18, 14, 14]} />)}</>;
}
