"use client";
import { apiGet } from "@/lib/api/client";
import type { SearchResponse } from "@/lib/api/types";
import { useApi } from "@/lib/api/useApi";
import { fa, formatToman } from "@/lib/format";
import type { PriceAlert } from "@/lib/types";
import { useAppState } from "@/state/AppState";
import { Icon } from "./Icon";
import styles from "./AlertsDropdown.module.css";

/** One /search per alert, capped at the threshold, page_size 1 → `total` is the live match count. */
const countMatches = (alert: PriceAlert, signal: AbortSignal): Promise<number> =>
  apiGet<SearchResponse>("/search", { ...alert.params, price_max: alert.threshold, page_size: 1 }, signal).then((r) => r.total);

function matchText(count: number | undefined, loading: boolean, failed: boolean): string {
  if (loading) return "در حال شمارش…";
  if (failed || count === undefined) return "شمارش در دسترس نیست";
  return `الان ${fa(count)} آگهی زیر این قیمت`;
}

export function AlertsDropdown() {
  const { alerts, loggedIn, removeAlert, toggleLogin } = useAppState();
  // Fetched live every time the dropdown opens (this component mounts on open).
  const counts = useApi(alerts.length ? JSON.stringify(alerts) : null, (signal) => Promise.all(alerts.map((a) => countMatches(a, signal))));

  return (
    <div className={styles.panel}>
      <div className={styles.head}>
        هشدارهای قیمت
        {loggedIn && <span className={styles.count}>{`${fa(alerts.length)} فعال`}</span>}
      </div>

      {!loggedIn && (
        <div className={styles.empty}>
          برای ذخیره جست‌وجو و گرفتن هشدار قیمت، اول وارد شو.
          <div className={styles.loginWrap}>
            <button className={styles.loginButton} onClick={toggleLogin}>ورود</button>
          </div>
        </div>
      )}

      {loggedIn && alerts.map((a, i) => (
        <div key={i} className={styles.row}>
          <div className={styles.icon}>
            <Icon name="trendDown" stroke="#d9232e" />
          </div>
          <div className={styles.text}>
            <div className={styles.title}>{a.title}</div>
            <div className={styles.meta}>{`قیمت کمتر از ${formatToman(a.threshold)} · ${matchText(counts.data?.[i], counts.loading, counts.error !== null)}`}</div>
          </div>
          <button className={styles.remove} onClick={() => removeAlert(i)} title="حذف">×</button>
        </div>
      ))}

      {loggedIn && alerts.length === 0 && (
        <div className={styles.empty}>هنوز هشداری نداری. توی نتایج جست‌وجو «ذخیره و هشدار» رو بزن.</div>
      )}
    </div>
  );
}
