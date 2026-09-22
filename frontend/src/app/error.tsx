"use client"; // error boundaries must be Client Components
import { useEffect } from "react";
import { SERVICE_UNAVAILABLE } from "@/components/ErrorBanner";
import styles from "./not-found.module.css";

// Next 16 passes `retry` (not `reset`) to error boundaries.
export default function RouteError({ error, retry }: Readonly<{ error: Error & { digest?: string }; retry: () => void }>) {
  useEffect(() => { console.error(error); }, [error]);
  return (
    <section className={styles.screen}>
      <div className={styles.card}>
        <h1 className={styles.title}>{SERVICE_UNAVAILABLE}</h1>
        <p className={styles.lead}>چند لحظه بعد دوباره امتحان کن.</p>
        <button type="button" className={styles.cta} onClick={() => retry()}>تلاش دوباره</button>
      </div>
    </section>
  );
}
