"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { clearAccount, importableLists, removeAlertById, toAlertBody, toPriceAlert, toggleSavedId, withAlertId } from "@/lib/account";
import { ApiError, apiDelete, apiGet, apiPost, apiPut } from "@/lib/api/client";
import type { AccountState, AssistantRequest, ChatDetail, ChatSummary, PriceAlertRead, UserRead } from "@/lib/api/types";
import { streamAssistant } from "@/lib/api/assistant-stream";
import type { ChatMessage, PriceAlert } from "@/lib/types";
import { toAssistantMessages } from "@/lib/chat";

export const MAX_COMPARE = 3;
export type AvatarAnimation = "idle" | "thinking" | "happy";

const STORAGE_KEY = "torobcar:v2"; // v1 held synthetic ids and is ignored
const TOAST_MS = 2200;
const HAPPY_MS = 2500;
type ChatEntry = ChatMessage & { id: string };
const GREETING: ChatEntry = { id: "greeting", role: "assistant", text: "سلام! من دستیار خرید خودروی تربم. بگو دنبال چه ماشینی هستی تا بین آگهی‌ها جست‌وجو کنم و بهترین گزینه‌ها رو پیدا کنم.", listings: [] };
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
  bellOpen: boolean; chatOpen: boolean; chatMessages: ChatEntry[]; chatBusy: boolean; avatarAnimation: AvatarAnimation; toast: string;
  chats: ChatSummary[]; activeChatId: string | null;
  startChat(): void; openChat(id: string): void; deleteChat(id: string): void;
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

