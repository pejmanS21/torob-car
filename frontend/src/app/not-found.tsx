import Link from "next/link";
import styles from "./not-found.module.css";

export default function NotFound() {
  return (
    <section className={styles.screen}>
      <div className={styles.card}>
        <h1 className={styles.title}>این صفحه پیدا نشد</h1>
        <p className={styles.lead}>آگهی یا مدلی با این نشانی نداریم.</p>
        <Link href="/" className={styles.cta}>برگشت به خانه</Link>
      </div>
    </section>
  );
}
