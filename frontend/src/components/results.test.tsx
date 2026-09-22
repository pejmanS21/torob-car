import { test, expect, mock } from "bun:test";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { network, renderApp, search, facets, json, failure } from "../../test/support";
import { navigation } from "../../test/setup";
import { FiltersPanel } from "./FiltersPanel";
import { ResultsScreen } from "./ResultsScreen";
import type { SearchOverrides } from "@/lib/search";
import { useState } from "react";

const change = (element: HTMLElement, value: string) => fireEvent.change(element, { target: { value } });

test("filters update every dimension, remove chips, expand options and reset", () => {
  const onChange = mock<(params: SearchOverrides) => void>(() => undefined);
  const reset = mock(() => undefined);
  const close = mock(() => undefined);
  const populated = { ...facets, models: Array.from({ length: 12 }, (_, i) => ({ brand: "brand", model: `model${i}`, count: 10 })), cities: Array.from({ length: 12 }, (_, i) => ({ value: `city${i}`, count: 10 })) };
  function Harness() {
    const [params, set] = useState<SearchOverrides>({ category: "light", models: ["model0"], cities: ["city0"], gearbox: "manual", price_min: 100000000, price_max: 1000000000, year_min: 1390, year_max: 1400, km_min: 10000, km_max: 100000, sources: ["divar"], price_types: ["lumpsum"], document_statuses: ["no_title"], only_below: true });
    return <FiltersPanel params={params} facets={populated} open onChange={next => { onChange(next); set(next); }} onReset={reset} onClose={close} resultCount={4} />;
  }
  render(<Harness />);
  for (const chip of screen.getAllByRole("button", { name: /حذف فیلتر/ })) fireEvent.click(chip);
  expect(onChange.mock.calls.length).toBeGreaterThan(8);
  for (const select of screen.getAllByRole("combobox") as HTMLSelectElement[]) {
    change(select, select.options[1].value);
    change(select, "");
  }
  for (const checkbox of screen.getAllByRole("checkbox")) fireEvent.click(checkbox);
  for (const name of [/مدل دیگر/, /شهر دیگر/]) {
    fireEvent.click(screen.getByRole("button", { name }));
    fireEvent.click(screen.getByRole("button", { name: "کمتر" }));
  }
  for (const button of Array.from(document.querySelectorAll<HTMLButtonElement>("button[aria-pressed]"))) fireEvent.click(button);
  fireEvent.click(screen.getByRole("button", { name: "همه" }));
  fireEvent.click(screen.getByRole("button", { name: "پاک‌کردن همه" }));
  expect(reset).toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "بستن فیلترها" }));
  expect(close).toHaveBeenCalled();
});

test("results support pagination retry, filters, sorting and saved searches", async () => {
  let calls = 0;
  network(url => {
    if (url.pathname.endsWith("/search")) {
      calls++;
      if (calls === 2) return failure();
      if (calls > 2) return json({ ...search, items: [{ ...search.items[0], id: "page2", is_exact: false }] });
      return json({ ...search, total: 50 });
    }
  });
  const sheet = mock<(open: boolean) => void>(() => undefined);
  const app = await renderApp(<ResultsScreen params={{ q: "پژو", category: "light" }} facets={facets} sheetOpen onSheetOpenChange={sheet} />);
  const more = await screen.findByRole("button", { name: /بیشتر/ });
  fireEvent.click(more);
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: /تلاش دوباره/ }));
  await waitFor(() => expect(screen.queryByRole("alert")?.tagName).toBeUndefined());
  fireEvent.click(screen.getByRole("button", { name: /هشدار قیمت/ }));
  expect(app.state().authOpen).toBe(true);
  const sort = screen.getByLabelText(/مرتب/);
  change(sort, "price");
  expect(navigation.replace.mock.calls.at(-1)?.[0]).toContain("sort=price");
  fireEvent.click(screen.getByRole("button", { name: /فیلترها \(/ }));
  expect(sheet).toHaveBeenCalledWith(true);
  fireEvent.click(screen.getByRole("button", { name: "پاک‌کردن همه" }));
  expect(navigation.replace.mock.calls.at(-1)?.[0]).toContain("q=");
  fireEvent.click(screen.getByRole("button", { name: "بستن فیلترها" }));
  expect(sheet).toHaveBeenCalledWith(false);
});

test("failed searches retry into empty state without creating a zero-price alert", async () => {
  let failed = true;
  network(url => url.pathname.endsWith("/search") ? failed ? failure() : json({ ...search, items: [], total: 0 }) : undefined);
  const app = await renderApp(<ResultsScreen params={{}} facets={null} sheetOpen={false} onSheetOpenChange={() => undefined} />);
  await screen.findByRole("alert");
  failed = false;
  fireEvent.click(screen.getByRole("button", { name: /تلاش دوباره/ }));
  await screen.findByText(/با این شرایط چیزی پیدا نشد/);
  fireEvent.click(screen.getByRole("button", { name: /هشدار قیمت/ }));
  expect(app.state().authOpen).toBe(false);
});
