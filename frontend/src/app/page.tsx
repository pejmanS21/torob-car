import Link from "next/link";
import { connection } from "next/server";
import { HomeSearch } from "@/components/HomeSearch";
import { apiGet } from "@/lib/api/client";
import type { Facets } from "@/lib/api/types";
import { fa, relativeTime } from "@/lib/format";
import { CATEGORY_NAMES, CATEGORY_ORDER } from "@/lib/labels";
import styles from "./page.module.css";

// Server Component: fetched on every request inside the Compose network; a failure
// renders app/error.tsx («سرویس جست‌وجو در دسترس نیست»), never made-up numbers.
export default async function HomePage() {
  await connection(); // Next 16 would otherwise prerender this page (and call the API) at build time
  const facets = await apiGet<Facets>("/facets");
  const total = Object.values(facets.categories).reduce((sum, count) => sum + (count ?? 0), 0);
  const updated = facets.data_as_of ? relativeTime(facets.data_as_of, new Date()) : "نامشخص";
  return (
    <section className={styles.home}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/logo.png" alt="" className={styles.logo} />
      <h1 className={styles.title}>ماشین می‌خوای؟ فقط بگو چی.</h1>
      <HomeSearch />
      <div className={styles.stats}>
        <span><b className={styles.statNum}>{fa(total.toLocaleString("en-US"))}</b> آگهی فعال</span>
        <span><b className={styles.statNum}>{fa(facets.model_count)}</b> مدل</span>
        <span>به‌روزرسانی: <b className={styles.statNum} suppressHydrationWarning>{updated}</b></span>
      </div>
      <nav className={styles.categories} aria-label="دسته‌ها">
        {CATEGORY_ORDER.filter((category) => facets.categories[category]).map((category) => (
          <Link key={category} href={`/results?category=${category}`} className={styles.category}>
            {CATEGORY_NAMES[category]} <b>{fa((facets.categories[category] ?? 0).toLocaleString("en-US"))}</b>
          </Link>
        ))}
      </nav>
    </section>
  );
}
