"use client";
import { useCallback, useState } from "react";
import { ReauthPrompt } from "@/components/ReauthPrompt";
import { ADMIN_ERROR_TEXT, needsReauth } from "@/lib/admin";
import { ApiError, apiGet, apiPatch } from "@/lib/api/client";
import type { AdminUserPage, AdminUserUpdate, UserRole } from "@/lib/api/types";
import { useApi } from "@/lib/api/useApi";
import { fa } from "@/lib/format";
import styles from "../admin.module.css";

export default function AdminUsers() {
  const [term, setTerm] = useState("");
  const [appliedTerm, setAppliedTerm] = useState("");
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState<(() => Promise<void>) | null>(null);

  // Same fetch-on-mount / refetch-on-key-change shape as ResultsScreen: no
  // raw effect calling setState, `retry()` reloads after a mutation.
  const users = useApi(`admin-users:${appliedTerm}`, (signal) =>
    apiGet<AdminUserPage>("/admin/users", { term: appliedTerm || undefined }, signal),
  );

  /** Runs an action; on `admin_reauth_required` parks it for the prompt to retry. */
  const guarded = useCallback(async (action: () => Promise<void>) => {
    try {
      await action();
      setNotice("");
    } catch (error) {
      if (needsReauth(error)) { setPending(() => action); return; }
      setNotice(
        error instanceof ApiError
          ? ADMIN_ERROR_TEXT[error.code] ?? error.message
          : "انجام نشد",
      );
    }
  }, []);

  const update = (id: string, patch: AdminUserUpdate) =>
    guarded(async () => {
      await apiPatch(`/admin/users/${id}`, patch);
      users.retry();
    });

  return (
    <>
      <form className={styles.search}
        onSubmit={(event) => { event.preventDefault(); setAppliedTerm(term); }}>
        <input value={term} onChange={(event) => setTerm(event.target.value)}
          placeholder="جست‌وجوی ایمیل" dir="ltr" />
        <button type="submit">جست‌وجو</button>
      </form>
      {notice && <p className={styles.error} role="alert">{notice}</p>}
      {users.error && <p className={styles.error} role="alert">کاربران در دسترس نیست</p>}
      <table className={styles.table}>
        <thead>
          <tr><th>ایمیل</th><th>نقش</th><th>وضعیت</th><th>اقدام</th></tr>
        </thead>
        <tbody>
          {(users.data?.items ?? []).map((row) => (
            <tr key={row.id}>
              <td dir="ltr">{row.email}</td>
              <td>{row.role === "admin" ? "ادمین" : "کاربر"}</td>
              <td>{row.is_active ? "فعال" : "غیرفعال"}</td>
              <td className={styles.rowActions}>
                <button type="button"
                  onClick={() => void update(row.id, { is_active: !row.is_active })}>
                  {row.is_active ? "غیرفعال" : "فعال"}
                </button>
                <button type="button"
                  onClick={() => void update(row.id, {
                    role: (row.role === "admin" ? "user" : "admin") as UserRole,
                  })}>
                  {row.role === "admin" ? "حذف ادمینی" : "ادمین کن"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {users.data && <p className={styles.total}>{`${fa(users.data.total)} کاربر`}</p>}
      <ReauthPrompt
        open={pending !== null}
        onCancel={() => setPending(null)}
        onDone={() => {
          const retry = pending;
          setPending(null);
          if (retry) void guarded(retry);
        }}
      />
    </>
  );
}
