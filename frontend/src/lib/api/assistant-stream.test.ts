import { afterEach, expect, test } from "bun:test";
import { streamAssistant } from "./assistant-stream";
import type { AssistantRequest, AssistantResponse } from "./types";

const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; });
const request: AssistantRequest = { messages: [{ role: "user", text: "۲۰۶ تهران" }], compare_ids: [] };
const answer: AssistantResponse = { text: "به‌صرفه بودن مهم است.", listings: [], answered_by: "llm", chat_id: null };
const event = (name: string, data: unknown) => `event: ${name}\r\ndata: ${JSON.stringify(data)}\r\n\r\n`;
const encoder = new TextEncoder();

function mockResponse(response: Response) {
  globalThis.fetch = (async () => response) as unknown as typeof fetch;
}

function bytesResponse(bytes: Uint8Array) {
  return new Response(new ReadableStream({
    start(controller) { for (const byte of bytes) controller.enqueue(new Uint8Array([byte])); controller.close(); },
  }), { headers: { "content-type": "text/event-stream" } });
}

test("SSE keeps split UTF-8 Persian and half-spaces intact and uses snapshots", async () => {
  const snapshots: string[] = [];
  mockResponse(bytesResponse(encoder.encode(": connected\r\n\r\n" + event("text", { text: "به" }) + event("text", { text: answer.text }) + event("done", answer))));
  expect(await streamAssistant(request, (text) => snapshots.push(text))).toEqual(answer);
  expect(snapshots).toEqual(["به", answer.text]);
});

test("readable updates arrive before the response stream closes", async () => {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const arrived = Promise.withResolvers<string>();
  mockResponse(new Response(new ReadableStream({ start(stream) { controller = stream; } }), { headers: { "content-type": "text/event-stream" } }));
  const result = streamAssistant(request, arrived.resolve);
  controller.enqueue(encoder.encode(event("text", { text: "می‌تونی" })));
  expect(await arrived.promise).toBe("می‌تونی");
  controller.enqueue(encoder.encode(event("done", answer)));
  controller.close();
  expect(await result).toEqual(answer);
});

test("a dropped stream never becomes a completed answer", async () => {
  mockResponse(bytesResponse(encoder.encode(event("text", { text: "ناقص" }))));
  await expect(streamAssistant(request, () => undefined)).rejects.toMatchObject({ code: "incomplete_stream" });
});

test("midstream errors propagate and stop processing", async () => {
  mockResponse(bytesResponse(encoder.encode(event("text", { text: "ناقص" }) + event("error", { code: "assistant_unavailable", message: "offline" }))));
  await expect(streamAssistant(request, () => undefined)).rejects.toMatchObject({ code: "assistant_unavailable" });
});

test("quota errors preserve their HTTP code without entering stream parsing", async () => {
  mockResponse(new Response(JSON.stringify({ error: { code: "anonymous_chat_limit", message: "ورود", details: { limit: 3 } } }), { status: 429 }));
  await expect(streamAssistant(request, () => undefined)).rejects.toMatchObject({ status: 429, code: "anonymous_chat_limit" });
});

test("expired authentication is refreshed before opening the stream", async () => {
  const paths: string[] = [];
  globalThis.fetch = (async (url: string | URL | Request) => {
    paths.push(String(url));
    if (paths.length === 1) return new Response(JSON.stringify({ error: { code: "token_expired", message: "expired" } }), { status: 401 });
    if (String(url).endsWith("/auth/refresh")) return new Response("{}");
    return bytesResponse(encoder.encode(event("done", answer)));
  }) as typeof fetch;
  expect(await streamAssistant(request, () => undefined)).toEqual(answer);
  expect(paths.map((path) => path.split("/api/v1")[1])).toEqual(["/assistant/stream", "/auth/refresh", "/assistant/stream"]);
});

test("a successful response with the wrong media type is not an assistant stream", async () => {
  mockResponse(new Response("{}", { headers: { "content-type": "application/json" } }));
  await expect(streamAssistant(request, () => undefined)).rejects.toMatchObject({ code: "invalid_stream" });
});
