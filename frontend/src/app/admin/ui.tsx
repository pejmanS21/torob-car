"use client";

import { Icon } from "@/components/Icon";
import type { AuditRow } from "@/lib/api/types";
import { describeAudit } from "@/lib/admin";
import { fa } from "@/lib/format";
import styles from "./admin.module.css";

const paths = {
  dashboard: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  users:
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 3a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
  shield: "M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11m-4-11 3 3 5-5",
  activity: "M3 3v18h18M7 14l4-4 4 3 6-7",
  car: "m5 7 2-4h10l2 4M3 8h18v10H3zM5 18v3M19 18v3M6 12h2M16 12h2",
  refresh:
    "M20 7v5h-5M4 17v-5h5M6 6a8 8 0 0 1 13 1l1 5M4 12l1 5a8 8 0 0 0 13 1",
  arrow: "M19 12H5m6-6-6 6 6 6",
  logout: "M9 21H4V3h5M10 12h11m-5-5 5 5-5 5",
  clock: "M12 8v4l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  close: "m6 6 12 12M6 18 18 6",
  check: "m5 12 4 4L19 6",
  settings: "M4 7h16M4 17h16M8 4v6M16 14v6",
} as const;
export type AdminIconName = keyof typeof paths;
export function AdminIcon({
  name,
  size = 20,
}: Readonly<{
  name: AdminIconName;
  size?: number;
}>) {
  return <Icon d={paths[name]} size={size} />;
}
export function adminDate(value: string | null, time = false) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("fa-IR", {
    dateStyle: "medium",
    ...(time ? { timeStyle: "short" as const } : {}),
    timeZone: "Asia/Tehran",
  }).format(date);
}
export function PageHeading({
  title,
  description,
  children,
}: Readonly<{
  title: string;
  description: string;
  children?: React.ReactNode;
}>) {
  return (
    <div className={styles.pageHeading}>
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className={styles.headingActions}>{children}</div>
    </div>
  );
}
export function RefreshButton({
  loading,
  onClick,
}: Readonly<{
  loading: boolean;
  onClick: () => void;
}>) {
  return (
    <button
      type="button"
      className={styles.button}
      onClick={onClick}
      disabled={loading}
    >
      <AdminIcon name="refresh" size={16} />
      به‌روزرسانی
    </button>
  );
}
export function EmptyState({
  title,
  description,
  children,
}: Readonly<{
  title: string;
  description: string;
  children?: React.ReactNode;
}>) {
  return (
    <div className={styles.empty}>
      <span className={styles.emptyIcon}>
        <AdminIcon name="users" size={26} />
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
      {children}
    </div>
  );
}
export function LoadingState() {
  return (
    <output className={styles.loading}>
      <span className={styles.spinner} />
      <span>در حال دریافت اطلاعات…</span>
    </output>
  );
}
export function Pagination({
  total,
  page,
  size,
  onChange,
}: Readonly<{
  total: number;
  page: number;
  size: number;
  onChange: (page: number) => void;
}>) {
  return (
    <div className={styles.pagination}>
      <span>
        {total
          ? `${fa(page * size + 1)} تا ${fa(Math.min((page + 1) * size, total))} از ${fa(total)} مورد`
          : "۰ مورد"}
      </span>
      <div>
        <button
          className={styles.button}
          disabled={page === 0}
          onClick={() => onChange(page - 1)}
        >
          قبلی
        </button>
        <span>
          صفحه {fa(page + 1)} از {fa(Math.max(1, Math.ceil(total / size)))}
        </span>
        <button
          className={styles.button}
          disabled={(page + 1) * size >= total}
          onClick={() => onChange(page + 1)}
        >
          بعدی
        </button>
      </div>
    </div>
  );
}
export function AuditList({ rows }: Readonly<{ rows: AuditRow[] }>) {
  if (!rows.length)
    return (
      <EmptyState
        title="هنوز فعالیتی ثبت نشده"
        description="تغییرات حساب‌های کاربری در این بخش نمایش داده می‌شوند."
      />
    );
  return (
    <ul className={styles.auditList}>
      {rows.map((row) => (
        <li key={row.id}>
          <span className={styles.auditIcon}>
            <AdminIcon
              name={row.action === "user_deleted" ? "users" : "shield"}
              size={17}
            />
          </span>
          <div>
            <p>{describeAudit(row)}</p>
            <time dateTime={row.created_at}>
              {adminDate(row.created_at, true)}
            </time>
          </div>
        </li>
      ))}
    </ul>
  );
}
