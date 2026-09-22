"use client";

import dynamic from "next/dynamic";
import type { ListingCard } from "@/lib/api/types";
import styles from "./MapCard.module.css";

const ListingsMap = dynamic(() => import("./ListingsMap"), { ssr: false });

interface Props { title: string; hint: string; listings: ListingCard[]; single?: boolean; sticky?: boolean; }

export function MapCard({ title, hint, listings, single = false, sticky = false }: Readonly<Props>) {
  return (
    <div className={`${styles.card} ${sticky ? styles.sticky : styles.fixed}`}>
      <div className={styles.head}><span className={styles.title}>{title}</span><span className={styles.hint}>{hint}</span></div>
      <div className={styles.map}><ListingsMap listings={listings} single={single} /></div>
    </div>
  );
}
