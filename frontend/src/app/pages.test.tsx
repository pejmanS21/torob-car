import { test, expect, mock, spyOn } from "bun:test";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { network, renderApp, failure, json, user } from "../../test/support";
import { navigation } from "../../test/setup";
import HomePage from "./page";
import RootLayout from "./layout";
import Loading from "./loading";
import NotFound from "./not-found";
import RouteError from "./error";
import ListingPage from "./listing/[id]/page";
import ModelPage from "./model/[model]/page";
import ResultsPage from "./results/page";
import LoginPage from "./login/page";
import { sourceLabelFromUrl } from "@/lib/url";

test("server pages render fetched catalog, listing and market data", async () => {
  network();
  render(await HomePage());
  expect(screen.getByRole("heading").textContent).toContain("ماشین");
  await renderApp(await ListingPage({ params: Promise.resolve({ id: "test" }) }));
  await renderApp(await ModelPage({ params: Promise.resolve({ model: "پژو" }) }));
  expect(screen.getAllByRole("heading").length).toBeGreaterThan(3);
});

test.each([404, 422, 503])("listing failures route correctly: %s", async status => {
  network(() => failure(status));
  expect(ListingPage({ params: Promise.resolve({ id: "bad" }) })).rejects.toThrow(status === 503 ? "خطای سرویس" : "NEXT_NOT_FOUND");
});

test.each([404, 503])("model failures route correctly: %s", async status => {
  network(() => failure(status));
  expect(ModelPage({ params: Promise.resolve({ model: "bad" }) })).rejects.toThrow(status === 404 ? "NEXT_NOT_FOUND" : "خطای سرویس");
});

test("unavailable similar listings leave the detail visible", async () => {
  network(url => url.pathname.endsWith("/similar") ? failure() : undefined);
  await renderApp(await ListingPage({ params: Promise.resolve({ id: "test" }) }));
  expect(screen.getByRole("link", { name: "مشاهده آگهی" })).toBeTruthy();
});

test("root document, loading and missing pages preserve navigation and accessibility", () => {
  navigation.pathname = "/admin";
  const markup = renderToStaticMarkup(<RootLayout><p>content</p></RootLayout>);
  expect(markup).toContain('lang="fa"');
  expect(markup).toContain("content");
  const view = render(<Loading />);
  expect(screen.getByLabelText("در حال بارگذاری")).toBeTruthy();
  view.rerender(<NotFound />);
  expect(screen.getByRole("link").getAttribute("href")).toBe("/");
});

test("route errors log and expose a retry action", () => {
  const log = spyOn(console, "error").mockImplementation(() => undefined);
  const retry = mock(() => undefined);
  try {
    render(<RouteError error={new Error("down")} retry={retry} />);
    fireEvent.click(screen.getByRole("button"));
    expect(retry).toHaveBeenCalled();
    expect(log).toHaveBeenCalled();
  } finally { log.mockRestore(); }
});

test("results page loads facets and opens its mobile filters", async () => {
  network();
  await renderApp(<ResultsPage />);
  await screen.findByRole("button", { name: /هشدار قیمت/ });
  fireEvent.click(screen.getByRole("button", { name: "فیلترها" }));
  expect(document.body.style.overflow).toBe("hidden");
});

test("login page reports failure and navigates after a successful login", async () => {
  let fail = true;
  navigation.search = new URLSearchParams("next=/admin/users");
  network(url => url.pathname.endsWith("/auth/login") ? fail ? failure(401, "invalid_credentials") : json(user) : undefined);
  await renderApp(<LoginPage />);
  fireEvent.change(screen.getByLabelText("ایمیل"), { target: { value: user.email } });
  fireEvent.change(screen.getByLabelText("رمز عبور"), { target: { value: "password" } });
  fireEvent.submit(screen.getByRole("button", { name: "ورود" }).closest("form")!);
  await screen.findByRole("alert");
  fail = false;
  fireEvent.submit(screen.getByRole("button", { name: "ورود" }).closest("form")!);
  await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/admin/users"));
});

test("source links show marketplace labels and safely handle invalid URLs", () => {
  for (const url of ["https://divar.ir/v/x", "https://www.bama.ir/x", "https://karnameh.com/x", "https://hamrah-mechanic.com/x", "https://example.com/x", "not a url"]) expect(sourceLabelFromUrl(url)).toBeTruthy();
});

test("malformed similar-listings payload propagates to the error boundary", async () => {
  network(url => url.pathname.endsWith("/similar") ? new Response("not JSON") : undefined);
  await expect(ListingPage({ params: Promise.resolve({ id: "test" }) })).rejects.toBeInstanceOf(SyntaxError);
});

test("route-specific loading screens and install manifest are complete", async () => {
  const { default: ListingLoading } = await import("./listing/[id]/loading");
  const { default: ModelLoading } = await import("./model/[model]/loading");
  const { default: manifest } = await import("./manifest");
  const view = render(<ListingLoading />);
  expect(screen.getAllByLabelText("در حال بارگذاری")).toHaveLength(2);
  view.rerender(<ModelLoading />);
  expect(screen.getAllByLabelText("در حال بارگذاری")).toHaveLength(1);
  expect(manifest()).toMatchObject({ lang: "fa", dir: "rtl", start_url: "/", display: "standalone" });
});
