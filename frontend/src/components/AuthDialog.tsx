"use client";
import { useEffect, useRef, useState } from "react";
import { AUTH_ERROR_TEXT, MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH } from "@/lib/account";
import { ApiError } from "@/lib/api/client";
import { useAppState } from "@/state/AppState";
import { errorText, SERVICE_UNAVAILABLE } from "./ErrorBanner";
import styles from "./AuthDialog.module.css";

type Mode = "login" | "register";
const TABS: { mode: Mode; label: string }[] = [{ mode: "login", label: "ورود" }, { mode: "register", label: "ثبت‌نام" }];

/** Branches on `ApiError.code`; a 422 shows the backend's own message, the rest the shared banner copy. */
const messageFor = (error: unknown): string =>
  error instanceof ApiError ? AUTH_ERROR_TEXT[error.code] ?? errorText(error) : SERVICE_UNAVAILABLE;

export function AuthDialog() {
  const { authOpen, closeAuth, login, register } = useAppState();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [mode, setMode] = useState<Mode>("login");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Native <dialog>: showModal() brings the focus trap, Escape and the backdrop for free.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (authOpen && !dialog.open) dialog.showModal();
    if (!authOpen && dialog.open) dialog.close();
  }, [authOpen]);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget; // gone after the first await
    const data = new FormData(form);
    setBusy(true);
    setError("");
    try {
      await (mode === "login" ? login : register)(String(data.get("email")), String(data.get("password")));
      form.reset();
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "email_taken") setMode("login");
      setError(messageFor(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <dialog ref={dialogRef} className={styles.dialog} onClose={closeAuth} aria-labelledby="auth-title">
      <div className={styles.head}>
        <h2 id="auth-title" className={styles.title}>حساب کاربری</h2>
        <button type="button" className={styles.close} onClick={closeAuth} aria-label="بستن">×</button>
      </div>
      <div className={styles.tabs} role="tablist">
        {TABS.map((tab) => (
          <button key={tab.mode} type="button" role="tab" aria-selected={mode === tab.mode}
            className={`${styles.tab} ${mode === tab.mode ? styles.tabActive : ""}`}
            onClick={() => { setMode(tab.mode); setError(""); }}>{tab.label}</button>
        ))}
      </div>
      <form className={styles.form} onSubmit={submit}>
        <label className={styles.field}>ایمیل
          <input name="email" type="email" required autoComplete="email" dir="ltr" />
        </label>
        <label className={styles.field}>رمز عبور
          <input name="password" type="password" required dir="ltr"
            minLength={mode === "register" ? MIN_PASSWORD_LENGTH : undefined} maxLength={MAX_PASSWORD_LENGTH}
            autoComplete={mode === "register" ? "new-password" : "current-password"} />
        </label>
        {error && <p className={styles.error} role="alert">{error}</p>}
        <button type="submit" className={styles.submit} disabled={busy}>{mode === "login" ? "ورود" : "ساخت حساب"}</button>
      </form>
    </dialog>
  );
}
