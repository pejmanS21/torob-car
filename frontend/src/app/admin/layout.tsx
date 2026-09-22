"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAppState } from "@/state/AppState";
import { AdminIcon, type AdminIconName, LoadingState } from "./ui";
import styles from "./admin.module.css";

const NAV: { href: string; label: string; icon: AdminIconName }[] = [
  { href: "/admin", label: "نمای کلی", icon: "dashboard" },
  { href: "/admin/users", label: "مدیریت کاربران", icon: "users" },
  { href: "/admin/audit", label: "گزارش فعالیت‌ها", icon: "activity" },
];
export default function AdminLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const { user, authReady, logout } = useAppState();
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => {
    if (authReady && !user)
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [authReady, user, pathname, router]);
  if (!authReady) return <LoadingState />;
  if (!user) return null;
  if (user.role !== "admin")
    return (
      <div className={styles.empty}>
        <AdminIcon name="shield" size={32} />
        <h1>دسترسی ندارید</h1>
        <p>این بخش فقط برای مدیران سامانه در دسترس است.</p>
        <Link className={styles.button} href="/">
          بازگشت به سایت
        </Link>
      </div>
    );
  return (
    <div className={styles.shell}>
      <a href="#admin-content" className={styles.skipLink}>
        رفتن به محتوای اصلی
      </a>
      <aside className={styles.sidebar}>
        <Link href="/admin" className={styles.brand}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.png" alt="" width={43} height={43} className={styles.brandMark} />
          <span>
            ترب‌کار<small>پنل مدیریت</small>
          </span>
        </Link>
        <div className={styles.navLabel}>فضای مدیریت</div>
        <nav className={styles.nav} aria-label="منوی مدیریت">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={pathname === item.href ? "page" : undefined}
              className={`${styles.navItem} ${pathname === item.href ? styles.navActive : ""}`}
            >
              <AdminIcon name={item.icon} />
              <span>{item.label}</span>
              {pathname === item.href && <span className={styles.activeDot} />}
            </Link>
          ))}
        </nav>
        <div className={styles.sidebarBottom}>
          <Link href="/" className={styles.navItem}>
            <AdminIcon name="arrow" />
            <span>بازگشت به سایت</span>
          </Link>
          <div className={styles.profile}>
            <span className={styles.avatar}>
              {user.email.slice(0, 1).toUpperCase()}
            </span>
            <div>
              <strong>مدیر سامانه</strong>
              <span dir="ltr" title={user.email}>
                {user.email}
              </span>
            </div>
            <button
              type="button"
              className={styles.iconButton}
              aria-label="خروج از حساب"
              onClick={() => void logout()}
            >
              <AdminIcon name="logout" size={18} />
            </button>
          </div>
        </div>
      </aside>
      <div className={styles.workspace}>
        <header className={styles.topbar}>
          <div className={styles.breadcrumb}>
            پنل مدیریت<span>/</span>
            <strong>
              {NAV.find((item) => item.href === pathname)?.label ?? "مدیریت"}
            </strong>
          </div>
          <div className={styles.topbarActions}>
            <Link className={styles.mobileSiteLink} href="/">
              بازگشت به سایت
            </Link>
            <button
              type="button"
              className={styles.mobileLogout}
              aria-label="خروج از حساب"
              onClick={() => void logout()}
            >
              <AdminIcon name="logout" size={17} />
            </button>
            <span className={styles.accessBadge}>
              <AdminIcon name="shield" size={15} />
              دسترسی مدیر
            </span>
          </div>
        </header>
        <main id="admin-content" tabIndex={-1} className={styles.body}>
          {children}
        </main>
        <footer className={styles.footer}>
          <span>ترب‌کار · فضای مدیریت</span>
          <span>تغییرات مدیریتی در گزارش فعالیت‌ها ثبت می‌شوند.</span>
        </footer>
      </div>
    </div>
  );
}
