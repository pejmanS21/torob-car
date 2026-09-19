import type { ApiError } from "@/lib/api/client";
import styles from "./ErrorBanner.module.css";

export const SERVICE_UNAVAILABLE = "سرویس جست‌وجو در دسترس نیست";

/** 422 → the backend's own message (a user problem); anything else → service unavailable. */
export const errorText = (error: ApiError): string => (error.status === 422 ? error.message : SERVICE_UNAVAILABLE);

export function ErrorBanner({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div className={styles.banner} role="alert">
      <span>{errorText(error)}</span>
      {onRetry && error.status !== 422 && <button type="button" className={styles.retry} onClick={onRetry}>تلاش دوباره</button>}
    </div>
  );
}
