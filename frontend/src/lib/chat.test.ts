import { expect, test } from "bun:test";
import { toAssistantMessages } from "./chat";
import type { ChatMessage } from "./types";
import fixture from "./api/__fixtures__/assistant.json";

test("follow-up history keeps the exact cards recommended by the assistant", () => {
  const messages: ChatMessage[] = [
    { role: "user", text: "۲۰۶ تهران", listings: [] },
    { role: "assistant", text: "پیدا کردم", listings: fixture.listings as ChatMessage["listings"] },
    { role: "user", text: "کدوم بهتره؟", listings: [] },
  ];
  const body = toAssistantMessages(messages);
  expect(body[1].listing_ids).toEqual(fixture.listings.map(({ id }) => id));
  expect(body[2].listing_ids).toEqual([]);
});

test("replayed history stays inside the API length bounds", () => {
  const messages: ChatMessage[] = Array.from({ length: 12 }, () => ({
    role: "assistant", text: "پ".repeat(2200), listings: [],
  }));
  expect(toAssistantMessages(messages)).toHaveLength(10);
  expect(toAssistantMessages(messages)[0].text).toHaveLength(2000);
});

test("partial replies and errors are never replayed as completed model answers", () => {
  const messages: ChatMessage[] = [
    { role: "user", text: "۲۰۶", listings: [] },
    { role: "assistant", text: "ناقص", listings: [], status: "streaming" },
    { role: "assistant", text: "خطا", listings: [], status: "failed" },
  ];
  expect(toAssistantMessages(messages)).toEqual([{ role: "user", text: "۲۰۶", listing_ids: [] }]);
});
