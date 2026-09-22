import { ApiError, apiPostStream } from "./client";
import type { AssistantRequest, AssistantResponse } from "./types";

interface Frame { event: string; data: string; }
const MAX_BUFFER_LENGTH = 128_000;

function parseFrame(frame: string): Frame {
  let event = "message";
  const data: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  return { event, data: data.join("\n") };
}

async function* readFrames(body: ReadableStream<Uint8Array>): AsyncGenerator<Frame> {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let buffer = "";
  try {
    while (true) {
      const chunk = await reader.read();
      buffer += chunk.done ? decoder.decode() : decoder.decode(chunk.value, { stream: true });
      buffer = buffer.replaceAll("\r\n", "\n");
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const frame = parseFrame(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        if (frame.data) yield frame;
      }
      if (buffer.length > MAX_BUFFER_LENGTH) throw new Error("Stream frame is too large");
      if (chunk.done) return;
    }
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

export async function streamAssistant(
  request: AssistantRequest, onText: (text: string) => void, signal?: AbortSignal,
): Promise<AssistantResponse> {
  const response = await apiPostStream("/assistant/stream", request, signal);
  if (!response.body || !response.headers.get("content-type")?.includes("text/event-stream")) {
    throw new ApiError(502, "invalid_stream", "Invalid assistant stream");
  }
  for await (const frame of readFrames(response.body)) {
    const data = JSON.parse(frame.data);
    if (frame.event === "error") throw new ApiError(503, data.code, data.message);
    if (frame.event === "text" && typeof data.text === "string") onText(data.text);
    if (frame.event === "done" && typeof data.text === "string" && Array.isArray(data.listings)) {
      return data as AssistantResponse;
    }
  }
  throw new ApiError(502, "incomplete_stream", "Assistant stream ended before completion");
}
