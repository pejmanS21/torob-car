import { test, expect, spyOn } from "bun:test";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { network, renderApp, listing, stats, json, failure, user, search } from "../../test/support";
import { navigation, markers, map, avatarController } from "../../test/setup";
import { cardOf } from "@/lib/view";
import { ListingScreen } from "./ListingScreen";
import { ModelScreen } from "./ModelScreen";
import ListingsMap from "./ListingsMap";
import { HomeSearch } from "./HomeSearch";
import { HeaderSearch } from "./HeaderSearch";
import { AuthDialog } from "./AuthDialog";
import { AppChrome } from "./AppChrome";
import { Toast } from "./Toast";
import { Avatar } from "./Avatar";
import { ListingCard } from "./ListingCard";
import { ChatPanel } from "./ChatPanel";
import { AlertsDropdown } from "./AlertsDropdown";
import { CardSkeletons } from "./Skeleton";
import ComparePage from "../app/compare/page";
import EstimatePage from "../app/estimate/page";

const change = (element: HTMLElement, value: string) => fireEvent.change(element, { target: { value } });

test("search forms preserve Persian queries and accept empty searches", () => {
  const view = render(<HomeSearch />);
  for (const text of ["دنا پلاس", ""]) {
    change(screen.getByRole("textbox"), text);
    fireEvent.submit(screen.getByRole("search"));
    expect(navigation.push).toHaveBeenLastCalledWith(text ? `/results?q=${encodeURIComponent(text)}` : "/results");
  }
  view.rerender(<HeaderSearch variant="desktop" />);
  for (const text of ["پژو", ""]) {
    change(screen.getByRole("textbox"), text);
    fireEvent.submit(screen.getByRole("search"));
    expect(navigation.push).toHaveBeenLastCalledWith(text ? `/results?q=${encodeURIComponent(text)}` : "/results");
  }
});

test("listing detail supports gallery, compare, save and source handoff", async () => {
  network();
  const open = spyOn(window, "open").mockImplementation(() => null);
  try {
    const app = await renderApp(<ListingScreen detail={{ ...listing, image_urls: ["/one.jpg", "/two.jpg"] }} similar={search.items} />);
    fireEvent.click(screen.getByRole("button", { name: "عکس ۲" }));
    expect(screen.getByRole("button", { name: "عکس ۲" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "+ مقایسه" }));
    expect(app.state().compare).toContain(listing.id);
    fireEvent.click(screen.getByTitle("نشان‌کردن"));
    expect(app.state().saved).toContain(listing.id);
    const source = screen.getByRole("link", { name: "مشاهده آگهی" });
    fireEvent.click(source, { ctrlKey: true });
    fireEvent.click(source);
    fireEvent.click(source);
    expect(screen.getByRole("dialog")).toBeTruthy();
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 1150)); });
    expect(open).toHaveBeenCalledWith(listing.url, "_blank", "noopener");
    expect(screen.queryByRole("dialog")?.tagName).toBeUndefined();
  } finally { open.mockRestore(); }
});

test("listing cards offer compare and bookmark shortcuts", async () => {
  network();
  await renderApp(<ListingCard card={cardOf(listing)} />);
  expect(screen.getByRole("link").getAttribute("href")).toBe(`/listing/${listing.id}`);
});

test("model summary opens auth for alerts", async () => {
  network();
  const app = await renderApp(<ModelScreen stats={stats} />);
  fireEvent.click(screen.getByRole("button", { name: /هشدار قیمت زیر/ }));
  expect(app.state().authOpen).toBe(true);
  expect(screen.getByRole("heading", { name: stats.model })).toBeTruthy();
});

test("maps fit pins, navigate from markers and show approximate single locations", () => {
  const view = render(<ListingsMap listings={[{ ...listing, lat: 35, lng: 51 }]} />);
  expect(map.fitBounds).toHaveBeenCalled();
  act(() => markers[0].click?.());
  expect(navigation.push).toHaveBeenLastCalledWith(`/listing/${listing.id}`);
  view.rerender(<ListingsMap listings={[{ ...listing, lat: 35, lng: 51 }]} single />);
  expect(map.setView).toHaveBeenCalledWith([35, 51], 13);
  view.rerender(<ListingsMap listings={[{ ...listing, lat: null }]} />);
  expect(map.remove).toHaveBeenCalled();
});

