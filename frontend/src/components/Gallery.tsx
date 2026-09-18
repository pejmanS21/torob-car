"use client";

import { useState } from "react";
import { fa } from "@/lib/format";
import styles from "./Gallery.module.css";

export function Gallery({ photos, title }: { photos: string[]; title: string }) {
  const [selected, setSelected] = useState(0);

  return (
    <>
      <div className={styles.heroWrap}>
        <div role="img" aria-label={title} className={styles.hero} style={{ backgroundImage: `url(${photos[selected]})` }} />
        <span className={styles.badge}>{fa(photos.length)} عکس</span>
      </div>
      <div className={styles.thumbs}>
        {photos.map((photo, i) => (
          <button
            key={i}
            type="button"
            aria-label={`عکس ${fa(i + 1)}`}
            aria-pressed={i === selected}
            className={styles.thumb}
            style={{ backgroundImage: `url(${photo})`, borderColor: i === selected ? "var(--red)" : "transparent", opacity: i === selected ? 1 : 0.75 }}
            onClick={() => setSelected(i)}
          />
        ))}
      </div>
    </>
  );
}
