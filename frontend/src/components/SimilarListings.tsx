import type { CardView } from "@/lib/view";
import { MiniListing } from "./MiniListing";
import styles from "./SimilarListings.module.css";

export function SimilarListings({ title, cards }: Readonly<{ title: string; cards: CardView[] }>) {
  if (cards.length === 0) return null;
  return (
    <div className={styles.card}>
      <div className={styles.title}>{title}</div>
      <div className={styles.list}>
        {cards.map((card) => (
          <MiniListing key={card.id} card={card} />
        ))}
      </div>
    </div>
  );
}