test("avatar changes animation and falls back when loading fails", async () => {
  network();
  const view = render(<Avatar size={24} />);
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)); });
  view.rerender(<Avatar size={24} animation="happy" />);
  expect(avatarController.play).toHaveBeenCalledWith("happy");
  network(() => failure());
  const warn = spyOn(console, "warn").mockImplementation(() => undefined);
  try {
    view.rerender(<Avatar size={24} body="#000000" />);
    expect(await screen.findByRole("img", { name: "دستیار" })).toBeTruthy();
  } finally { warn.mockRestore(); }
});

test("chrome opens alerts, chat and login; outside click closes alerts", async () => {
  network();
  navigation.pathname = "/results";
  const app = await renderApp(<><AppChrome><p>content</p></AppChrome><AuthDialog /><Toast /></>);
  fireEvent.click(screen.getByRole("button", { name: "هشدارها" }));
  expect(app.state().bellOpen).toBe(true);
  fireEvent.click(document.body);
  expect(app.state().bellOpen).toBe(false);
  fireEvent.click(screen.getAllByRole("button", { name: "دستیار" })[0]);
  expect(app.state().chatOpen).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "بستن" }));
  fireEvent.click(screen.getByRole("button", { name: "ورود" }));
  expect(app.state().authOpen).toBe(true);
  act(() => app.state().showToast("پیام"));
  expect(screen.getByRole("status").textContent).toBe("پیام");
});

test("auth dialog handles duplicate email and login retry", async () => {
  let fail = true;
  network((url) => {
    if (url.pathname.endsWith("/auth/register")) return failure(409, "email_taken");
    if (url.pathname.endsWith("/auth/login")) return fail ? failure(422, "invalid_search", "bad input") : json(user);
  });
  const app = await renderApp(<AuthDialog />);
  act(() => app.state().openAuth());
  fireEvent.click(screen.getByRole("tab", { name: "ثبت‌نام" }));
  change(screen.getByLabelText("ایمیل"), user.email);
  change(screen.getByLabelText("رمز عبور"), "password123");
  const submit = () => fireEvent.submit(screen.getByLabelText("ایمیل").closest("form")!);
  submit();
  await screen.findByRole("alert");
  expect(screen.getByRole("tab", { name: "ورود" }).getAttribute("aria-selected")).toBe("true");
  submit();
  await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("bad input"));
  fail = false;
  submit();
  await waitFor(() => expect(app.state().loggedIn).toBe(true));
  expect(app.state().authOpen).toBe(false);
  act(() => app.state().openAuth());
  fireEvent.click(screen.getByRole("button", { name: "بستن" }));
  expect(app.state().authOpen).toBe(false);
});

test("compare page removes selected listings", async () => {
  network((url) => url.pathname.endsWith("/listings") ? json([listing]) : undefined);
  const app = await renderApp(<ComparePage />);
  expect(screen.getByText(/هنوز چیزی برای مقایسه/)).toBeTruthy();
  act(() => app.state().toggleCompare(listing.id));
  fireEvent.click(await screen.findByRole("button", { name: "حذف از مقایسه" }));
  expect(app.state().compare).toEqual([]);
});

