// The ONLY place the /api/v1 prefix and the backend host are known.
// Server Components run inside the Compose network and talk to the backend directly;
// the browser goes through Traefik on the same origin, so its base is relative.
const API_PREFIX = "/api/v1";
const DEFAULT_INTERNAL_URL = "http://backend:8000";

export function apiBase(inBrowser: boolean = typeof window !== "undefined"): string {
  if (inBrowser) return API_PREFIX;
  return `${process.env.API_INTERNAL_URL ?? DEFAULT_INTERNAL_URL}${API_PREFIX}`;
}
