"use client";

import { useEffect, useRef } from "react";
import styles from "./RedirectOverlay.module.css";

/** Full-screen "taking you to <site>" card shown while an outbound ad link opens.
 * The fallback link covers the case where the new tab never appears (popup blocked). */
export function RedirectOverlay({
  sourceLabel,
  title,
  url,
}: Readonly<{
  sourceLabel: string;
  title: string;
  url: string;
}>) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  return (
    <dialog ref={dialog} className={styles.backdrop} aria-label="انتقال به آگهی" aria-live="polite">
      <div className={styles.card}>
        <span className={styles.badge} aria-hidden="true">
          <span className={styles.badgeRing} />
        </span>
        <p className={styles.lead}>در حال انتقال از ترب‌کار به</p>
        <p className={styles.source}>{sourceLabel}</p>
        <p className={styles.title}>{title}</p>
        <PixelCar />
        <a href={url} target="_blank" rel="noopener" className={styles.fallback}>
          اگر منتقل نشدید، اینجا کلیک کنید
        </a>
        <span className={styles.progress} aria-hidden="true" />
      </div>
    </dialog>
  );
}

/** Pixel-art car, drawn as flat rects so it stays crisp at any size. */
function PixelCar() {
  const body = "var(--red)";
  const dark = "var(--red-dark)";
  const glass = "#cdd7e5";
  const tyre = "#172033";
  return (
    <svg className={styles.car} viewBox="0 0 22 14" shapeRendering="crispEdges" aria-hidden="true">
      <rect x="5" y="2" width="11" height="4" fill={dark} />
      <rect x="6" y="3" width="4" height="2" fill={glass} />
      <rect x="11" y="3" width="4" height="2" fill={glass} />
      <rect x="2" y="6" width="18" height="4" fill={body} />
      <rect x="2" y="9" width="18" height="1" fill={dark} />
      <rect x="1" y="7" width="1" height="2" fill={body} />
      <rect x="20" y="7" width="1" height="2" fill={body} />
      <rect x="4" y="10" width="3" height="2" fill={tyre} />
      <rect x="15" y="10" width="3" height="2" fill={tyre} />
    </svg>
  );
}
