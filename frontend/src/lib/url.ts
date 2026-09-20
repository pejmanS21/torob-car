/** Builds an API path segment out of a Next route param.
 *
 * Route params reach a page percent-encoded (a Persian model name stays `%D9%BE…`), so encoding
 * one again would double-encode it and the API would answer 404. Decoding first yields exactly
 * one layer of encoding whether or not the param arrived encoded. */
export function encodePathSegment(param: string): string {
  let decoded = param;
  try {
    decoded = decodeURIComponent(param);
  } catch {
    // A literal '%' that is not an escape: the param is already decoded.
  }
  return encodeURIComponent(decoded);
}

const SOURCE_NAMES: Record<string, string> = {
  "divar.ir": "دیوار",
  "bama.ir": "باما",
  "karnameh.com": "کارنامه",
  "hamrah-mechanic.com": "همراه مکانیک",
};

/** Persian name of the site an ad lives on, read from its URL. Falls back to the bare host so
 * a source we have no name for still reads as a place rather than as a blank. */
export function sourceLabelFromUrl(url: string): string {
  let host: string;
  try {
    host = new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "سایت آگهی";
  }
  return SOURCE_NAMES[host] ?? host;
}