export function AppStateProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const [persisted, setPersisted] = useState<Persisted>(EMPTY);
  const [hydrated, setHydrated] = useState(false);
  const [bellOpen, setBellOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatEntry[]>([GREETING]);
  const [chatBusy, setChatBusy] = useState(false);
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [recentReply, setRecentReply] = useState(false);
  const [toast, setToast] = useState("");
  const [user, setUser] = useState<UserRead | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const userRef = useRef<UserRead | null>(null); // callbacks read this, so they stay stable
  const toastTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const happyTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const persistedRef = useRef<Persisted>(EMPTY);
  const chatRef = useRef<ChatEntry[]>([GREETING]);
  const chatBusyRef = useRef(false);
  const chatControllerRef = useRef<AbortController | null>(null);
  const chatNavigationRef = useRef(0);
  const activeChatRef = useRef<string | null>(null); // sendChat reads this, so it stays a ref
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

  // The history list is a convenience, never the chat itself: a failed load leaves the
  // panel working with an empty list rather than showing an error.
  const refreshChats = useCallback(() => {
    if (!userRef.current) return;
    apiGet<ChatSummary[]>("/me/chats").then(setChats).catch(() => undefined);
  }, []);

  const startChat = useCallback(() => {
    chatNavigationRef.current += 1;
    chatControllerRef.current?.abort();
    chatBusyRef.current = false;
    setChatBusy(false);
    chatRef.current = [GREETING];
    setChatMessages(chatRef.current);
    activeChatRef.current = null; // the next question creates the chat server-side
    setActiveChatId(null);
  }, []);
  const adoptAccount = useCallback((state: AccountState, ownerId: string) => {
    commitPersisted(persistedRef, setPersisted, (p) => ({ next: { ...p, saved: state.saved, alerts: state.alerts.map(toPriceAlert), ownerId }, result: undefined }));
  }, []);

  // Who am I? Server Components stay anonymous, so the session is discovered here.
  useEffect(() => {
    if (!hydrated) return;
    let cancelled = false;
    const load = async () => {
      const me = await apiGet<UserRead>("/me");
      const [saved, alerts, stored] = await Promise.all([apiGet<string[]>("/me/saved"), apiGet<PriceAlertRead[]>("/me/alerts"), apiGet<ChatSummary[]>("/me/chats")]);
      if (cancelled) return;
      adoptSession(me);
      adoptAccount({ saved, alerts }, me.id);
      setChats(stored);
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
      chatControllerRef.current?.abort();
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
    refreshChats(); // this account's own history, never the previous visitor's
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
  }, [adoptSession, adoptAccount, refreshChats, showToast]);

  const login = useCallback((email: string, password: string) => signIn("/auth/login", email, password), [signIn]);
  const register = useCallback((email: string, password: string) => signIn("/auth/register", email, password), [signIn]);

  const logout = useCallback(async () => {
    try { await apiPost<void>("/auth/logout", {}); } catch { showToast("خروج انجام نشد؛ دوباره امتحان کن"); return; }
    adoptSession(null);
    commitPersisted(persistedRef, setPersisted, (p) => ({ next: clearAccount(p), result: undefined }));
    setBellOpen(false);
    // The transcript is this account's, so it leaves with the session — the next
    // person on a shared browser must not find it.
    setChats([]);
    startChat();
    showToast("خارج شدی");
  }, [adoptSession, startChat, showToast]);

  const openAuth = useCallback(() => { setBellOpen(false); setAuthOpen(true); }, []);
  const closeAuth = useCallback(() => setAuthOpen(false), []);

  const appendChat = useCallback((message: ChatMessage) => {
    chatRef.current = [...chatRef.current, { ...message, id: crypto.randomUUID() }];
    setChatMessages(chatRef.current);
  }, []);

  // A reply carries the chat it was stored in: the first answer of a new conversation
  // names a chat this browser has not seen, so the history list is re-read.
  const adoptChat = useCallback((chatId: string | null) => {
    if (chatId === null || chatId === activeChatRef.current) return;
    activeChatRef.current = chatId;
    setActiveChatId(chatId);
    refreshChats();
  }, [refreshChats]);

  const openChat = useCallback((id: string) => {
    if (chatBusyRef.current) return;
    const navigation = ++chatNavigationRef.current;
    apiGet<ChatDetail>(`/me/chats/${id}`)
      .then((chat) => {
        if (!mountedRef.current || navigation !== chatNavigationRef.current) return;
        chatRef.current = chat.messages.map(({ role, text, listings }) => ({ role, text, listings, id: crypto.randomUUID() }));
        setChatMessages(chatRef.current);
        activeChatRef.current = chat.id;
        setActiveChatId(chat.id);
      })
      .catch(() => { if (navigation === chatNavigationRef.current) showToast("گفتگو باز نشد؛ دوباره امتحان کن"); });
  }, [showToast]);

  const deleteChat = useCallback((id: string) => {
    setChats((current) => current.filter((chat) => chat.id !== id));
    if (activeChatRef.current === id) startChat();
    apiDelete(`/me/chats/${id}`).catch(() => { showToast(SYNC_FAILED); refreshChats(); });
  }, [startChat, refreshChats, showToast]);

  // The assistant itself stays stateless: every call carries the recent history, the
  // compare ids and — for a logged-in visitor — which stored chat to append to.
  const sendChat = useCallback((raw: string) => {
    const text = raw.trim();
    if (!text || chatBusyRef.current) return;
    chatNavigationRef.current += 1;
    chatBusyRef.current = true;
    setChatBusy(true);
    appendChat({ role: "user", text, listings: [] });
    const body: AssistantRequest = { messages: toAssistantMessages(chatRef.current), compare_ids: persistedRef.current.compare, chat_id: activeChatRef.current };
    const controller = new AbortController();
    chatControllerRef.current = controller;
    const replyIndex = chatRef.current.length;
    appendChat({ role: "assistant", text: "", listings: [], status: "streaming" });
    const updateReply = (message: ChatMessage) => {
      if (!mountedRef.current || controller.signal.aborted) return;
      chatRef.current = chatRef.current.map((current, index) => index === replyIndex ? { ...message, id: current.id } : current);
      setChatMessages(chatRef.current);
    };
    streamAssistant(body, (text) => updateReply({ role: "assistant", text, listings: [], status: "streaming" }), controller.signal)
      .then((reply) => {
        if (!mountedRef.current || controller.signal.aborted) return;
        adoptChat(reply.chat_id);
        updateReply({ role: "assistant", text: reply.text, listings: reply.listings });
        setRecentReply(true);
        clearTimeout(happyTimer.current);
        happyTimer.current = setTimeout(() => setRecentReply(false), HAPPY_MS);
      })
      .catch((error: unknown) => {
        if (!mountedRef.current || controller.signal.aborted) return;
        const limited = error instanceof ApiError && error.code === "anonymous_chat_limit";
        if (limited) setAuthOpen(true);
        updateReply({ role: "assistant", text: error instanceof ApiError && (limited || error.status === 422) ? error.message : CHAT_UNAVAILABLE, listings: [], status: "failed" });
      })
      .finally(() => {
        if (!mountedRef.current || controller.signal.aborted) return;
        chatBusyRef.current = false;
        setChatBusy(false);
        chatControllerRef.current = null;
      });
  }, [appendChat, adoptChat]);

  const restingAnimation: AvatarAnimation = recentReply ? "happy" : "idle";
  const avatarAnimation: AvatarAnimation = chatBusy ? "thinking" : restingAnimation;

  const value = useMemo<AppStateValue>(() => ({
    ...persisted, user, loggedIn: user !== null, authReady, authOpen, bellOpen, chatOpen, chatMessages, chatBusy, avatarAnimation, toast, chats, activeChatId,
    toggleCompare, removeFromCompare, toggleSaved, addAlert, removeAlert, login, register, logout, openAuth, closeAuth, setBellOpen, setChatOpen, sendChat, showToast, startChat, openChat, deleteChat,
  }), [persisted, user, authReady, authOpen, bellOpen, chatOpen, chatMessages, chatBusy, avatarAnimation, toast, chats, activeChatId, toggleCompare, removeFromCompare, toggleSaved, addAlert, removeAlert, login, register, logout, openAuth, closeAuth, sendChat, showToast, startChat, openChat, deleteChat]);

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState(): AppStateValue {
  const value = useContext(AppStateContext);
  if (!value) throw new Error("useAppState must be used inside <AppStateProvider>");
  return value;
}
