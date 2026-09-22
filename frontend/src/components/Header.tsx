"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useRef } from "react";
import { fa } from "@/lib/format";
import { useAppState } from "@/state/AppState";
import { AlertsDropdown } from "./AlertsDropdown";
import { Avatar } from "./Avatar";
import { HeaderSearch } from "./HeaderSearch";
import { Icon } from "./Icon";
import styles from "./Header.module.css";

const SEARCH_SECTION_PREFIXES = ["/results", "/model", "/listing"];
export const isSearchSection = (pathname: string): boolean => SEARCH_SECTION_PREFIXES.some((p) => pathname.startsWith(p));

export function Header() {
  const pathname = usePathname();
  const { compare, alerts, user, loggedIn, bellOpen, chatOpen, setBellOpen, setChatOpen, openAuth, logout } = useAppState();
  const bellRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!bellOpen) return;
    const closeOnOutsideClick = (event: MouseEvent) => { if (!bellRef.current?.contains(event.target as Node)) setBellOpen(false); };
    document.addEventListener("click", closeOnOutsideClick);
    return () => document.removeEventListener("click", closeOnOutsideClick);
  }, [bellOpen, setBellOpen]);

  const tabs = [
    { label: "خانه", href: "/", active: pathname === "/" },
    { label: "جست‌وجو", href: "/results", active: isSearchSection(pathname) },
    { label: compare.length ? `مقایسه (${fa(compare.length)})` : "مقایسه", href: "/compare", active: pathname === "/compare" },
    { label: "تخمین قیمت", href: "/estimate", active: pathname === "/estimate" },
  ];
  const showSearch = pathname !== "/";

  return (
    <>
      <header className={styles.header}>
        <div className={styles.inner}>
          <Link href="/" className={styles.brand}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/logo.png" alt="" width={34} height={34} />
            <span>ترب‌کار</span>
          </Link>
          <nav className={styles.nav}>
            {tabs.map((t) => (
              <Link key={t.href} href={t.href} className={`${styles.tab} ${t.active ? styles.tabActive : ""}`}>{t.label}</Link>
            ))}
          </nav>
          {showSearch && <Suspense fallback={null}><HeaderSearch variant="desktop" /></Suspense>}
          <div className={styles.actions} ref={bellRef}>
            <button className={styles.chatButton} onClick={() => setChatOpen(!chatOpen)}>
              <span className={styles.chatAvatar}><Avatar size={24} /></span>
              <span>دستیار</span>
            </button>
            <button className={styles.iconButton} aria-label="هشدارها" aria-expanded={bellOpen} onClick={() => setBellOpen(!bellOpen)}>
              <Icon name="bell" stroke="#172033" />
              {loggedIn && alerts.length > 0 && <span className={styles.dot} />}
            </button>
            {user
              ? (
                <details className={styles.userMenu}>
                  <summary className={styles.user} title={user.email}>
                    <span className={styles.userBadge}>{user.email.charAt(0).toUpperCase()}</span>
                  </summary>
                  <div className={styles.menu}>
                    <div className={styles.menuEmail} dir="ltr">{user.email}</div>
                    {user.role === "admin" && (
                      <Link href="/admin" className={styles.menuLink}>پنل مدیریت</Link>
                    )}
                    <button type="button" className={styles.menuItem} onClick={logout}>خروج</button>
                  </div>
                </details>
              )
              : <button className={styles.login} onClick={openAuth}>ورود</button>}
            {bellOpen && <AlertsDropdown />}
          </div>
        </div>
      </header>
      {showSearch && <Suspense fallback={null}><HeaderSearch variant="mobile" /></Suspense>}
    </>
  );
}
