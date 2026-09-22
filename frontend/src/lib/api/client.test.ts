import { afterEach, expect, test } from "bun:test";
import { apiBase } from "./base";
import { ApiError, apiDelete, apiGet, apiPost, apiPut, buildQuery } from "./client";
import error404 from "./__fixtures__/error-404.json";
import error422 from "./__fixtures__/error-422.json";
import facets from "./__fixtures__/facets.json";
import type { Facets } from "./types";

interface Call { url: string; init: RequestInit | undefined; }
const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; });

function stubFetch(respond: () => Promise<Response>): Call[] {
  const calls: Call[] = [];
  globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    return respond();
  }) as unknown as typeof fetch;
  return calls;
}
const json = (status: number, body: unknown) => () => Promise.resolve(new Response(JSON.stringify(body), { status }));

async function failure(promise: Promise<unknown>): Promise<ApiError> {
  try { await promise; } catch (error) { if (error instanceof ApiError) return error; throw error; }
  throw new Error("expected the request to fail");
}

test("apiBase: server hits the internal backend, browser stays same-origin", () => {
  expect(apiBase(true)).toBe("/api/v1");
  expect(apiBase(false)).toBe(`${process.env.API_INTERNAL_URL ?? "http://backend:8000"}/api/v1`);
});

test("buildQuery drops empty values and repeats array keys", () => {
  expect(buildQuery({ q: "۲۰۶", models: ["پژو 206", "دنا"], page: 2, only_below: true, year: undefined, category: null, sort: "" }))
    .toBe("?q=%DB%B2%DB%B0%DB%B6&models=%D9%BE%DA%98%D9%88+206&models=%D8%AF%D9%86%D8%A7&page=2&only_below=true");
  expect(buildQuery({})).toBe("");
});

test("apiGet parses JSON and never lets the browser cache", async () => {
  const calls = stubFetch(json(200, facets));
  const body = await apiGet<Facets>("/facets", { category: "light" });
  expect(body.model_count).toBe(facets.model_count);
  expect(calls[0].url.endsWith("/api/v1/facets?category=light")).toBe(true);
  expect(calls[0].init?.cache).toBe("no-store");
});

test("an error envelope becomes an ApiError with the backend's code", async () => {
  stubFetch(json(404, error404));
  const error = await failure(apiGet("/listings/nope"));
  expect([error.status, error.code]).toEqual([404, "listing_not_found"]);
  expect(error.details).toEqual(error404.error.details);
});

test("apiPost sends JSON and surfaces 422 envelopes", async () => {
  const calls = stubFetch(json(422, error422));
  const error = await failure(apiPost("/estimates", { year: 1200 }));
  expect(calls[0].init?.method).toBe("POST");
  expect(calls[0].init?.body).toBe(JSON.stringify({ year: 1200 }));
  expect([error.code, error.message]).toEqual(["invalid_search", "Invalid search filters"]);
});

test("a non-JSON failure and a network failure are still ApiErrors", async () => {
  stubFetch(() => Promise.resolve(new Response("<html>bad gateway</html>", { status: 502, statusText: "Bad Gateway" })));
  const gateway = await failure(apiGet("/facets"));
  expect([gateway.status, gateway.code]).toEqual([502, "http_error"]);
  stubFetch(() => Promise.reject(new TypeError("fetch failed")));
  const offline = await failure(apiGet("/facets"));
  expect([offline.status, offline.code]).toEqual([0, "network_error"]);
});

const EXPIRED = { error: { code: "token_expired", message: "Token expired", details: {} } };
const ANONYMOUS = { error: { code: "not_authenticated", message: "Not authenticated", details: {} } };
const reply = (status: number, body: unknown): Response => new Response(JSON.stringify(body), { status });
const pathOf = (call: Call): string => call.url.replace(/^.*\/api\/v1/, "");

function routeFetch(respond: (path: string) => Response): Call[] {
  const calls: Call[] = [];
  globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
    const call = { url: String(url), init };
    calls.push(call);
    return respond(pathOf(call));
  }) as unknown as typeof fetch;
  return calls;
}

test("a 204 resolves to undefined, and PUT/DELETE use their methods", async () => {
  const calls = stubFetch(() => Promise.resolve(new Response(null, { status: 204 })));
  expect(await apiPut("/me/saved/abc")).toBeUndefined();
  expect(await apiDelete("/me/saved/abc")).toBeUndefined();
  expect(calls.map((c) => c.init?.method)).toEqual(["PUT", "DELETE"]);
  expect(calls[0].init?.body).toBeUndefined();
});

test("token_expired refreshes once and replays the request", async () => {
  let refreshed = false;
  const calls = routeFetch((path) => {
    if (path === "/auth/refresh") { refreshed = true; return reply(200, {}); }
    return refreshed ? reply(200, { ok: true }) : reply(401, EXPIRED);
  });
  expect(await apiGet<{ ok: boolean }>("/me")).toEqual({ ok: true });
  expect(calls.map(pathOf)).toEqual(["/me", "/auth/refresh", "/me"]);
  expect(calls[1].init?.method).toBe("POST");
});

test("parallel expired requests share a single refresh", async () => {
  let refreshed = false;
  const calls = routeFetch((path) => {
    if (path === "/auth/refresh") { refreshed = true; return reply(200, {}); }
    return refreshed ? reply(200, []) : reply(401, EXPIRED);
  });
  await Promise.all([apiGet("/me"), apiGet("/me/saved"), apiGet("/me/alerts")]);
  expect(calls.filter((c) => pathOf(c) === "/auth/refresh")).toHaveLength(1);
});

test("a failed refresh surfaces the original token_expired error", async () => {
  const calls = routeFetch((path) => (path === "/auth/refresh" ? reply(401, ANONYMOUS) : reply(401, EXPIRED)));
  const error = await failure(apiGet("/me"));
  expect(error.code).toBe("token_expired");
  expect(calls.map(pathOf)).toEqual(["/me", "/auth/refresh"]);
});

test("not_authenticated never triggers a refresh", async () => {
  const calls = routeFetch(() => reply(401, ANONYMOUS));
  expect((await failure(apiGet("/me"))).code).toBe("not_authenticated");
  expect(calls).toHaveLength(1);
});

test("an expired refresh call is not itself refreshed", async () => {
  const calls = routeFetch(() => reply(401, EXPIRED));
  await failure(apiPost("/auth/refresh", {}));
  expect(calls).toHaveLength(1);
});
