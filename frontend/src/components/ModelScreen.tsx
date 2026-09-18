"use client";

import type { ModelStats } from "@/lib/api/types";
import { fa, formatToman } from "@/lib/format";
import { cardOf } from "@/lib/view";
import { useAppState } from "@/state/AppState";
import { Breadcrumbs } from "./Breadcrumbs";
import { Icon } from "./Icon";
import { ListingRow } from "./ListingRow";
import { MapCard } from "./MapCard";
import { PriceHistogram } from "./PriceHistogram";
import { TrimBars } from "./TrimBars";
import styles from "./ModelScreen.module.css";

export const ALERT_FRACTION_OF_MEDIAN = 0.9;
const ALERT_ROUNDING = 10_000_000;

export function ModelScreen({ stats }: { stats: ModelStats }) {
  const { addAlert } = useAppState();
  const threshold = stats.price_median === null ? null : Math.round((stats.price_median * ALERT_FRACTION_OF_MEDIAN) / ALERT_ROUNDING) * ALERT_ROUNDING;
  const saveAlert = () => threshold && addAlert({ title: stats.model, params: { models: [stats.model], category: stats.category }, threshold });
  const years = stats.year_min === null || stats.year_max === null ? "نامشخص" : `${fa(stats.year_min)} تا ${fa(stats.year_max)}`;

  return (
    <section className={styles.screen}>
      <Breadcrumbs items={[{ label: "خانه", href: "/" }, { label: "جست‌وجو", href: `/results?category=${stats.category}` }, { label: stats.model }]} />
      <div className={styles.head}>
        <div>
          <h1 className={styles.name}>{stats.model}</h1>
          <div className={styles.sub}>
            {fa(stats.count)} آگهی فعال · سال‌های {years} · میانهٔ قیمت <b>{stats.price_median === null ? "—" : formatToman(stats.price_median)}</b>
          </div>
        </div>
        {threshold !== null && (
          <button className={styles.alert} onClick={saveAlert}>
            <Icon name="bell" size={16} />
            هشدار قیمت زیر {formatToman(threshold)}
          </button>
        )}
      </div>
      <div className={styles.topGrid}>
        <PriceHistogram buckets={stats.histogram} median={stats.price_median} />
        <TrimBars trims={stats.trims} total={stats.count} />
      </div>
      <div className={styles.bottomGrid}>
        <div>
          <div className={styles.listHead}>
            <h2>بهترین آگهی‌ها به ترتیب ارزش خرید</h2>
            <span>قیمت نسبت به بازار + کارکرد + بدنه</span>
          </div>
          <div className={styles.rows}>
            {stats.top_deals.map((l) => <ListingRow key={l.id} card={cardOf(l)} />)}
            {stats.top_deals.length === 0 && <div className={styles.sub}>برای این مدل هنوز تخمین قیمتی نداریم.</div>}
          </div>
        </div>
        {stats.top_deals.some((l) => l.lat !== null) && (
          <MapCard sticky title="آگهی‌ها روی نقشه" hint="رنگ نقطه = قیمت نسبت به بازار · کلیک = آگهی" listings={stats.top_deals} />
        )}
      </div>
    </section>
  );
}
