"use client";
import { useCallback, useState } from "react";
import { ReauthPrompt } from "@/components/ReauthPrompt";
import { MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH } from "@/lib/account";
import { ADMIN_ERROR_TEXT, needsReauth } from "@/lib/admin";
import { ApiError, apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api/client";
import type { AdminPasswordReset, AdminUserPage, AdminUserUpdate, UserRole } from "@/lib/api/types";
import { useApi } from "@/lib/api/useApi";
import { fa } from "@/lib/format";
import { useAppState } from "@/state/AppState";
import styles from "../admin.module.css";

export default function AdminUsers() {
  const { user: currentUser } = useAppState();
  const [term, setTerm] = useState("");
  const [appliedTerm, setAppliedTerm] = useState("");
  const [notice, setNotice] = useState({ text: "", ok: false });
  const [pending, setPending] = useState<{ action: () => Promise<void>; message: string } | null>(null);
  const [resetFor, setResetFor] = useState<string | null>(null);
  const [resetValue, setResetValue] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  // Same escape hatch as the dashboard (F1): a stale admin window 403s this read
  // with no mutation button left to open ReauthPrompt, so surface it here too.
  const [readReauthDismissed, setReadReauthDismissed] = useState(false);

  // Same fetch-on-mount / refetch-on-key-change shape as ResultsScreen: no
  // raw effect calling setState, `retry()` reloads after a mutation.
  const users = useApi(`admin-users:${appliedTerm}`, (signal) =>
    apiGet<AdminUserPage>("/admin/users", { term: appliedTerm || undefined }, signal),
  );

  /** Runs an action; on `admin_reauth_required` parks it for the prompt to retry.
   *  `successMessage` (empty by default, matching the toggle/promote actions that
   *  show nothing) is shown on success and carried along when parked for reauth. */
  const guarded = useCallback(async (action: () => Promise<void>, successMessage = "") => {
    try {
      await action();
      setNotice({ text: successMessage, ok: true });
    } catch (error) {
      if (needsReauth(error)) { setPending({ action, message: successMessage }); return; }
      setNotice({
        text: error instanceof ApiError
          ? ADMIN_ERROR_TEXT[error.code] ?? error.message
          : "انجام نشد",
        ok: false,
      });
    }
  }, []);

  const update = (id: string, patch: AdminUserUpdate) =>
    guarded(async () => {
      await apiPatch(`/admin/users/${id}`, patch);
      users.retry();
    });

  const resetPassword = (id: string) => {
    // replace_password bumps token_version, so an admin resetting their own
    // password signs themselves out. That IS correct — only say so (F6).
    const successMessage =
      currentUser?.id === id ? "رمز بازنشانی شد؛ باید دوباره وارد شوی" : "رمز بازنشانی شد";
    return guarded(async () => {
      const body: AdminPasswordReset = { new: resetValue };
      await apiPost(`/admin/users/${id}/password`, body);
      setResetFor(null);
      setResetValue("");
    }, successMessage);
  };

  const deleteUser = (id: string) =>
    guarded(async () => {
      await apiDelete(`/admin/users/${id}`);
      setConfirmDelete(null);
      users.retry();
    }, "کاربر حذف شد");

  return (
    <>
      <form className={styles.search}
        onSubmit={(event) => { event.preventDefault(); setAppliedTerm(term); }}>
        <input value={term} onChange={(event) => setTerm(event.target.value)}
          placeholder="جست‌وجوی ایمیل" dir="ltr" />
        <button type="submit">جست‌وجو</button>
      </form>
      {notice.text && (
        <p className={notice.ok ? styles.success : styles.error} role="alert">{notice.text}</p>
      )}
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
                {resetFor === row.id ? (
                  <form className={styles.inlineReset}
                    onSubmit={(event) => { event.preventDefault(); void resetPassword(row.id); }}>
                    <input type="password" value={resetValue} dir="ltr" required
                      minLength={MIN_PASSWORD_LENGTH} maxLength={MAX_PASSWORD_LENGTH}
                      autoComplete="new-password" aria-label="رمز جدید"
                      onChange={(event) => setResetValue(event.target.value)} />
                    <button type="submit">تأیید</button>
                  </form>
                ) : (
                  <button type="button"
                    onClick={() => { setResetFor(row.id); setResetValue(""); }}>
                    بازنشانی رمز
                  </button>
                )}
                {confirmDelete === row.id ? (
                  <>
                    <button type="button" onClick={() => void deleteUser(row.id)}>تأیید حذف</button>
                    <button type="button" onClick={() => setConfirmDelete(null)}>انصراف</button>
                  </>
                ) : (
                  <button type="button" onClick={() => setConfirmDelete(row.id)}>حذف</button>
                )}
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
          if (retry) void guarded(retry.action, retry.message);
        }}
      />
      <ReauthPrompt
        open={needsReauth(users.error) && !readReauthDismissed}
        onCancel={() => setReadReauthDismissed(true)}
        onDone={() => { setReadReauthDismissed(false); users.retry(); }}
      />
    </>
  );
}
