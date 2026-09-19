"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, apiPost } from "@/lib/api/client";
import type { AssistantRequest, AssistantResponse } from "@/lib/api/types";
import type { ChatMessage, PriceAlert } from "@/lib/types";

export const MAX_COMPARE = 3;
export type AvatarAnimation = "idle" | "thinking" | "happy";

const STORAGE_KEY = "torobcar:v2"; // v1 held synthetic ids and is ignored
const TOAST_MS = 2200;
const HAPPY_MS = 2500;
const HISTORY_LIMIT = 10; // the backend caps history at 10 messages
const GREETING: ChatMessage = { role: "assistant", text: "سلام! بگو دنبال چه ماشینی هستی، یا بپرس کدوم آگهی به‌صرفه‌تره. من همهٔ آگهی‌های فعال رو می‌بینم.", listings: [] };
const CHAT_UNAVAILABLE = "الان به سرویس جست‌وجو دسترسی ندارم؛ چند لحظه بعد دوباره بپرس.";

interface Persisted { compare: string[]; saved: string[]; alerts: PriceAlert[]; loggedIn: boolean; }
const EMPTY: Persisted = { compare: [], saved: [], alerts: [], loggedIn: false };

interface Commit<T> { next: Persisted; result: T; }

// Single read-modify-write path for `persisted`: reads the latest value from a
// ref (never from render-scope state), so two synchronous calls in the same
// tick each see the other's effect. The decision (compute) is pure — no
// toasts or other side effects here, since setPersisted is called with a
// plain value (not an updater function) and React/Strict Mode never
// re-invokes this call site.
function commitPersisted<T>(
  ref: { current: Persisted },
  setPersisted: (next: Persisted) => void,
  compute: (current: Persisted) => Commit<T>,
): T {
  const { next, result } = compute(ref.current);
  ref.current = next;
  setPersisted(next);
  return result;
}

export interface AppStateValue extends Persisted {
  bellOpen: boolean; chatOpen: boolean; chatMessages: ChatMessage[]; chatBusy: boolean; avatarAnimation: AvatarAnimation; toast: string;
  toggleCompare(id: string): void; removeFromCompare(id: string): void; toggleSaved(id: string): void;
  addAlert(alert: PriceAlert): void; removeAlert(index: number): void; toggleLogin(): void;
  setBellOpen(open: boolean): void; setChatOpen(open: boolean): void; sendChat(text: string): void; showToast(text: string): void;
}

const AppStateContext = createContext<AppStateValue | null>(null);

const isAlert = (a: unknown): a is PriceAlert =>
  typeof a === "object" && a !== null && typeof (a as PriceAlert).title === "string" && typeof (a as PriceAlert).threshold === "number" && typeof (a as PriceAlert).params === "object";

function readPersisted(): Persisted {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY;
    const parsed = JSON.parse(raw) as Partial<Persisted>;
    return {
      compare: Array.isArray(parsed.compare) ? parsed.compare.slice(0, MAX_COMPARE) : EMPTY.compare,
      saved: Array.isArray(parsed.saved) ? parsed.saved : EMPTY.saved,
      alerts: Array.isArray(parsed.alerts) ? parsed.alerts.filter(isAlert) : EMPTY.alerts,
      loggedIn: typeof parsed.loggedIn === "boolean" ? parsed.loggedIn : EMPTY.loggedIn,
    };
  } catch {
    return EMPTY; // storage blocked or corrupt → start clean (spec: Error handling)
  }
}

