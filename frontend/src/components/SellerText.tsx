import Link from "next/link";
import styles from "./SellerText.module.css";

export function SellerText({ desc, links }: Readonly<{ desc: string; links: { text: string; href: string }[] }>) {
  return (
    <div className={styles.card}>
      <div className={styles.title}>متن آگهی فروشنده</div>
      <p className={styles.desc}>{desc}</p>
      <div className={styles.crumbs}>
        {links.map((link) => (
          <Link key={link.href} href={link.href} className={styles.crumb}>
            {link.text}
          </Link>
        ))}
      </div>
    </div>
  );
}
