import { HomeSearch } from "@/components/HomeSearch";
import { MODELS } from "@/lib/catalog";
import { fa } from "@/lib/format";
import { LISTINGS } from "@/lib/listings";
import styles from "./page.module.css";

export default function HomePage() {
  return (
    <section className={styles.home}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/logo.png" alt="" className={styles.logo} />
      <h1 className={styles.title}>ماشین می‌خوای؟ فقط بگو چی.</h1>
      <HomeSearch />
      <div className={styles.stats}>
        <span><b className={styles.statNum}>{fa(LISTINGS.length)}</b> آگهی فعال</span>
        <span><b className={styles.statNum}>{fa(MODELS.length)}</b> مدل</span>
        <span>به‌روزرسانی: <b className={styles.statNum}>۱۲ دقیقه پیش</b></span>
      </div>
    </section>
  );
}
