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
  "governed-proposal-form",
  "proposal-source-message",
  "proposal-create",
  "governed-decision-form",
  "decision-proposal",
  "decision-record",
  "cto-handoff-form",
  "cto-handoff-proposal",
  "cto-handoff-record",
  "conversation-lifecycle-state",
  "conversation-lifecycle-list",
]) {
  assert.match(html, new RegExp(`id=["']${id}["']`), `${id} must exist`);
}
assert.match(html, /id="conversation-new"[^>]*disabled/);
assert.match(html, /id="conversation-sign-out"[^>]*disabled/);
assert.match(html, /id="conversation-message"[^>]*maxlength="20000"[^>]*disabled/);
assert.match(html, /id="decision-request-button"[^>]*disabled/);
assert.match(html, /Conversation text can never authorize delegation or execution/);

assert.equal((moduleSource.match(/method: "POST"/g) ?? []).length, 6);
assert.doesNotMatch(moduleSource, /method: "(?:PUT|PATCH|DELETE)"/);
assert.doesNotMatch(moduleSource, /localStorage|sessionStorage|indexedDB/);
assert.doesNotMatch(moduleSource, /innerHTML|insertAdjacentHTML|document\.write/);
assert.match(moduleSource, /credentials: "same-origin"/);
assert.match(moduleSource, /conversationSession\?\.conversation_authority/);
assert.match(moduleSource, /"X-MC-CSRF": conversationSession\.csrf_token/);
assert.match(moduleSource, /"Idempotency-Key": conversationIdempotencyKey/);
assert.match(moduleSource, /runtime_unavailable|Responses may remain unavailable/);
assert.match(moduleSource, /audit-timeline\?limit=100/);
assert.match(moduleSource, /\/api\/notifications\?limit=100/);
assert.match(moduleSource, /\["not_configured", "enabled"\]\.includes\(notifications\.transport_status\)/);
assert.match(moduleSource, /"pending", "in_flight", "retry_wait", "delivered", "dead_letter"/);
assert.match(moduleSource, /notification\.last_error \?\? null/);
assert.match(moduleSource, /"body" in event|"rationale" in event/);
assert.match(moduleSource, /source_evidence_refs: \[\]/);
assert.match(moduleSource, /proposal draft recorded · no authority/);
assert.match(moduleSource, /CEO decision recorded · no authority/);
assert.match(moduleSource, /conversationSession\?\.cto_handoff_recording !== true/);
assert.match(moduleSource, /\/api\/task-proposals\/\$\{encodeURIComponent\(proposalId\)\}\/cto-handoffs/);
assert.match(moduleSource, /CTO handoff recorded · connector pending · no authority/);
assert.match(moduleSource, /handoff\.dispatch_authorized !== false/);
assert.match(moduleSource, /conversationSession\?\.cto_handoff_results !== true/);
assert.match(moduleSource, /\/api\/conversations\/\$\{encodeURIComponent\(conversationId\)\}\/cto-handoff-results\?limit=100/);
assert.match(moduleSource, /result\.execution_authorized !== false/);
assert.match(moduleSource, /assignment_id !== null \|\| proposal\.execution_authorized !== false/);
assert.match(moduleSource, /recordedDecisionProposalIds\.has\(proposal\.proposal_id\)/);
assert.match(moduleSource, /renderGovernedProposals\(\{ proposals: activeGovernedProposals \}, \{ live: true \}\);/);
assert.match(moduleSource, /\["Bounded scope", proposal\.scope\]/);
assert.match(moduleSource, /\["Expected result", proposal\.expected_result\]/);
assert.match(moduleSource, /typeof proposal\.scope !== "string"/);
assert.match(moduleSource, /proposal\.scope\.slice\(0, 160\)/);

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
