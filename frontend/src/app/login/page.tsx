"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { errorText, SERVICE_UNAVAILABLE } from "@/components/ErrorBanner";
import { AUTH_ERROR_TEXT, MAX_PASSWORD_LENGTH } from "@/lib/account";
import { safeNext } from "@/lib/admin";
import { ApiError } from "@/lib/api/client";
import { useAppState } from "@/state/AppState";
import styles from "./login.module.css";

const messageFor = (error: unknown): string =>
  error instanceof ApiError
    ? AUTH_ERROR_TEXT[error.code] ?? errorText(error)
    : SERVICE_UNAVAILABLE;

function LoginForm() {
  const { user, authReady, login } = useAppState();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (authReady && user) router.replace(next);
  }, [authReady, user, next, router]);

  const submit = async (event: React.SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await login(data.get("email") as string, data.get("password") as string);
      router.replace(next);
    } catch (error_) {
      setError(messageFor(error_));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className={styles.form} onSubmit={submit}>
      <h1 className={styles.title}>ورود به ترب‌کار</h1>
      <label className={styles.field}>
        <span>ایمیل</span>
        <input name="email" type="email" required autoComplete="email" dir="ltr" />
      </label>
      <label className={styles.field}>
        <span>رمز عبور</span>
        <input name="password" type="password" required dir="ltr"
          maxLength={MAX_PASSWORD_LENGTH} autoComplete="current-password" />
      </label>
      {error && <p className={styles.error} role="alert">{error}</p>}
      <button type="submit" className={styles.submit} disabled={busy}>ورود</button>
    </form>
  );
}

export default function LoginPage() {
  // useSearchParams requires a Suspense boundary in the App Router.
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
