"use client";
import { useEffect, useRef, useState } from "react";
import { cardOf } from "@/lib/view";
import { useAppState } from "@/state/AppState";
import { Avatar } from "./Avatar";
import { Icon } from "./Icon";
import { MiniListing } from "./MiniListing";
import styles from "./ChatPanel.module.css";

const OPENING = ["پژو ۲۰۶ تیپ ۲ تهران", "پراید زیر ۳۰۰ میلیون", "دنا پلاس اتومات"];
const COMPARING = ["بین این‌ها کدوم به‌صرفه‌تره؟"];
const FOLLOW_UP = ["ارزان‌ترین سمند مشهد", "فقط ارزان‌تر از بازار نشون بده"];

export function ChatPanel() {
  const { chatOpen, setChatOpen, chatMessages, chatBusy, avatarAnimation, compare, sendChat, loggedIn, chats, activeChatId, startChat, openChat, deleteChat, openAuth } = useAppState();
  const [input, setInput] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight }); }, [chatMessages, chatBusy]);
  if (!chatOpen) return null;

  const lastRecommendations = chatMessages.findLast((message) => message.role === "assistant" && message.listings.length > 0);
  const canCompare = lastRecommendations ? lastRecommendations.listings.length >= 2 : compare.length >= 2;
  const followUpSuggestions = canCompare ? COMPARING : FOLLOW_UP;
  const suggestions = chatMessages.length <= 1 ? OPENING : followUpSuggestions;
  function submit(event: React.SubmitEvent) { event.preventDefault(); sendChat(input); setInput(""); }
  function newChat() { setHistoryOpen(false); startChat(); }
  function resume(id: string) { setHistoryOpen(false); openChat(id); }

  return (
    <aside className={styles.panel} aria-label="دستیار خرید">
      <div className={styles.head}>
        <div className={styles.avatar}><Avatar size={40} animation={avatarAnimation} /></div>
        <div className={styles.title}>دستیار خرید</div>
        {loggedIn && (
          <>
            <button className={styles.headAction} onClick={newChat} disabled={chatBusy}>گفتگوی جدید +</button>
            <button className={styles.headAction} onClick={() => setHistoryOpen(!historyOpen)} aria-expanded={historyOpen} disabled={chatBusy}>
              {historyOpen ? "بازگشت" : `پیشین (${chats.length})`}
            </button>
          </>
        )}
        <button className={styles.close} onClick={() => setChatOpen(false)} aria-label="بستن">×</button>
      </div>
      {/* `loggedIn` guards the view too: logging out while the list is open would
          otherwise strand the visitor there, since "بازگشت" lives in the head above. */}
      {loggedIn && historyOpen ? (
        <div className={styles.history}>
          {chats.length === 0 && <p className={styles.empty}>هنوز گفتگویی ذخیره نشده.</p>}
          {chats.map((chat) => (
            <div key={chat.id} className={chat.id === activeChatId ? styles.chatRowActive : styles.chatRow}>
              <button className={styles.chatOpen} onClick={() => resume(chat.id)} disabled={chatBusy}>
                <span className={styles.chatTitle}>{chat.title}</span>
                <span className={styles.chatDate}>{new Date(chat.updated_at).toLocaleDateString("fa-IR")}</span>
              </button>
              <button className={styles.chatDelete} onClick={() => deleteChat(chat.id)} aria-label={`حذف ${chat.title}`} disabled={chatBusy}>×</button>
            </div>
          ))}
        </div>
      ) : (
      <>
      <div className={styles.messages} ref={scrollRef}>
        {chatMessages.map((m) => (
          <div key={m.id} className={m.role === "user" ? styles.fromUser : styles.fromAssistant}>
            {m.text && <div className={styles.bubble} lang="fa" dir="rtl" aria-busy={m.status === "streaming"}>{m.text}</div>}
            {m.listings.length > 0 && (
              <div className={styles.cards}>
                {m.listings.map((l) => <MiniListing key={l.id} card={cardOf(l)} bordered />)}
              </div>
            )}
          </div>
        ))}
        {chatBusy && <div className={styles.typing}><span /><span /><span /></div>}
      </div>
      <div className={styles.suggestions}>
        {suggestions.map((s) => <button key={s} className={styles.chip} onClick={() => sendChat(s)} disabled={chatBusy}>{s}</button>)}
        {!loggedIn && <button className={styles.chip} onClick={openAuth}>ادامهٔ گفتگو با ورود به حساب</button>}
      </div>
      <form className={styles.form} onSubmit={submit}>
        <input value={input} onChange={(e) => setInput(e.target.value)} spellCheck={false} placeholder="مثلاً: بین این‌ها کدوم به‌صرفه‌تره؟" className={styles.input} aria-label="پیام" maxLength={500} />
        <button type="submit" className={styles.send} aria-label="ارسال" disabled={chatBusy}><Icon name="send" stroke="#fff" /></button>
      </form>
      </>
      )}
    </aside>
  );
}
