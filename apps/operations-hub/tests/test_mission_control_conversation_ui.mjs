import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const moduleSource = readFileSync(new URL("../mission-control/mission-control.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../mission-control/index.html", import.meta.url), "utf8");

for (const id of [
  "conversation-sign-in",
  "conversation-new",
  "conversation-sign-out",
  "conversation-message",
  "decision-request-button",
]) {
  assert.match(html, new RegExp(`id=["']${id}["']`), `${id} must exist`);
}
assert.match(html, /id="conversation-new"[^>]*disabled/);
assert.match(html, /id="conversation-sign-out"[^>]*disabled/);
assert.match(html, /id="conversation-message"[^>]*maxlength="20000"[^>]*disabled/);
assert.match(html, /id="decision-request-button"[^>]*disabled/);
assert.match(html, /Conversation text can never authorize delegation or execution/);

assert.equal((moduleSource.match(/method: "POST"/g) ?? []).length, 3);
assert.doesNotMatch(moduleSource, /method: "(?:PUT|PATCH|DELETE)"/);
assert.doesNotMatch(moduleSource, /localStorage|sessionStorage|indexedDB/);
assert.doesNotMatch(moduleSource, /innerHTML|insertAdjacentHTML|document\.write/);
assert.match(moduleSource, /credentials: "same-origin"/);
assert.match(moduleSource, /conversationSession\?\.conversation_authority/);
assert.match(moduleSource, /"X-MC-CSRF": conversationSession\.csrf_token/);
assert.match(moduleSource, /"Idempotency-Key": conversationIdempotencyKey/);
assert.match(moduleSource, /runtime_unavailable|Responses may remain unavailable/);

const start = moduleSource.indexOf("function conversationIdempotencyKey(prefix) {");
const end = moduleSource.indexOf("\nfunction setConversationState", start);
assert.ok(start >= 0 && end > start, "bounded idempotency helper must exist");
const conversationIdempotencyKey = runInNewContext(
  `${moduleSource.slice(start, end)}\nconversationIdempotencyKey`,
  { globalThis: { crypto: { randomUUID: () => "00000000-0000-4000-8000-000000000001" } }, Date, Math },
);
assert.equal(
  conversationIdempotencyKey("submit"),
  "submit-00000000-0000-4000-8000-000000000001",
);

console.log("Mission Control conversation UI security contract: GREEN");
