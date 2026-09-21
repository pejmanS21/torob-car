"use client";
import { useEffect, useRef, useState } from "react";
import { SERVICE_UNAVAILABLE } from "@/components/ErrorBanner";
import { MAX_PASSWORD_LENGTH } from "@/lib/account";
import { ADMIN_ERROR_TEXT } from "@/lib/admin";
import { ApiError, apiPost } from "@/lib/api/client";
import styles from "./ReauthPrompt.module.css";

/** Shown when the API answers `admin_reauth_required`. On success the caller retries
 *  its action once; the admin is never signed out, only asked to prove presence. */
export function ReauthPrompt({ open, onDone, onCancel }: Readonly<{
  open: boolean;
  onDone: () => void;
  onCancel: () => void;
}>) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const submit = async (event: React.SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await apiPost("/auth/reauth", { password: data.get("password") as string });
      onDone();
    } catch (error_) {
      setError(
        error_ instanceof ApiError
          ? ADMIN_ERROR_TEXT[error_.code] ?? "رمز اشتباه است"
          : SERVICE_UNAVAILABLE,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <dialog ref={dialogRef} className={styles.dialog} onClose={onCancel}>
      <form className={styles.form} onSubmit={submit}>
        <p className={styles.lead}>{ADMIN_ERROR_TEXT.admin_reauth_required}</p>
        <input name="password" type="password" required dir="ltr"
          maxLength={MAX_PASSWORD_LENGTH} autoComplete="current-password" />
        {error && <p className={styles.error} role="alert">{error}</p>}
        <div className={styles.actions}>
          <button type="button" onClick={onCancel} className={styles.cancel}>انصراف</button>
          <button type="submit" disabled={busy} className={styles.submit}>تأیید</button>
        </div>
      </form>
    </dialog>
  );
}
