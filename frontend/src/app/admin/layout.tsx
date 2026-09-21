"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAppState } from "@/state/AppState";
import styles from "./admin.module.css";

const TABS = [
  { href: "/admin", label: "نمای کلی" },
  { href: "/admin/users", label: "کاربران" },
];

export default function AdminLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const { user, authReady } = useAppState();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (authReady && !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [authReady, user, pathname, router]);

  if (!authReady) return <p className={styles.state}>در حال بررسی دسترسی…</p>;
  if (!user) return null; // redirecting
  if (user.role !== "admin") return <p className={styles.state}>دسترسی ندارید</p>;

  return (
    <div className={styles.shell}>
      <nav className={styles.nav}>
        {TABS.map((tab) => (
          <Link key={tab.href} href={tab.href}
            className={`${styles.tab} ${pathname === tab.href ? styles.tabActive : ""}`}>
            {tab.label}
          </Link>
        ))}
      </nav>
      <section className={styles.body}>{children}</section>
    </div>
  );
}