test("estimate form resolves model and years, submits details and retries failures", async () => {
  let fail = true;
  network((url) => url.pathname.endsWith("/estimates") && fail ? failure(422, "no_comparables", "داده کافی نیست") : undefined);
  await renderApp(<EstimatePage />);
  const form = screen.getByRole("button", { name: "تخمین بزن" }).closest("form")!;
  fireEvent.submit(form);
  const suggestions = await screen.findByRole("list", { name: "مدل‌های پیشنهادی" });
  fireEvent.click(suggestions.querySelector("button")!);
  const year = screen.getByLabelText("سال ساخت") as HTMLSelectElement;
  await waitFor(() => expect(year.disabled).toBe(false));
  change(year, year.options[1].value);
  change(screen.getByLabelText(/قیمت پیشنهادی/), "۶۵۰");
  for (const slider of screen.getAllByRole("slider")) change(slider, "5");

  fireEvent.submit(form);
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("داده کافی نیست"));
  fail = false;
  fireEvent.submit(form);
  expect(await screen.findByText("چطور حساب شد؟")).toBeTruthy();
  change(screen.getByLabelText("برند و مدل"), "دیگر");
  change(screen.getByLabelText("دسته"), "motorcycle");
  expect((screen.getByRole("button", { name: "تخمین بزن" }) as HTMLButtonElement).disabled).toBe(true);
});

test("chat history can resume, delete, submit a message and start over", async () => {
  const stored = { id: "c1", title: "گفتگوی پژو", updated_at: "2026-09-01", messages: [{ role: "assistant", text: "پیشنهاد", listings: [listing] }] };
  network((url) => {
    if (url.pathname.endsWith("/me")) return json(user);
    if (url.pathname.endsWith("/me/chats")) return json([stored]);
    if (url.pathname.endsWith("/me/chats/c1")) return json(stored);
    if (url.pathname.endsWith("/assistant/stream")) return failure();
  });
  const app = await renderApp(<ChatPanel />);
  act(() => app.state().setChatOpen(true));
  fireEvent.click(screen.getByRole("button", { name: /پیشین/ }));
  fireEvent.click(screen.getByText("گفتگوی پژو").closest("button")!);
  await screen.findByText("پیشنهاد");
  change(screen.getByRole("textbox", { name: "پیام" }), "پژو");
  fireEvent.click(screen.getByRole("button", { name: "ارسال" }));
  await waitFor(() => expect(app.state().chatBusy).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "گفتگوی جدید +" }));
  expect(app.state().activeChatId).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /پیشین/ }));
  fireEvent.click(screen.getByRole("button", { name: "حذف گفتگوی پژو" }));
  expect(app.state().chats).toEqual([]);
});

test("alerts count matches and remove saved alerts", async () => {
  network((url) => {
    if (url.pathname.endsWith("/me")) return json(user);
    if (url.pathname.endsWith("/me/alerts")) return json([{ id: "a", title: "پژو", threshold_toman: 500000000, search_params: {} }]);
    if (url.pathname.endsWith("/me/alerts/a")) return new Response(null, { status: 204 });
  });
  const app = await renderApp(<AlertsDropdown />);
  await screen.findByText(/الان .* آگهی زیر این قیمت/);
  fireEvent.click(screen.getByTitle("حذف"));
  expect(app.state().alerts).toEqual([]);
});

test("loading cards provide accessible placeholders", () => {
  render(<CardSkeletons count={3} />);
  expect(screen.getAllByLabelText("در حال بارگذاری")).toHaveLength(3);
});

test("signed-in chrome exposes account actions and mobile navigation", async () => {
  network(url => {
    if (url.pathname.endsWith("/me")) return json(user);
    if (url.pathname.endsWith("/auth/logout")) return new Response(null, { status: 204 });
  });
  const app = await renderApp(<AppChrome>content</AppChrome>);
  const menu = document.querySelector("details")!;
  fireEvent.click(menu.querySelector("summary")!);
  menu.open = true;
  expect(screen.getByRole("link", { name: "پنل مدیریت" })).toBeTruthy();
  fireEvent.click(screen.getAllByRole("button", { name: "دستیار" }).at(-1)!);
  expect(app.state().chatOpen).toBe(true);
  const nav = screen.getByRole("navigation", { name: "ناوبری اصلی" });
  fireEvent.click(nav.querySelector("a")!);
  expect(app.state().chatOpen).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "خروج" }));
  await waitFor(() => expect(app.state().loggedIn).toBe(false));
});
