"use client";
import Link from "next/link";
import { CompareTable } from "@/components/CompareTable";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Skeleton } from "@/components/Skeleton";
import { apiGet } from "@/lib/api/client";
import type { ListingCard } from "@/lib/api/types";
import { useApi } from "@/lib/api/useApi";
import { useAppState } from "@/state/AppState";
import styles from "./page.module.css";

export default function ComparePage() {
  const { compare, removeFromCompare } = useAppState();
  const cards = useApi(compare.length ? `compare:${compare.join(",")}` : null, (signal) => apiGet<ListingCard[]>("/listings", { ids: compare }, signal));
  return (
    <section className={styles.screen}>
      <h1 className={styles.title}>مقایسه</h1>
      <p className={styles.lead}>تا سه خودرو رو از صفحهٔ آگهی به مقایسه اضافه کن.</p>
      {compare.length === 0 && (
        <div className={styles.empty}>
          هنوز چیزی برای مقایسه انتخاب نکردی.
          <div>
            <Link href="/results" className={styles.cta}>برو به آگهی‌ها</Link>
          </div>
        </div>
      )}
      {cards.loading && <Skeleton lines={[120, 40, 40, 40]} />}
      {cards.error && <ErrorBanner error={cards.error} onRetry={cards.retry} />}
      {(cards.data?.length ?? 0) > 0 && <CompareTable cards={cards.data ?? []} onRemove={removeFromCompare} />}
      {cards.data?.length === 0 && <div className={styles.empty}>این آگهی‌ها دیگر فعال نیستند.</div>}
    </section>
  );
}
