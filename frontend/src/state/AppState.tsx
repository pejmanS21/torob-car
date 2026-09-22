"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { clearAccount, importableLists, removeAlertById, toAlertBody, toPriceAlert, toggleSavedId, withAlertId } from "@/lib/account";
import { ApiError, apiDelete, apiGet, apiPost, apiPut } from "@/lib/api/client";
import type { AccountState, AssistantRequest, AssistantResponse, PriceAlertRead, UserRead } from "@/lib/api/types";
import type { ChatMessage, PriceAlert } from "@/lib/types";

export const MAX_COMPARE = 3;
export type AvatarAnimation = "idle" | "thinking" | "happy";

const STORAGE_KEY = "torobcar:v2"; // v1 held synthetic ids and is ignored
const TOAST_MS = 2200;
const HAPPY_MS = 2500;
const HISTORY_LIMIT = 10; // the backend caps history at 10 messages
const GREETING: ChatMessage = { role: "assistant", text: "سلام! بگو دنبال چه ماشینی هستی، یا بپرس کدوم آگهی به‌صرفه‌تره. من همهٔ آگهی‌های فعال رو می‌بینم.", listings: [] };
const CHAT_UNAVAILABLE = "الان به سرویس جست‌وجو دسترسی ندارم؛ چند لحظه بعد دوباره بپرس.";
const SYNC_FAILED = "ذخیره نشد؛ دوباره امتحان کن";
type AuthPath = "/auth/login" | "/auth/register";

// `loggedIn` used to live here as a fake flag; an old stored value is simply ignored.
// `ownerId` (P1-b): which account's data `saved`/`alerts` are. `null` = anonymous —
// including every blob stored before this field existed, so old data keeps working.
interface Persisted { compare: string[]; saved: string[]; alerts: PriceAlert[]; ownerId: string | null; }
const EMPTY: Persisted = { compare: [], saved: [], alerts: [], ownerId: null };

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

// addAlert's two commitPersisted updaters, extracted so the .then/.catch call
// sites pass a named function instead of nesting another arrow inline (Sonar
// max-nested-functions). `local` is matched BY REFERENCE against `p.alerts`,
// so the optimistic add/revert stays keyed to the exact object addAlert
// pushed — never rebuild or clone it before passing it here.
function attachAlertServerId(local: PriceAlert, serverId: string) {
  return (p: Persisted): Commit<undefined> => ({
    next: { ...p, alerts: withAlertId(p.alerts, local, serverId) },
    result: undefined,
  });
}

function revertOptimisticAlert(local: PriceAlert) {
  return (p: Persisted): Commit<undefined> => ({
    next: { ...p, alerts: p.alerts.filter((a) => a !== local) },
    result: undefined,
  });
}

export interface AppStateValue extends Persisted {
  user: UserRead | null; loggedIn: boolean; authReady: boolean; authOpen: boolean;
  bellOpen: boolean; chatOpen: boolean; chatMessages: ChatMessage[]; chatBusy: boolean; avatarAnimation: AvatarAnimation; toast: string;
  toggleCompare(id: string): void; removeFromCompare(id: string): void; toggleSaved(id: string): void;
  addAlert(alert: PriceAlert): void; removeAlert(id: string): void;
  login(email: string, password: string): Promise<void>; register(email: string, password: string): Promise<void>; logout(): Promise<void>;
  openAuth(): void; closeAuth(): void;
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
      ownerId: typeof parsed.ownerId === "string" ? parsed.ownerId : EMPTY.ownerId,
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
  const [user, setUser] = useState<UserRead | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const userRef = useRef<UserRead | null>(null); // callbacks read this, so they stay stable
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

  const adoptSession = useCallback((me: UserRead | null) => { userRef.current = me; setUser(me); }, []);
  const adoptAccount = useCallback((state: AccountState, ownerId: string) => {
    commitPersisted(persistedRef, setPersisted, (p) => ({ next: { ...p, saved: state.saved, alerts: state.alerts.map(toPriceAlert), ownerId }, result: undefined }));
  }, []);

  // Who am I? Server Components stay anonymous, so the session is discovered here.
  useEffect(() => {
    if (!hydrated) return;
    let cancelled = false;
    const load = async () => {
      const me = await apiGet<UserRead>("/me");
      const [saved, alerts] = await Promise.all([apiGet<string[]>("/me/saved"), apiGet<PriceAlertRead[]>("/me/alerts")]);
      if (cancelled) return;
      adoptSession(me);
      adoptAccount({ saved, alerts }, me.id);
    };
    // A 401 is the normal answer for a visitor, and an unreachable API leaves them
    // anonymous too: either way the locally stored `saved` list keeps working.
    load().catch(() => undefined).finally(() => { if (!cancelled) setAuthReady(true); });
    return () => { cancelled = true; };
  }, [hydrated, adoptSession, adoptAccount]);

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

