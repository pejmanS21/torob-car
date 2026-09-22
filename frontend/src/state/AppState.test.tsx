import { describe, test, expect } from "bun:test";
import { act, render, waitFor } from "@testing-library/react";
import { useAppState } from "./AppState";
import { renderApp, network, json, failure, user, account, listing, deferred } from "../../test/support";

const alert = { title: "پژو", threshold: 500000000, params: { q: "پژو" } };
const storedAlert = { id: "a1", title: alert.title, threshold_toman: alert.threshold, search_params: alert.params };
const chat = { id: "chat1", title: "پژو", updated_at: "2026-09-01T00:00:00Z", messages: [{ role: "assistant", text: "سلام دوباره", listings: [listing] }] };
const stream = () => new Response(`event: text\ndata: ${JSON.stringify({ text: "سلام" })}\n\nevent: done\ndata: ${JSON.stringify({ text: "پاسخ کامل", listings: [listing], chat_id: "chat1" })}\n\n`, { headers: { "content-type": "text/event-stream" } });

describe("account state", () => {
  test("context requires a provider", () => {
    function Orphan() { useAppState(); return null; }
    expect(() => render(<Orphan />)).toThrow("AppStateProvider");
  });
  test("hydrates safely and limits compare additions within one tick", async () => {
    network();
    localStorage.setItem("torobcar:v2", "broken");
    const app = await renderApp(null);
    act(() => { for (const id of ["a", "b", "c", "d"]) app.state().toggleCompare(id); });
    expect(app.state().compare).toEqual(["a", "b", "c"]);
    expect(app.state().toast).toContain("سه");
    act(() => { app.state().toggleCompare("a"); app.state().removeFromCompare("b"); app.state().toggleSaved("saved"); });
    expect(app.state().compare).toEqual(["c"]);
    expect(app.state().saved).toEqual(["saved"]);
    act(() => { app.state().toggleSaved("saved"); app.state().addAlert(alert); });
    expect(app.state().saved).toEqual([]);
    expect(app.state().authOpen).toBe(true);
    act(() => app.state().closeAuth());
    expect(app.state().authOpen).toBe(false);
    act(() => { app.state().setBellOpen(true); app.state().openAuth(); app.state().setChatOpen(true); });
    expect(app.state().bellOpen).toBe(false);
    expect(app.state().chatOpen).toBe(true);
  });
  test("restores valid local lists and filters malformed alerts", async () => {
    network();
    localStorage.setItem("torobcar:v2", JSON.stringify({ compare: ["a", "b", "c", "d"], saved: ["s"], alerts: [alert, null, {}], ownerId: "old" }));
    const app = await renderApp(null);
    expect(app.state().alerts).toEqual([alert]);
    expect(app.state().compare).toHaveLength(3);
    expect(app.state().ownerId).toBe("old");
  });
  test("loads the session and rolls back failed optimistic mutations", async () => {
    let fail = false;
    network((url, init) => {
      if (url.pathname.endsWith("/me")) return json(user);
      if (init?.method && init.method !== "GET") return fail ? failure() : json(storedAlert);
    });
    const app = await renderApp(null);
    expect(app.state().loggedIn).toBe(true);
    act(() => app.state().toggleSaved("s"));
    await waitFor(() => expect(app.state().saved).toEqual(["s"]));
    act(() => app.state().toggleSaved("s"));
    expect(app.state().saved).toEqual([]);
    act(() => app.state().addAlert(alert));
    await waitFor(() => expect(app.state().alerts[0]?.id).toBe("a1"));
    fail = true;
    act(() => { app.state().removeAlert("missing"); app.state().removeAlert("a1"); });
    await waitFor(() => expect(app.state().alerts).toHaveLength(1));
    act(() => { app.state().addAlert({ ...alert, title: "failed" }); app.state().toggleSaved("failed"); });
    await waitFor(() => { expect(app.state().alerts).toHaveLength(1); expect(app.state().saved).toEqual([]); });
    fail = false;
    act(() => app.state().removeAlert("a1"));
    await waitFor(() => expect(app.state().alerts).toEqual([]));
  });
  test("login imports anonymous lists and logout clears private state", async () => {
    let failImport = true;
    let failLogout = true;
    const fetcher = network((url) => {
      if (/auth\/(login|register)$/.test(url.pathname)) return json(user);
      if (url.pathname.endsWith("/me/import")) return failImport ? failure() : json(account);
      if (url.pathname.endsWith("/auth/logout")) return failLogout ? failure() : new Response(null, { status: 204 });
    });
    const app = await renderApp(null);
    await act(async () => { await app.state().login(user.email, "password"); });
    expect(app.state().loggedIn).toBe(true);
    expect(app.state().toast).toContain("ذخیره نشد");
    await act(async () => { await app.state().logout(); });
    expect(app.state().loggedIn).toBe(true);
    failImport = false;
    await act(async () => { await app.state().register(user.email, "password"); });
    expect(app.state().ownerId).toBe(user.id);
    failLogout = false;
    await act(async () => { await app.state().logout(); });
    expect(app.state().loggedIn).toBe(false);
    expect(app.state().ownerId).toBeNull();
    expect(fetcher.mock.calls.some(([url]) => String(url).includes("/me/import"))).toBe(true);
  });
});

