"use client";
import { useState } from "react";
import { ReauthPrompt } from "@/components/ReauthPrompt";
import { needsReauth } from "@/lib/admin";
import { apiGet } from "@/lib/api/client";
import type { AuditPage } from "@/lib/api/types";
import { useApi } from "@/lib/api/useApi";
import { fa } from "@/lib/format";
import {
  AuditList,
  EmptyState,
  LoadingState,
  PageHeading,
  Pagination,
  RefreshButton,
} from "../ui";
import styles from "../admin.module.css";

const PAGE_SIZE = 20;
export default function AdminAudit() {
  const [action, setAction] = useState("");
  const [page, setPage] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const audit = useApi(`admin-audit:${action}:${page}`, (signal) =>
    apiGet<AuditPage>(
      "/admin/audit",
      {
        action: action || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      },
      signal,
    ),
  );
  function renderAudit() {
    if (audit.loading) return (
          <LoadingState />
        );
    if (audit.error) return (
          <EmptyState
            title="گزارش در دسترس نیست"
            description="برای دریافت فعالیت‌ها دوباره تلاش کنید."
          >
            <button
              className={styles.button}
              onClick={() => {
                setDismissed(false);
                audit.retry();
              }}
            >
              تلاش دوباره
            </button>
          </EmptyState>
        );
    return (
          <AuditList rows={audit.data?.items ?? []} />
        );
  }
  return (
    <>
      <PageHeading
        title="گزارش فعالیت‌ها"
        description="تاریخچه تغییرات مدیریتی؛ چه کسی، چه تغییری و در چه زمانی انجام داده است."
      >
        <RefreshButton loading={audit.loading} onClick={audit.retry} />
      </PageHeading>
      <section className={styles.panel}>
        <div className={styles.panelHeading}>
          <div className={styles.inlineHeading}>
            <h2>فعالیت‌های ثبت‌شده</h2>
            {audit.data && (
              <span className={styles.countBadge}>
                {fa(audit.data.total)} رویداد
              </span>
            )}
          </div>
          <label className={styles.filterLabel}>
            <span>نوع فعالیت</span>
            <select
              value={action}
              onChange={(event) => {
                setAction(event.target.value);
                setPage(0);
              }}
            >
              <option value="">همه فعالیت‌ها</option>
              <option value="user_enabled">فعال‌سازی حساب</option>
              <option value="user_disabled">غیرفعال‌سازی حساب</option>
              <option value="user_promoted">ارتقا به مدیر</option>
              <option value="user_demoted">تغییر نقش به کاربر</option>
              <option value="user_password_reset">بازنشانی رمز</option>
              <option value="user_deleted">حذف حساب</option>
            </select>
          </label>
        </div>
        {renderAudit()}
        {audit.data && (
          <Pagination
            total={audit.data.total}
            page={page}
            size={PAGE_SIZE}
            onChange={setPage}
          />
        )}
      </section>
      <ReauthPrompt
        open={needsReauth(audit.error) && !dismissed}
        onCancel={() => setDismissed(true)}
        onDone={() => {
          setDismissed(false);
          audit.retry();
        }}
      />
    </>
  );
}
