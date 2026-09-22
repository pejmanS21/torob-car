import { act, render, waitFor } from "@testing-library/react";
import { expect, mock } from "bun:test";
import { AppStateProvider, useAppState, type AppStateValue } from "../src/state/AppState";
import type { ListingDetail, ModelStats, SearchResponse, Facets } from "../src/lib/api/types";
import listingFixture from "../src/lib/api/__fixtures__/listing.json";
import statsFixture from "../src/lib/api/__fixtures__/model-stats.json";
import searchFixture from "../src/lib/api/__fixtures__/search.json";
import facetsFixture from "../src/lib/api/__fixtures__/facets.json";
import suggestions from "../src/lib/api/__fixtures__/suggest.json";
import estimate from "../src/lib/api/__fixtures__/estimate.json";

export const listing = listingFixture as ListingDetail;
export const stats = statsFixture as ModelStats;
export const search = searchFixture as SearchResponse;
export const facets = facetsFixture as Facets;
export const user = { id: "user-1", email: "test@example.com", role: "admin", is_active: true, created_at: "2026-09-01T00:00:00Z" };
export const account = { saved: [], alerts: [] };
export const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
export const failure = (status = 503, code = "service_unavailable", message = "خطای سرویس") => json({ error: { code, message, details: {} } }, status);
type Handler = (url: URL, init?: RequestInit) => Response | Promise<Response> | undefined;
export function network(handler: Handler = () => undefined) {
  const fetcher = mock(async (input: string | URL | Request, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const response = await handler(url, init);
    if (response) return response;
    if (url.pathname === "/strobi.avatar.json") return json({ colors: {} });
    const path = url.pathname.replace("/api/v1", "");
    if (path === "/me") return failure(401, "not_authenticated");
    if (path === "/me/state" || path === "/me/import") return json(account);
    if (path === "/me/saved" || path === "/me/alerts") return json([]);
    if (path === "/me/chats") return json([]);
    if (path === "/search") return json(search);
    if (path === "/facets") return json(facets);
    if (path.endsWith("/stats")) return json(stats);
    if (path === "/catalog/suggest") return json(suggestions);
    if (path === "/estimates") return json(estimate);
    if (path === "/listings" || path.endsWith("/similar")) return json(search.items);
    if (path.startsWith("/listings/")) return json(listing);
    throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${path}`);
  });
  globalThis.fetch = fetcher as unknown as typeof fetch;
  return fetcher;
}

export async function renderApp(children: React.ReactNode) {
  const current = { value: null as AppStateValue | null };
  function Probe() { current.value = useAppState(); return null; }
  const view = render(<AppStateProvider><Probe />{children}</AppStateProvider>);
  await waitFor(() => expect(current.value?.authReady).toBe(true));
  return { ...view, state: () => current.value!, act };
}

export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((success, failure) => { resolve = success; reject = failure; });
  return { promise, resolve, reject };
}
