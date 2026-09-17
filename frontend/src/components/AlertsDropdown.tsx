"use client";
import { fa, num } from "@/lib/format";
import { useAppState } from "@/state/AppState";
import { Icon } from "./Icon";
import styles from "./AlertsDropdown.module.css";

export function AlertsDropdown() {
  const { alerts, loggedIn, removeAlert, toggleLogin } = useAppState();

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
            <div className={styles.meta}>{`قیمت کمتر از ${num(a.threshold)} میلیون · الان ${fa(a.matches)} آگهی زیر این قیمت`}</div>
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
