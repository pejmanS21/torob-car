"use client";
import Link from "next/link";
import { useState } from "react";
import { ReauthPrompt } from "@/components/ReauthPrompt";
import { needsReauth } from "@/lib/admin";
import { apiGet } from "@/lib/api/client";
import type { AdminStats } from "@/lib/api/types";
import { useApi } from "@/lib/api/useApi";
import { num } from "@/lib/format";
import {
  AdminIcon,
  type AdminIconName,
  adminDate,
  AuditList,
  LoadingState,
  PageHeading,
  RefreshButton,
} from "./ui";
import styles from "./admin.module.css";

export default function AdminDashboard() {
  const stats = useApi("admin-stats", (signal) =>
    apiGet<AdminStats>("/admin/stats", {}, signal),
  );
  const [reauthDismissed, setReauthDismissed] = useState(false);
  const data = stats.data;
  const tiles: {
    label: string;
    value: number;
    detail: string;
    icon: AdminIconName;
    tone: string;
  }[] = data
    ? [
        {
          label: "کل کاربران",
          value: data.users_total,
          detail: "حساب‌های ثبت‌شده در سامانه",
          icon: "users",
          tone: "red",
        },
        {
          label: "کاربران فعال",
          value: data.users_active,
          detail: "حساب‌های دارای دسترسی فعال",
          icon: "check",
          tone: "green",
        },
        {
          label: "مدیران فعال",
          value: data.admins_active,
          detail: "دارای دسترسی به پنل مدیریت",
          icon: "shield",
          tone: "blue",
        },
        {
          label: "آگهی‌های خودرو",
          value: data.listings_total,
          detail: "کل آگهی‌های موجود در سامانه",
          icon: "car",
          tone: "amber",
        },
      ]
    : [];
  return (
    <>
      <PageHeading
        title="نمای کلی"
        description="وضعیت سامانه و آخرین فعالیت‌های مدیریتی در یک نگاه."
      >
        <RefreshButton loading={stats.loading} onClick={stats.retry} />
      </PageHeading>
      {stats.loading && <LoadingState />}
      {stats.error && (
        <div className={styles.error} role="alert">
          <span>دریافت آمار انجام نشد. دوباره تلاش کنید.</span>
          <button
            className={styles.button}
            onClick={() => {
              setReauthDismissed(false);
              stats.retry();
            }}
          >
            تلاش دوباره
          </button>
        </div>
      )}
      {data && (
        <>
          <div className={styles.tiles}>
            {tiles.map((tile) => (
              <article key={tile.label} className={styles.tile}>
                <div className={styles.tileTop}>
                  <span>{tile.label}</span>
                  <span className={styles.metricIcon} data-tone={tile.tone}>
                    <AdminIcon name={tile.icon} />
                  </span>
                </div>
                <strong className={styles.tileValue}>{num(tile.value)}</strong>
                <span className={styles.tileDetail}>{tile.detail}</span>
              </article>
            ))}
          </div>
          <div className={styles.dashboardGrid}>
            <section className={styles.panel}>
              <div className={styles.panelHeading}>
                <div>
                  <h2>آخرین فعالیت‌ها</h2>
                  <p>تغییرات اخیر مدیران در سامانه</p>
                </div>
                <Link href="/admin/audit" className={styles.textLink}>
                  مشاهده همه <AdminIcon name="arrow" size={15} />
                </Link>
              </div>
              <AuditList rows={data.recent_audit} />
            </section>
            <div className={styles.sideCards}>
              <section className={styles.panel}>
                <div className={styles.panelHeading}>
                  <h2>وضعیت حساب‌ها</h2>
                  <AdminIcon name="users" />
                </div>
                <div className={styles.accountSummary}>
                  <div>
                    <span>حساب‌های فعال</span>
                    <strong>
                      {num(data.users_active)}{" "}
                      <small>از {num(data.users_total)}</small>
                    </strong>
                  </div>
                  <div
                    className={styles.progress}
                    role="img"
                    aria-label={`${num(data.users_active)} حساب فعال از ${num(data.users_total)} حساب`}
                  >
                    <span
                      style={{
                        width: `${data.users_total ? (data.users_active / data.users_total) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <div className={styles.legend}>
                    <span>
                      <i />
                      <span>فعال</span>
                    </span>
                    <span>
                      غیرفعال: {num(data.users_total - data.users_active)}
                    </span>
                  </div>
                  <Link href="/admin/users" className={styles.button}>
                    مدیریت کاربران
                    <AdminIcon name="arrow" size={16} />
                  </Link>
                </div>
              </section>
              <section className={styles.freshness}>
                <span className={styles.metricIcon} data-tone="blue">
                  <AdminIcon name="clock" />
                </span>
                <h2>آخرین دریافت آگهی</h2>
                <p>
                  {data.newest_listing_fetched_at
                    ? adminDate(data.newest_listing_fetched_at, true)
                    : "هنوز آگهی‌ای دریافت نشده است"}
                </p>
                <small>زمان آخرین دریافت داده از منابع آگهی</small>
              </section>
            </div>
          </div>
        </>
      )}
      <ReauthPrompt
        open={needsReauth(stats.error) && !reauthDismissed}
        onDone={() => {
          setReauthDismissed(false);
          stats.retry();
        }}
        onCancel={() => setReauthDismissed(true)}
      />
    </>
  );
}
