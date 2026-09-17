"use client";
import { useEffect, useRef, useState } from "react";
import { findListing } from "@/lib/listings";
import { cardOf } from "@/lib/view";
import { useAppState } from "@/state/AppState";
import { Avatar } from "./Avatar";
import { Icon } from "./Icon";
import { MiniListing } from "./MiniListing";
import styles from "./ChatPanel.module.css";

const OPENING = ["دنا پلاس زیر ۹۰۰ میلیون", "کم‌کارکردترین ۲۰۶ تهران", "تارا اتومات به‌صرفه"];
const COMPARING = ["بین این‌ها کدوم به‌صرفه‌تره؟"];
const FOLLOW_UP = ["ارزان‌ترین جک J4", "فقط ارزان‌تر از بازار نشون بده"];

export function ChatPanel() {
  const { chatOpen, setChatOpen, chatMessages, chatBusy, avatarAnimation, compare, sendChat } = useAppState();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight }); }, [chatMessages, chatBusy]);
  if (!chatOpen) return null;

  const suggestions = chatMessages.length <= 1 ? OPENING : compare.length >= 2 ? COMPARING : FOLLOW_UP;
  function submit(event: React.FormEvent) { event.preventDefault(); sendChat(input); setInput(""); }

  return (
    <aside className={styles.panel} aria-label="دستیار خرید">
      <div className={styles.head}>
        <div className={styles.avatar}><Avatar size={40} animation={avatarAnimation} /></div>
        <div className={styles.title}>دستیار خرید</div>
        <button className={styles.close} onClick={() => setChatOpen(false)} aria-label="بستن">×</button>
      </div>
      <div className={styles.messages} ref={scrollRef}>
        {chatMessages.map((m, i) => (
          <div key={i} className={m.role === "user" ? styles.fromUser : styles.fromAssistant}>
            <div className={styles.bubble}>{m.text}</div>
            {m.cardIds && (
              <div className={styles.cards}>
                {m.cardIds.map((id) => { const l = findListing(id); return l ? <MiniListing key={id} card={cardOf(l)} bordered /> : null; })}
              </div>
            )}
          </div>
        ))}
        {chatBusy && <div className={styles.typing}><span /><span /><span /></div>}
      </div>
      <div className={styles.suggestions}>
        {suggestions.map((s) => <button key={s} className={styles.chip} onClick={() => sendChat(s)}>{s}</button>)}
      </div>
      <form className={styles.form} onSubmit={submit}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="مثلاً: بین این‌ها کدوم به‌صرفه‌تره؟" className={styles.input} aria-label="پیام" />
        <button type="submit" className={styles.send} aria-label="ارسال"><Icon name="send" stroke="#fff" /></button>
      </form>
    </aside>
  );
}
