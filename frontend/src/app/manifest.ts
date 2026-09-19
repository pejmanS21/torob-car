import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ترب‌کار",
    short_name: "ترب‌کار",
    description: "ماشین می‌خوای؟ فقط بگو چی.",
    start_url: "/",
    display: "standalone",
    dir: "rtl",
    lang: "fa",
    theme_color: "#d9232e",
    background_color: "#f6f7f9",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
