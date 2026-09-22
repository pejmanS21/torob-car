import type { Metadata, Viewport } from "next";
import { Vazirmatn } from "next/font/google";
import { AppStateProvider } from "@/state/AppState";
import { AuthDialog } from "@/components/AuthDialog";
import { AppChrome } from "@/components/AppChrome";
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
  icons: { icon: "/icons/icon-192.png", apple: "/icons/apple-touch-icon.png" },
  appleWebApp: { capable: true, title: "ترب‌کار", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#d9232e",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fa" dir="rtl" className={vazirmatn.variable}>
      <body>
        <AppStateProvider>
          <AppChrome>{children}</AppChrome>
          <AuthDialog />
          <Toast />
        </AppStateProvider>
      </body>
    </html>
  );
}