  const flipSaved = useCallback((id: string): boolean =>
    commitPersisted(persistedRef, setPersisted, (p) => {
      const { saved, wasSaved } = toggleSavedId(p.saved, id);
      return { next: { ...p, saved }, result: wasSaved };
    }), []);

  const toggleSaved = useCallback((id: string) => {
    const wasSaved = flipSaved(id);
    showToast(wasSaved ? "از نشان‌ها حذف شد" : "نشان شد");
    if (!userRef.current) return; // anonymous: the list lives in this browser only
    const sync = wasSaved ? apiDelete(`/me/saved/${id}`) : apiPut(`/me/saved/${id}`);
    sync.catch(() => { flipSaved(id); showToast(SYNC_FAILED); });
  }, [flipSaved, showToast]);

  const addAlert = useCallback((alert: PriceAlert) => {
    if (!userRef.current) { setAuthOpen(true); showToast("برای هشدار قیمت اول وارد شو"); return; }
    commitPersisted(persistedRef, setPersisted, (p) => ({ next: { ...p, alerts: [...p.alerts, alert] }, result: undefined }));
    showToast("هشدار قیمت ذخیره شد");
    apiPost<PriceAlertRead>("/me/alerts", toAlertBody(alert))
      .then((stored) => commitPersisted(persistedRef, setPersisted, attachAlertServerId(alert, stored.id)))
      .catch(() => {
        commitPersisted(persistedRef, setPersisted, revertOptimisticAlert(alert));
        showToast(SYNC_FAILED);
      });
  }, [showToast]);

  const removeAlert = useCallback((id: string) => {
    const removed = commitPersisted(persistedRef, setPersisted, (p) => {
      const result = removeAlertById(p.alerts, id);
      return { next: { ...p, alerts: result.alerts }, result: result.removed };
    });
    if (!removed) return;
    apiDelete(`/me/alerts/${id}`).catch(() => {
      commitPersisted(persistedRef, setPersisted, (p) => ({ next: { ...p, alerts: [...p.alerts, removed] }, result: undefined }));
      showToast(SYNC_FAILED);
    });
  }, [showToast]);

  const signIn = useCallback(async (path: AuthPath, email: string, password: string) => {
    const me = await apiPost<UserRead>(path, { email, password }); // failures propagate to the dialog
    adoptSession(me);
    setAuthOpen(false);
    showToast("خوش اومدی!");
    // P1-b: a blob owned by a different account (cookie expiry is not logout) never
    // gets imported here — only anonymous or this-account data goes up.
    const { saved, alerts } = importableLists(persistedRef.current, me.id);
    try {
      adoptAccount(await apiPost<AccountState>("/me/import", { saved, alerts: alerts.map(toAlertBody) }), me.id);
    } catch {
      // ponytail: a failed import keeps this browser's lists until the next reload, which
      // replaces them with the server copy. Add a retry queue if that loss ever matters.
      showToast(SYNC_FAILED);
    }
  }, [adoptSession, adoptAccount, showToast]);

  const login = useCallback((email: string, password: string) => signIn("/auth/login", email, password), [signIn]);
  const register = useCallback((email: string, password: string) => signIn("/auth/register", email, password), [signIn]);

  const logout = useCallback(async () => {
    try { await apiPost<void>("/auth/logout", {}); } catch { showToast("خروج انجام نشد؛ دوباره امتحان کن"); return; }
    adoptSession(null);
    commitPersisted(persistedRef, setPersisted, (p) => ({ next: clearAccount(p), result: undefined }));
    setBellOpen(false);
    showToast("خارج شدی");
  }, [adoptSession, showToast]);

  const openAuth = useCallback(() => { setBellOpen(false); setAuthOpen(true); }, []);
  const closeAuth = useCallback(() => setAuthOpen(false), []);

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
    ...persisted, user, loggedIn: user !== null, authReady, authOpen, bellOpen, chatOpen, chatMessages, chatBusy, avatarAnimation, toast,
    toggleCompare, removeFromCompare, toggleSaved, addAlert, removeAlert, login, register, logout, openAuth, closeAuth, setBellOpen, setChatOpen, sendChat, showToast,
  }), [persisted, user, authReady, authOpen, bellOpen, chatOpen, chatMessages, chatBusy, avatarAnimation, toast, toggleCompare, removeFromCompare, toggleSaved, addAlert, removeAlert, login, register, logout, openAuth, closeAuth, sendChat, showToast]);

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState(): AppStateValue {
  const value = useContext(AppStateContext);
  if (!value) throw new Error("useAppState must be used inside <AppStateProvider>");
  return value;
}
