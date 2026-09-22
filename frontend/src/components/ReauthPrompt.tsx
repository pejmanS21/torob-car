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
  const formRef = useRef<HTMLFormElement>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  // Drop whatever was typed so the next open always demands a fresh password
  // (P1-a). `open` only ever becomes false as a direct result of one of these
  // two handlers running (never from outside), so resetting here — instead of
  // in an effect reacting to `open` — covers every close path without a
  // setState-in-effect.
  const resetForm = () => { formRef.current?.reset(); setError(""); };
  const cancel = () => { resetForm(); onCancel(); };

  const submit = async (event: React.SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await apiPost("/auth/reauth", { password: data.get("password") as string });
      resetForm(); // clear before onDone in case the caller keeps `open` true
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
    <dialog ref={dialogRef} className={styles.dialog} onClose={cancel}>
      <form ref={formRef} className={styles.form} onSubmit={submit}>
        <p className={styles.lead}>{ADMIN_ERROR_TEXT.admin_reauth_required}</p>
        <input name="password" type="password" required dir="ltr"
          maxLength={MAX_PASSWORD_LENGTH} autoComplete="current-password" />
        {error && <p className={styles.error} role="alert">{error}</p>}
        <div className={styles.actions}>
          <button type="button" onClick={cancel} className={styles.cancel}>انصراف</button>
          <button type="submit" disabled={busy} className={styles.submit}>تأیید</button>
        </div>
      </form>
    </dialog>
  );
}
