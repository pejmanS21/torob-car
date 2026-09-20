"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Icon } from "./Icon";
import styles from "./HeaderSearch.module.css";

const PLACEHOLDER = { desktop: "مثلاً: دنا پلاس اتومات زیر یک میلیارد، کرج", mobile: "جست‌وجو…" } as const;

export function HeaderSearch({ variant }: { variant: "desktop" | "mobile" }) {
  const router = useRouter();
  const query = useSearchParams().get("q") ?? "";
  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = String(new FormData(event.currentTarget).get("q") ?? "").trim();
    router.push(text ? `/results?q=${encodeURIComponent(text)}` : "/results");
  }
  return (
    <form onSubmit={submit} className={styles[variant]} role="search">
      <div className={styles.box}>
        <Icon name="search" stroke="#667085" />
        <input key={query} name="q" defaultValue={query} spellCheck={false} placeholder={PLACEHOLDER[variant]} className={styles.input} aria-label="جست‌وجو" />
      </div>
    </form>
  );
}
