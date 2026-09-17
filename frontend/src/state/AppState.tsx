"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { scriptedReply } from "@/lib/assistant";
import { LISTINGS } from "@/lib/listings";
import type { ChatMessage, PriceAlert } from "@/lib/types";

export const MAX_COMPARE = 3;
export type AvatarAnimation = "idle" | "thinking" | "happy";

const STORAGE_KEY = "torobcar:v1";
const TOAST_MS = 2200;
const REPLY_DELAY_MS = 700;
const HAPPY_MS = 2500;
const GREETING: ChatMessage = { role: "assistant", text: "سلام! بگو دنبال چه ماشینی هستی، یا بپرس کدوم آگهی به‌صرفه‌تره. من همهٔ آگهی‌های فعال رو می‌بینم." };

interface Persisted { compare: string[]; saved: string[]; alerts: PriceAlert[]; loggedIn: boolean; }
const EMPTY: Persisted = { compare: [], saved: [], alerts: [], loggedIn: false };

export interface AppStateValue extends Persisted {
  bellOpen: boolean; chatOpen: boolean; chatMessages: ChatMessage[]; chatBusy: boolean; avatarAnimation: AvatarAnimation; toast: string;
  toggleCompare(id: string): void; removeFromCompare(id: string): void; toggleSaved(id: string): void;
  addAlert(alert: PriceAlert): void; removeAlert(index: number): void; toggleLogin(): void;
  setBellOpen(open: boolean): void; setChatOpen(open: boolean): void; sendChat(text: string): void; showToast(text: string): void;
}

const AppStateContext = createContext<AppStateValue | null>(null);

function readPersisted(): Persisted {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? { ...EMPTY, ...(JSON.parse(raw) as Partial<Persisted>) } : EMPTY;
  } catch {
    return EMPTY; // storage blocked or corrupt → start clean (spec: Error handling)
  }
}

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

  // Load after mount so server and first client render match.
  // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time hydration-safe load from localStorage
  useEffect(() => { setPersisted(readPersisted()); setHydrated(true); }, []);
  useEffect(() => {
    if (!hydrated) return;
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(persisted)); } catch { /* storage unavailable: state stays in memory */ }
  }, [persisted, hydrated]);

  const patch = useCallback((change: (p: Persisted) => Partial<Persisted>) => setPersisted((p) => ({ ...p, ...change(p) })), []);

  const showToast = useCallback((text: string) => {
    setToast(text);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), TOAST_MS);
  }, []);

  const toggleCompare = useCallback((id: string) => {
    if (persisted.compare.includes(id)) { patch((p) => ({ compare: p.compare.filter((x) => x !== id) })); return; }
    if (persisted.compare.length >= MAX_COMPARE) { showToast("حداکثر سه خودرو می‌تونی مقایسه کنی"); return; }
    patch((p) => ({ compare: [...p.compare, id] }));
    showToast("به مقایسه اضافه شد");
  }, [persisted.compare, patch, showToast]);

  const removeFromCompare = useCallback((id: string) => patch((p) => ({ compare: p.compare.filter((x) => x !== id) })), [patch]);

  const toggleSaved = useCallback((id: string) => {
    const wasSaved = persisted.saved.includes(id);
    patch((p) => ({ saved: wasSaved ? p.saved.filter((x) => x !== id) : [...p.saved, id] }));
    showToast(wasSaved ? "از نشان‌ها حذف شد" : "نشان شد");
  }, [persisted.saved, patch, showToast]);

  const addAlert = useCallback((alert: PriceAlert) => {
    if (!persisted.loggedIn) { setBellOpen(true); showToast("برای هشدار قیمت اول وارد شو"); return; }
    patch((p) => ({ alerts: [...p.alerts, alert] }));
    showToast("هشدار قیمت ذخیره شد");
  }, [persisted.loggedIn, patch, showToast]);

  const removeAlert = useCallback((index: number) => patch((p) => ({ alerts: p.alerts.filter((_, i) => i !== index) })), [patch]);

  const toggleLogin = useCallback(() => {
    showToast(persisted.loggedIn ? "خارج شدی" : "خوش اومدی علی!");
    patch((p) => ({ loggedIn: !p.loggedIn }));
    setBellOpen(false);
  }, [persisted.loggedIn, patch, showToast]);

  const sendChat = useCallback((raw: string) => {
    const text = raw.trim();
    if (!text || chatBusy) return;
    setChatMessages((m) => [...m, { role: "user", text }]);
    setChatBusy(true);
    const compareIds = persisted.compare;
    setTimeout(() => {
      setChatMessages((m) => [...m, { role: "assistant", ...scriptedReply(text, LISTINGS, compareIds) }]);
      setChatBusy(false);
      setRecentReply(true);
      clearTimeout(happyTimer.current);
      happyTimer.current = setTimeout(() => setRecentReply(false), HAPPY_MS);
    }, REPLY_DELAY_MS);
  }, [chatBusy, persisted.compare]);

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
