"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Icon } from "./Icon";
import styles from "./HomeSearch.module.css";

// Real queries that return results on the crawled data (checked against the API).
const EXAMPLES = [
  "پژو ۲۰۶ تیپ ۲ تهران",
  "پراید زیر ۳۰۰ میلیون",
  "دنا پلاس اتومات",
  "سمند مدل ۹۵ به بالا مشهد",
];

export function HomeSearch() {
  const router = useRouter();
  const [text, setText] = useState("");

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = text.trim();
    router.push(trimmed ? `/results?q=${encodeURIComponent(trimmed)}` : "/results");
  }

  return (
    <>
      <form onSubmit={submit} className={styles.form} role="search">
        <div className={styles.box}>
          <Icon name="search" stroke="#98a2b3" size={22} />
          <input
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="مثلاً: پژو ۲۰۶ کم‌کارکرد زیر ۷۰۰ میلیون، تهران"
            className={styles.input}
            aria-label="جست‌وجو"
            spellCheck={false}
          />
          <button type="submit" className={styles.submit}>جست‌وجو</button>
        </div>
      </form>
      <div className={styles.examples}>
        {EXAMPLES.map((example) => (
          <Link key={example} href={`/results?q=${encodeURIComponent(example)}`} className={styles.example}>{example}</Link>
        ))}
      </div>
    </>
  );
}
