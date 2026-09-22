import { apiBase } from "./base";
import type { ApiErrorBody } from "./types";

export type QueryValue = string | number | boolean | string[] | null | undefined;
export type QueryParams = Record<string, QueryValue>;

export const NETWORK_ERROR_STATUS = 0;

/** The backend's error envelope as an exception. Screens branch on `code`, never on `message`. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const isAbort = (error: unknown): boolean => error instanceof DOMException && error.name === "AbortError";

export function buildQuery(params: QueryParams): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((item) => query.append(key, item));
    else query.append(key, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as ApiErrorBody;
    return new ApiError(response.status, body.error.code, body.error.message, body.error.details);
  } catch {
    return new ApiError(response.status, "http_error", response.statusText || `HTTP ${response.status}`);
  }
}

const NO_CONTENT = 204;
const REFRESH_PATH = "/auth/refresh";
const TOKEN_EXPIRED = "token_expired";

async function send(path: string, init: RequestInit): Promise<Response> {
  let response: Response;
  try {
    // Redis already caches rankings server-side; the browser never caches API responses.
    response = await fetch(`${apiBase()}${path}`, { ...init, cache: "no-store" });
  } catch (error) {
    if (isAbort(error)) throw error;
    throw new ApiError(NETWORK_ERROR_STATUS, "network_error", "network failure");
  }
  if (!response.ok) throw await toApiError(response);
  return response;
}

let refreshInFlight: Promise<void> | null = null;

/** One refresh shared by every request that found its access token expired. */
function refreshSession(): Promise<void> {
  refreshInFlight ??= send(REFRESH_PATH, { method: "POST" })
    .then(() => undefined)
    .finally(() => { refreshInFlight = null; });
  return refreshInFlight;
}

/** The access token lives 15 minutes and its cookie 30 days, so an expired one still
 *  arrives and the backend says `token_expired`: refresh once, then replay. The cookies
 *  are HttpOnly and same-origin — no token is ever visible to this code. */
async function request(path: string, init: RequestInit): Promise<Response> {
  try {
    return await send(path, init);
  } catch (error) {
    const expired = error instanceof ApiError && error.code === TOKEN_EXPIRED && path !== REFRESH_PATH;
    if (!expired) throw error;
    try { await refreshSession(); } catch { throw error; } // the session is over: report the original failure
    return send(path, init);
  }
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await request(path, init);
  if (response.status === NO_CONTENT) return undefined as T;
  return (await response.json()) as T;
}

const withJson = (method: string, body: unknown, signal?: AbortSignal): RequestInit =>
  body === undefined ? { method, signal } : { method, body: JSON.stringify(body), headers: { "content-type": "application/json" }, signal };

export function apiGet<T>(path: string, params: QueryParams = {}, signal?: AbortSignal): Promise<T> {
  return requestJson<T>(`${path}${buildQuery(params)}`, { method: "GET", signal });
}

export function apiPost<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return requestJson<T>(path, withJson("POST", body, signal));
}

export function apiPostStream(path: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  const init = withJson("POST", body, signal);
  return request(path, { ...init, headers: { ...init.headers, accept: "text/event-stream" } });
}

export function apiPut<T = void>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  return requestJson<T>(path, withJson("PUT", body, signal));
}

export function apiPatch<T = void>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  return requestJson<T>(path, withJson("PATCH", body, signal));
}

export function apiDelete<T = void>(path: string, signal?: AbortSignal): Promise<T> {
  return requestJson<T>(path, { method: "DELETE", signal });
}