describe("chat state", () => {
  test("streams a reply, resumes history, and resets after deleting the active chat", async () => {
    network((url) => {
      if (url.pathname.endsWith("/me")) return json(user);
      if (url.pathname.endsWith("/assistant/stream")) return stream();
      if (url.pathname.endsWith("/me/chats/chat1")) return json(chat);
      if (url.pathname.endsWith("/me/chats")) return json([chat]);
    });
    const app = await renderApp(null);
    act(() => { app.state().sendChat(" "); app.state().sendChat("پژو"); app.state().sendChat("duplicate"); app.state().openChat("chat1"); });
    await waitFor(() => expect(app.state().chatBusy).toBe(false));
    expect(app.state().chatMessages.at(-1)?.text).toBe("پاسخ کامل");
    expect(app.state().activeChatId).toBe("chat1");
    expect(app.state().avatarAnimation).toBe("happy");
    act(() => app.state().openChat("chat1"));
    await waitFor(() => expect(app.state().chatMessages[0].text).toBe("سلام دوباره"));
    act(() => app.state().deleteChat("chat1"));
    expect(app.state().activeChatId).toBeNull();
    expect(app.state().chats).toEqual([]);
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 2550)); });
    expect(app.state().avatarAnimation).toBe("idle");
  });
  test.each([[429, "anonymous_chat_limit"], [422, "invalid_search"], [503, "unavailable"]])("handles assistant failure %s", async (status, code) => {
    network((url) => url.pathname.endsWith("/assistant/stream") ? failure(status, code, "خطا") : undefined);
    const app = await renderApp(null);
    act(() => app.state().sendChat("پژو"));
    await waitFor(() => expect(app.state().chatBusy).toBe(false));
    expect(app.state().chatMessages.at(-1)?.status).toBe("failed");
    expect(app.state().authOpen).toBe(code === "anonymous_chat_limit");
  });
  test("failed history operations notify and stale navigation does not replace a new chat", async () => {
    const pending = deferred<Response>();
    network((url) => {
      if (url.pathname.endsWith("/me/chats/slow")) return pending.promise;
      if (url.pathname.includes("/me/chats/")) return failure();
    });
    const app = await renderApp(null);
    act(() => app.state().openChat("missing"));
    await waitFor(() => expect(app.state().toast).toContain("باز نشد"));
    act(() => app.state().deleteChat("missing"));
    await waitFor(() => expect(app.state().toast).toContain("ذخیره نشد"));
    act(() => { app.state().openChat("slow"); app.state().startChat(); });
    await act(async () => pending.resolve(json(chat)));
    expect(app.state().activeChatId).toBeNull();
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 2250)); });
    expect(app.state().toast).toBe("");
  });
  test("starting over cancels an outstanding assistant response", async () => {
    const pending = deferred<Response>();
    network((url) => url.pathname.endsWith("/assistant/stream") ? pending.promise : undefined);
    const app = await renderApp(null);
    act(() => { app.state().sendChat("پژو"); app.state().startChat(); });
    await act(async () => pending.resolve(stream()));
    expect(app.state().chatBusy).toBe(false);
    expect(app.state().chatMessages).toHaveLength(1);
  });
});
