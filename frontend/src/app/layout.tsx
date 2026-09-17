import type { Metadata, Viewport } from "next";
import { Vazirmatn } from "next/font/google";
import { AppStateProvider } from "@/state/AppState";
import { ChatPanel } from "@/components/ChatPanel";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { MobileTabBar } from "@/components/MobileTabBar";
import { Toast } from "@/components/Toast";
import "./globals.css";

const vazirmatn = Vazirmatn({
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-vazirmatn",
});

export const metadata: Metadata = {
  title: "ترب‌کار",
  description: "ماشین می‌خوای؟ فقط بگو چی.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#d9232e",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl" className={vazirmatn.variable}>
      <body>
        <AppStateProvider>
          <div className="app">
            <Header />
            <main className="page">{children}</main>
            <Footer />
          </div>
          <MobileTabBar />
          <ChatPanel />
          <Toast />
        </AppStateProvider>
      </body>
    </html>
  );
}
