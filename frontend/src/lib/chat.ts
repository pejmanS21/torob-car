import type { AssistantMessage } from "./api/types";
import type { ChatMessage } from "./types";

const HISTORY_LIMIT = 10;
const REPLY_LIMIT = 2000;

export function toAssistantMessages(messages: ChatMessage[]): AssistantMessage[] {
  return messages.filter(({ status }) => !status).slice(-HISTORY_LIMIT).map(({ role, text, listings }) => ({
    role,
    text: text.slice(0, REPLY_LIMIT),
    listing_ids: role === "assistant" ? listings.map(({ id }) => id).slice(0, 3) : [],
  }));
}
