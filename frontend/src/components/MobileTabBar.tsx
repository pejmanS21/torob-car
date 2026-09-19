"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAppState } from "@/state/AppState";
import { isSearchSection } from "./Header";
import { Icon, type IconName } from "./Icon";
import styles from "./MobileTabBar.module.css";

const ACTIVE_FILL = "#fde2e4";

export function MobileTabBar() {
  const pathname = usePathname();
  const { chatOpen, setChatOpen } = useAppState();
  const links: { label: string; href: string; icon: IconName; active: boolean }[] = [
    { label: "خانه", href: "/", icon: "home", active: pathname === "/" },
    { label: "جست‌وجو", href: "/results", icon: "search", active: isSearchSection(pathname) },
    { label: "مقایسه", href: "/compare", icon: "compare", active: pathname === "/compare" },
    { label: "تخمین", href: "/estimate", icon: "estimate", active: pathname === "/estimate" },
  ];
  const item = (l: (typeof links)[number]) => (
    <Link key={l.href} href={l.href} className={`${styles.item} ${l.active ? styles.active : ""}`} onClick={() => setChatOpen(false)}>
      <Icon name={l.icon} size={22} fill={l.active ? ACTIVE_FILL : "none"} />{l.label}
    </Link>
  );
  return (
    <nav className={styles.bar} aria-label="ناوبری اصلی">
      {links.slice(0, 2).map(item)}
      <button className={`${styles.item} ${chatOpen ? styles.active : ""}`} onClick={() => setChatOpen(!chatOpen)}>
        <Icon name="sparkles" size={22} fill={chatOpen ? ACTIVE_FILL : "none"} />دستیار
      </button>
      {links.slice(2).map(item)}
    </nav>
  );
}
