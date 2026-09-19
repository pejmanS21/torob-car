import { describe, expect, test } from "bun:test";
import { encodePathSegment } from "./url";

describe("encodePathSegment", () => {
  test("encodes a plain Persian model name once", () => {
    expect(encodePathSegment("پژو 206")).toBe("%D9%BE%DA%98%D9%88%20206");
  });

  test("does not double-encode a param that already arrived encoded", () => {
    // The regression: Next hands route params over percent-encoded, and encoding again
    // produced %25D9%25BE… which the API answered with 404 → the page rendered not-found.
    expect(encodePathSegment("%D9%BE%DA%98%D9%88%20206")).toBe("%D9%BE%DA%98%D9%88%20206");
  });

  test("keeps a literal percent that is not an escape sequence", () => {
    expect(encodePathSegment("100% اصل")).toBe("100%25%20%D8%A7%D8%B5%D9%84");
  });

  test("leaves an ascii name untouched", () => {
    expect(encodePathSegment("206")).toBe("206");
  });
});
