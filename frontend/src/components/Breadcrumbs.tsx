import Link from "next/link";
import { Fragment } from "react";
import styles from "./Breadcrumbs.module.css";

interface Item { label: string; href?: string; }

export function Breadcrumbs({ items }: Readonly<{ items: Item[] }>) {
  return (
    <div className={styles.crumbs}>
      {items.map((item, i) => (
        <Fragment key={`${item.label}-${i}`}>
          {item.href ? <Link href={item.href}>{item.label}</Link> : <span className={styles.current}>{item.label}</span>}
          {i < items.length - 1 && <span>›</span>}
        </Fragment>
      ))}
    </div>
  );
}
