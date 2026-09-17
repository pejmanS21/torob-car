"use client";

import { useMemo } from "react";
import { num } from "@/lib/format";
import { LISTINGS } from "@/lib/listings";
import { ALERT_FRACTION_OF_MEDIAN, modelStats } from "@/lib/modelStats";
import { cardOf } from "@/lib/view";
import { useAppState } from "@/state/AppState";
import { Breadcrumbs } from "./Breadcrumbs";
import { Icon } from "./Icon";
import { IssueBars } from "./IssueBars";
import { ListingRow } from "./ListingRow";
import { MapCard } from "./MapCard";
import { PriceHistogram } from "./PriceHistogram";
import styles from "./ModelScreen.module.css";

export function ModelScreen({ modelId }: { modelId: string }) {
  const { addAlert } = useAppState();
  const stats = useMemo(() => modelStats(modelId, LISTINGS), [modelId]);
  const saveAlert = () =>
    addAlert({
      title: stats.model.name,
      threshold: stats.alertThreshold,
      matches: stats.listings.filter((l) => l.price < stats.median * ALERT_FRACTION_OF_MEDIAN).length,
    });

  return (
    <section className={styles.screen}>
      <Breadcrumbs items={[{ label: "خانه", href: "/" }, { label: "جست‌وجو", href: "/results" }, { label: stats.model.name }]} />
      <div className={styles.head}>
        <div>
          <h1 className={styles.name}>{stats.model.name}</h1>
          <div className={styles.sub}>
            {stats.countFa} آگهی فعال · سال‌های {stats.yearRange} · میانهٔ قیمت <b>{num(stats.median)}</b> میلیون
          </div>
        </div>
        <button className={styles.alert} onClick={saveAlert}>
          <Icon name="bell" size={16} />
          هشدار قیمت زیر {num(stats.alertThreshold)} میلیون
        </button>
      </div>
      <div className={styles.topGrid}>
        <PriceHistogram buckets={stats.buckets} minFa={num(stats.min)} maxFa={num(stats.max)} />
        <IssueBars issues={stats.issues} />
      </div>
      <div className={styles.bottomGrid}>
        <div>
          <div className={styles.listHead}>
            <h2>آگهی‌ها به ترتیب ارزش خرید</h2>
            <span>قیمت نسبت به بازار + کارکرد + بدنه</span>
          </div>
          <div className={styles.rows}>
            {stats.listings.map((l) => (
              <ListingRow key={l.id} card={cardOf(l)} />
            ))}
          </div>
        </div>
        <MapCard sticky title="آگهی‌ها روی نقشه" hint="رنگ نقطه = قیمت نسبت به بازار · کلیک = آگهی" listings={stats.listings} />
      </div>
    </section>
  );
}
