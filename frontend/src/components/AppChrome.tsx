"use client";

import { usePathname } from "next/navigation";
import { ChatPanel } from "./ChatPanel";
import { Footer } from "./Footer";
import { Header } from "./Header";
import { MobileTabBar } from "./MobileTabBar";

/** Administration has its own navigation and full-width workspace. */
export function AppChrome({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();
  if (pathname === "/admin" || pathname.startsWith("/admin/")) {
    return <div className="admin-app">{children}</div>;
  }
  return (
    <>
      <div className="app">
        <Header />
        <main className="page">{children}</main>
        <Footer />
      </div>
      <MobileTabBar />
      <ChatPanel />
    </>
  );
}