const toAssistantMessages = (messages: ChatMessage[]): AssistantRequest["messages"] =>
  messages.slice(-HISTORY_LIMIT).map(({ role, text }) => ({ role, text }));

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const [persisted, setPersisted] = useState<Persisted>(EMPTY);
  const [hydrated, setHydrated] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([GREETING]);
  const [chatBusy, setChatBusy] = useState(false);
  const [recentReply, setRecentReply] = useState(false);
  const [toast, setToast] = useState("");
  const toastTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const happyTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const persistedRef = useRef<Persisted>(EMPTY);
  const chatRef = useRef<ChatMessage[]>([GREETING]);
  const chatBusyRef = useRef(false);
  const mountedRef = useRef(true);

  // Load after mount so server and first client render match.
  useEffect(() => {
    const loaded = readPersisted();
    persistedRef.current = loaded;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time hydration-safe load from localStorage
    setPersisted(loaded);
    setHydrated(true);
  }, []);
  useEffect(() => {
    if (!hydrated) return;
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(persisted)); } catch { /* storage unavailable: state stays in memory */ }
  }, [persisted, hydrated]);

  // Clear pending timers on unmount so a fired timeout never calls setState
  // after teardown (Strict Mode mounts/unmounts/remounts in dev).
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      clearTimeout(toastTimer.current);
      clearTimeout(happyTimer.current);
    };
  }, []);

  const showToast = useCallback((text: string) => {
    setToast(text);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), TOAST_MS);
  }, []);

  const toggleCompare = useCallback((id: string) => {
    const outcome = commitPersisted(persistedRef, setPersisted, (p) => {
      if (p.compare.includes(id)) {
        return { next: { ...p, compare: p.compare.filter((x) => x !== id) }, result: "removed" as const };
      }
      if (p.compare.length >= MAX_COMPARE) {
        return { next: p, result: "limit" as const };
      }
      return { next: { ...p, compare: [...p.compare, id] }, result: "added" as const };
    });
    if (outcome === "limit") showToast("حداکثر سه خودرو می‌تونی مقایسه کنی");
    else if (outcome === "added") showToast("به مقایسه اضافه شد");
  }, [showToast]);

  const removeFromCompare = useCallback((id: string) => {
    commitPersisted(persistedRef, setPersisted, (p) => ({ next: { ...p, compare: p.compare.filter((x) => x !== id) }, result: undefined }));
  }, []);

  const toggleSaved = useCallback((id: string) => {
    const wasSaved = commitPersisted(persistedRef, setPersisted, (p) => {
      const already = p.saved.includes(id);
      return { next: { ...p, saved: already ? p.saved.filter((x) => x !== id) : [...p.saved, id] }, result: already };
    });
    showToast(wasSaved ? "از نشان‌ها حذف شد" : "نشان شد");
  }, [showToast]);

  const addAlert = useCallback((alert: PriceAlert) => {
    const outcome = commitPersisted(persistedRef, setPersisted, (p) => {
      if (!p.loggedIn) return { next: p, result: "blocked" as const };
      return { next: { ...p, alerts: [...p.alerts, alert] }, result: "saved" as const };
    });
    if (outcome === "blocked") { setBellOpen(true); showToast("برای هشدار قیمت اول وارد شو"); }
    else showToast("هشدار قیمت ذخیره شد");
  }, [showToast]);

  const removeAlert = useCallback((index: number) => {
    commitPersisted(persistedRef, setPersisted, (p) => ({ next: { ...p, alerts: p.alerts.filter((_, i) => i !== index) }, result: undefined }));
  }, []);

  const toggleLogin = useCallback(() => {
    const nextLoggedIn = commitPersisted(persistedRef, setPersisted, (p) => ({ next: { ...p, loggedIn: !p.loggedIn }, result: !p.loggedIn }));
    showToast(nextLoggedIn ? "خوش اومدی علی!" : "خارج شدی");
    setBellOpen(false);
  }, [showToast]);

  const appendChat = useCallback((message: ChatMessage) => {
    chatRef.current = [...chatRef.current, message];
    setChatMessages(chatRef.current);
  }, []);

  // Stateless assistant: every call carries the recent history and the compare ids.
  const sendChat = useCallback((raw: string) => {
    const text = raw.trim();
    if (!text || chatBusyRef.current) return;
    chatBusyRef.current = true;
    setChatBusy(true);
    appendChat({ role: "user", text, listings: [] });
    const body: AssistantRequest = { messages: toAssistantMessages(chatRef.current), compare_ids: persistedRef.current.compare };
    apiPost<AssistantResponse>("/assistant", body)
      .then((reply) => ({ role: "assistant" as const, text: reply.text, listings: reply.listings }))
      .catch((error: unknown) => ({ role: "assistant" as const, text: error instanceof ApiError && error.status === 422 ? error.message : CHAT_UNAVAILABLE, listings: [] }))
      .then((message) => {
        if (!mountedRef.current) return;
        appendChat(message);
        chatBusyRef.current = false;
        setChatBusy(false);
        setRecentReply(true);
        clearTimeout(happyTimer.current);
        happyTimer.current = setTimeout(() => setRecentReply(false), HAPPY_MS);
      });
  }, [appendChat]);

  const avatarAnimation: AvatarAnimation = chatBusy ? "thinking" : recentReply ? "happy" : "idle";

  const value = useMemo<AppStateValue>(() => ({
    ...persisted, bellOpen, chatOpen, chatMessages, chatBusy, avatarAnimation, toast,
    toggleCompare, removeFromCompare, toggleSaved, addAlert, removeAlert, toggleLogin, setBellOpen, setChatOpen, sendChat, showToast,
  }), [persisted, bellOpen, chatOpen, chatMessages, chatBusy, avatarAnimation, toast, toggleCompare, removeFromCompare, toggleSaved, addAlert, removeAlert, toggleLogin, sendChat, showToast]);

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState(): AppStateValue {
  const value = useContext(AppStateContext);
  if (!value) throw new Error("useAppState must be used inside <AppStateProvider>");
  return value;
}
