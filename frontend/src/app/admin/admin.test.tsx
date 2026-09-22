import { test, expect, spyOn } from "bun:test";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { network, renderApp, user, json, failure } from "../../../test/support";
import { navigation } from "../../../test/setup";
import AdminLayout from "./layout";
import AdminDashboard from "./page";
import AdminUsers from "./users/page";
import AdminAudit from "./audit/page";
import { adminDate } from "./ui";
import { AppChrome } from "@/components/AppChrome";

const row = { ...user, id: "other", email: "other@example.com", role: "user", last_login_at: "2026-09-01" };
const audit = { id: "audit1", actor_id: user.id, actor_email: user.email, target_id: row.id, target_email: row.email, action: "user_deleted", summary: { email: row.email }, created_at: "2026-09-01T00:00:00Z" };
const stats = { users_total: 10, users_active: 8, admins_active: 2, listings_total: 50, newest_listing_fetched_at: "2026-09-01T00:00:00Z", recent_audit: [audit] };
const change = (element: HTMLElement, value: string) => fireEvent.change(element, { target: { value } });
function adminNetwork(handler: Parameters<typeof network>[0] = () => undefined) {
  return network((url, init) => {
    const override = handler(url, init);
    if (override) return override;
    if (url.pathname.endsWith("/me")) return json(user);
    if (url.pathname.endsWith("/admin/stats")) return json(stats);
    if (url.pathname.endsWith("/admin/users")) return json({ items: [row], total: 31 });
    if (url.pathname.endsWith("/admin/audit")) return json({ items: [audit], total: 25 });
    if (url.pathname.endsWith("/auth/reauth") || url.pathname.endsWith("/auth/logout")) return new Response(null, { status: 204 });
    if (url.pathname.includes("/admin/users/")) return new Response(null, { status: 204 });
  });
}
async function submitReauth() {
  const dialog = screen.getAllByRole("dialog").at(-1)!;
  change(dialog.querySelector("input")!, "password");
  fireEvent.submit(dialog.querySelector("form")!);
}

test("admin shell redirects guests and denies non-admin accounts", async () => {
  network();
  navigation.pathname = "/admin";
  const guest = await renderApp(<AdminLayout>secret</AdminLayout>);
  expect(navigation.replace).toHaveBeenCalledWith("/login?next=%2Fadmin");
  guest.unmount();
  network(url => url.pathname.endsWith("/me") ? json({ ...user, role: "user" }) : undefined);
  await renderApp(<AdminLayout>secret</AdminLayout>);
  expect(screen.getByRole("heading", { name: "دسترسی ندارید" })).toBeTruthy();
});

test("admin dashboard displays statistics, navigation and logout controls", async () => {
  adminNetwork();
  navigation.pathname = "/admin";
  const app = await renderApp(<AppChrome><AdminLayout><AdminDashboard /></AdminLayout></AppChrome>);
  await screen.findByText("کل کاربران");
  expect(screen.getByRole("navigation", { name: "منوی مدیریت" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "به‌روزرسانی" }));
  await screen.findByText("کل کاربران");
  fireEvent.click(screen.getAllByRole("button", { name: "خروج از حساب" })[0]);
  await waitFor(() => expect(app.state().loggedIn).toBe(false));
  expect(adminDate(null)).toBe("—");
  expect(adminDate("bad date")).toBe("—");
});

test.each(["dashboard", "audit", "users"])("admin %s retries reads after reauthentication and cancellation", async page => {
  let locked = true;
  let badPassword = true;
  adminNetwork((url) => {
    if (url.pathname.includes("/admin/")) return locked ? failure(403, "admin_reauth_required") : undefined;
    if (url.pathname.endsWith("/auth/reauth")) {
      if (badPassword) return failure(401, "invalid_credentials");
      locked = false;
      return new Response(null, { status: 204 });
    }
  });
  const component = page === "dashboard" ? <AdminDashboard /> : page === "audit" ? <AdminAudit /> : <AdminUsers />;
  await renderApp(component);
  await screen.findByRole("dialog");
  fireEvent.click(screen.getByRole("button", { name: "انصراف" }));
  fireEvent.click(screen.getByRole("button", { name: "تلاش دوباره" }));
  await screen.findByRole("dialog");
  await submitReauth();
  await screen.findByText("رمز اشتباه است");
  badPassword = false;
  await submitReauth();
  await waitFor(() => expect(screen.queryByRole("dialog")?.tagName).toBeUndefined());
  expect(locked).toBe(false);
});

test("user filters, paging and empty results remain usable", async () => {
  let empty = false;
  const fetcher = adminNetwork(url => url.pathname.endsWith("/admin/users") && empty ? json({ items: [], total: 0 }) : undefined);
  await renderApp(<AdminUsers />);
  await screen.findByRole("button", { name: `مدیریت ${row.email}` });
  fireEvent.click(screen.getByRole("button", { name: "بعدی" }));
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).includes("offset=15"))).toBe(true));
  fireEvent.click(screen.getByRole("button", { name: "قبلی" }));
  change(screen.getByLabelText("جست‌وجوی ایمیل"), "missing");
  empty = true;
  fireEvent.click(screen.getByRole("button", { name: "جست‌وجو" }));
  await screen.findByText("کاربری با این مشخصات پیدا نشد");
  change(screen.getByLabelText("نقش"), "admin");
  change(screen.getByLabelText("وضعیت"), "inactive");
  fireEvent.click(screen.getAllByRole("button", { name: "پاک کردن فیلترها" })[0]);
  await screen.findByText("کاربری برای نمایش وجود ندارد");
});

