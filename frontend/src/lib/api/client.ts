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

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    // Redis already caches rankings server-side; the browser never caches API responses.
    response = await fetch(`${apiBase()}${path}`, { ...init, cache: "no-store" });
  } catch (error) {
    if (isAbort(error)) throw error;
    throw new ApiError(NETWORK_ERROR_STATUS, "network_error", "network failure");
  }
  if (!response.ok) throw await toApiError(response);
  return (await response.json()) as T;
}

export function apiGet<T>(path: string, params: QueryParams = {}, signal?: AbortSignal): Promise<T> {
  return request<T>(`${path}${buildQuery(params)}`, { method: "GET", signal });
}

export function apiPost<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body), headers: { "content-type": "application/json" }, signal });
}
