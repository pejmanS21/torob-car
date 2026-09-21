"use client";
import { useState } from "react";
import { ReauthPrompt } from "@/components/ReauthPrompt";
import { describeAudit, needsReauth } from "@/lib/admin";
import { apiGet } from "@/lib/api/client";
import type { AdminStats } from "@/lib/api/types";
import { useApi } from "@/lib/api/useApi";
import { fa } from "@/lib/format";
import styles from "./admin.module.css";

export default function AdminDashboard() {
  const stats = useApi("admin-stats", (signal) =>
    apiGet<AdminStats>("/admin/stats", {}, signal),
  );
  // A stale admin window 403s this read with no other button left to reopen
  // ReauthPrompt (spec §3.2) — surface it here so reload-and-hope isn't the
  // only recovery.
  const [reauthDismissed, setReauthDismissed] = useState(false);
  const reauth = (
    <ReauthPrompt
      open={needsReauth(stats.error) && !reauthDismissed}
      onDone={() => { setReauthDismissed(false); stats.retry(); }}
      onCancel={() => setReauthDismissed(true)}
    />
  );

  if (stats.loading) return <p className={styles.state}>در حال بارگذاری…</p>;
  if (stats.error || !stats.data) {
    return (
      <>
        <p className={styles.state}>آمار در دسترس نیست</p>
        {reauth}
      </>
    );
  }

  const tiles = [
    { label: "کاربران", value: stats.data.users_total },
    { label: "کاربران فعال", value: stats.data.users_active },
    { label: "ادمین‌های فعال", value: stats.data.admins_active },
    { label: "آگهی‌ها", value: stats.data.listings_total },
  ];

  return (
    <>
      <div className={styles.tiles}>
        {tiles.map((tile) => (
          <div key={tile.label} className={styles.tile}>
            <span className={styles.tileValue}>{fa(tile.value)}</span>
            <span className={styles.tileLabel}>{tile.label}</span>
          </div>
        ))}
      </div>
      <h2 className={styles.heading}>آخرین اقدام‌ها</h2>
      <ul className={styles.list}>
        {stats.data.recent_audit.map((row) => (
          <li key={row.id} className={styles.listRow}>{describeAudit(row)}</li>
        ))}
        {stats.data.recent_audit.length === 0 && (
          <li className={styles.listRow}>هنوز اقدامی ثبت نشده</li>
        )}
      </ul>
      {reauth}
    </>
  );
}