test.each(["status", "role", "password", "delete"])("admin confirms %s action", async action => {
  const fetcher = adminNetwork();
  await renderApp(<AdminUsers />);
  fireEvent.click(await screen.findByRole("button", { name: `مدیریت ${row.email}` }));
  const name = { status: /غیرفعال کردن حساب/, role: /ارتقا به مدیر/, password: /بازنشانی رمز عبور/, delete: /حذف حساب کاربری/ }[action]!;
  fireEvent.click(screen.getByRole("button", { name }));
  fireEvent.click(screen.getByRole("button", { name: "بازگشت" }));
  fireEvent.click(screen.getByRole("button", { name }));
  if (action === "password") change(screen.getByLabelText(/رمز عبور جدید/), "new password");
  fireEvent.click(screen.getByRole("button", { name: /تأیید/ }));
  await screen.findByRole("button", { name: "بستن پیام" });
  expect(fetcher.mock.calls.some(([url, init]) => String(url).includes("/admin/users/other") && init?.method !== "GET")).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "بستن پیام" }));
  fireEvent.click(await screen.findByRole("button", { name: `مدیریت ${row.email}` }));
  fireEvent(screen.getByRole("dialog"), new Event("cancel", { bubbles: false, cancelable: true }));
  expect(screen.queryByRole("dialog")?.tagName).toBeUndefined();
});

test("admin action retries after reauth, handles failure and supports cancel", async () => {
  let mode = "locked";
  adminNetwork((url) => {
    if (url.pathname.includes("/admin/users/")) return failure(mode === "locked" ? 403 : 409, mode === "locked" ? "admin_reauth_required" : "last_admin");
    if (url.pathname.endsWith("/auth/reauth")) { mode = "failed"; return new Response(null, { status: 204 }); }
  });
  await renderApp(<AdminUsers />);
  const open = async () => {
    fireEvent.click(await screen.findByRole("button", { name: `مدیریت ${row.email}` }));
    fireEvent.click(screen.getByRole("button", { name: /حذف حساب کاربری/ }));
    fireEvent.click(screen.getByRole("button", { name: /تأیید/ }));
    await screen.findByRole("button", { name: "انصراف" });
  };
  await open();
  fireEvent.click(screen.getByRole("button", { name: "انصراف" }));
  fireEvent.click(screen.getByRole("button", { name: "بستن" }));
  await open();
  await submitReauth();
  await screen.findByRole("button", { name: "بستن پیام" });
  expect(screen.queryByRole("dialog")?.tagName).toBeUndefined();
});

test("deleting the last row on page two returns to the previous page", async () => {
  const fetcher = adminNetwork();
  await renderApp(<AdminUsers />);
  await screen.findByRole("button", { name: `مدیریت ${row.email}` });
  fireEvent.click(screen.getByRole("button", { name: "بعدی" }));
  fireEvent.click(await screen.findByRole("button", { name: `مدیریت ${row.email}` }));
  fireEvent.click(screen.getByRole("button", { name: /حذف حساب کاربری/ }));
  fireEvent.click(screen.getByRole("button", { name: /تأیید/ }));
  await screen.findByRole("button", { name: "بستن پیام" });
  await waitFor(() => expect(fetcher.mock.calls.filter(([url]) => String(url).includes("offset=0")).length).toBeGreaterThan(1));
});

test("resetting own password navigates to login after token revocation", async () => {
  adminNetwork(url => url.pathname.endsWith("/admin/users") ? json({ items: [{ ...row, ...user }], total: 1 }) : undefined);
  const assign = spyOn(window.location, "assign").mockImplementation(() => undefined);
  try {
    await renderApp(<AdminUsers />);
    fireEvent.click(await screen.findByRole("button", { name: `مدیریت ${user.email}` }));
    fireEvent.click(screen.getByRole("button", { name: /بازنشانی رمز عبور/ }));
    change(screen.getByLabelText(/رمز عبور جدید/), "new password");
    fireEvent.click(screen.getByRole("button", { name: /تأیید/ }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("/login?next=%2Fadmin%2Fusers"));
  } finally { assign.mockRestore(); }
});

test("audit filter and pagination preserve the chosen action", async () => {
  const fetcher = adminNetwork();
  await renderApp(<AdminAudit />);
  await screen.findByText(/other@example.com/);
  change(screen.getByLabelText("نوع فعالیت"), "user_deleted");
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).includes("action=user_deleted"))).toBe(true));
  fireEvent.click(screen.getByRole("button", { name: "بعدی" }));
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).includes("offset=20"))).toBe(true));
});

test("empty audit history is explicit", async () => {
  adminNetwork(url => url.pathname.endsWith("/admin/audit") ? json({ items: [], total: 0 }) : undefined);
  await renderApp(<AdminAudit />);
  expect(await screen.findByText("هنوز فعالیتی ثبت نشده")).toBeTruthy();
});

test("reauthentication reports malformed server responses", async () => {
  adminNetwork(url => {
    if (url.pathname.endsWith("/admin/stats")) return failure(403, "admin_reauth_required");
    if (url.pathname.endsWith("/auth/reauth")) return new Response("malformed JSON");
  });
  await renderApp(<AdminDashboard />);
  await screen.findByRole("dialog");
  await submitReauth();
  expect(await screen.findByText("سرویس جست‌وجو در دسترس نیست")).toBeTruthy();
});
