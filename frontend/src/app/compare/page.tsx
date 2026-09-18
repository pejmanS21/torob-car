"use client";
import Link from "next/link";
import { CompareTable } from "@/components/CompareTable";
import { findListing } from "@/lib/listings";
import type { Listing } from "@/lib/types";
import { useAppState } from "@/state/AppState";
import styles from "./page.module.css";

export default function ComparePage() {
  const { compare, removeFromCompare } = useAppState();
  const cars = compare.map(findListing).filter((l): l is Listing => l !== undefined);
  return (
    <section className={styles.screen}>
      <h1 className={styles.title}>مقایسه</h1>
      <p className={styles.lead}>تا سه خودرو رو از صفحهٔ آگهی به مقایسه اضافه کن.</p>
      {cars.length === 0 ? (
        <div className={styles.empty}>
          هنوز چیزی برای مقایسه انتخاب نکردی.
          <div>
            <Link href="/results" className={styles.cta}>برو به آگهی‌ها</Link>
          </div>
        </div>
      ) : (
        <CompareTable cars={cars} onRemove={removeFromCompare} />
      )}
    </section>
  );
}
