import "./test_mission_control_write_callbacks.mjs";
import "./test_mission_control_session_errors.mjs";
import "./test_mission_control_session_races.mjs";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const moduleSource = readFileSync(new URL("../mission-control/mission-control.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../mission-control/index.html", import.meta.url), "utf8");
const deployWorkflow = readFileSync(new URL("../../../.github/workflows/mission-control-readonly-deploy.yml", import.meta.url), "utf8");

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
  "ruby-review-synthetic-panel",
  "ruby-review-synthetic-state",
  "ruby-review-synthetic-list",
]) {
  assert.match(html, new RegExp(`id=["']${id}["']`), `${id} must exist`);
}
assert.match(html, /id="conversation-new"[^>]*disabled/);
assert.match(html, /id="conversation-sign-out"[^>]*disabled/);
assert.match(html, /id="conversation-message"[^>]*maxlength="20000"[^>]*disabled/);
assert.match(html, /id="decision-request-button"[^>]*disabled/);
assert.match(html, /Conversation text can never authorize delegation or execution/);
const rubyPanel = html.slice(html.indexOf('id="ruby-review-synthetic-panel"'), html.indexOf('id="governed-proposals-title"'));
assert.match(rubyPanel, /hidden/);
assert.match(rubyPanel, /Synthetic fixture only/);
assert.doesNotMatch(rubyPanel, /<button\b|<form\b|<input\b|<select\b|<textarea\b/);

const approvedPostRoutes = [
  '"/auth/google/logout"',
  '"/api/conversations"',
  '`/api/conversations/${encodeURIComponent(activeConversationId)}/messages`',
  '`/api/conversations/${encodeURIComponent(activeConversationId)}/task-proposals`',
  '`/api/task-proposals/${encodeURIComponent(proposalId)}/decisions`',
  '`/api/task-proposals/${encodeURIComponent(proposalId)}/cto-handoffs`',
];
const postMethodCount = (source) => [...source.matchAll(/(?:\bmethod\b|["']method["'])\s*:\s*(["'`])POST\1/g)].length;
const requestStart = /conversationRequest\(\s*(["'`])([^"'`]+)\1\s*,\s*\{/g;
function balancedObject(source, start) {
  let depth = 0;
  let quote = null;
  let escaped = false;
  for (let index = start; index < source.length; index += 1) {
    const character = source[index];
    if (quote) {
      if (escaped) escaped = false;
      else if (character === "\\") escaped = true;
      else if (character === quote) quote = null;
    } else if ('"\'`'.includes(character)) quote = character;
    else if (character === "{") depth += 1;
    else if (character === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(start, index + 1);
    }
  }
  return "";
}
function conversationPostRoutes(source) {
  return [...source.matchAll(requestStart)]
    .filter((match) => /(?:\bmethod\b|["']method["'])\s*:\s*(["'`])POST\1/.test(balancedObject(source, match.index + match[0].length - 1)))
    .map((match) => `${match[1]}${match[2]}${match[1]}`);
}
function assertApprovedPostInventory(source) {
  assert.equal(postMethodCount(source), approvedPostRoutes.length);
  assert.deepEqual(conversationPostRoutes(source).sort(), approvedPostRoutes.slice().sort());
}
assertApprovedPostInventory(moduleSource);
assert.throws(() => assertApprovedPostInventory(`${moduleSource}\nconversationRequest("/api/unapproved", { headers: {}, method: "POST" });`));
assert.throws(() => assertApprovedPostInventory(`${moduleSource}\nfetch("/api/unapproved", { headers: {}, method: "POST" });`));
assert.doesNotMatch(moduleSource, /\/api\/decision-requests/);
assert.equal((deployWorkflow.match(/approved_post_routes = \(/g) ?? []).length, 2);
assert.equal((deployWorkflow.match(/def _conversation_request_post_routes/g) ?? []).length, 2);
assert.equal((deployWorkflow.match(/post_method_count = len\(post_method\.findall\(module\)\)/g) ?? []).length, 2);
for (const route of approvedPostRoutes) {
  const escaped = route.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  assert.equal((deployWorkflow.match(new RegExp(escaped, "g")) ?? []).length, 2, `${route} must be enforced before publish and after deployment`);
}
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
assert.match(moduleSource, /"awaiting_connector", "acknowledged", "result_recorded"/);
assert.match(moduleSource, /acknowledged: "acknowledged · no authority"/);
assert.match(moduleSource, /conversationSession\?\.cto_handoff_results !== true/);
assert.match(moduleSource, /\/api\/conversations\/\$\{encodeURIComponent\(conversationId\)\}\/cto-handoff-results\?limit=100/);
assert.match(moduleSource, /result\.execution_authorized !== false/);
assert.match(moduleSource, /conversationSession\?\.ruby_review_synthetic !== true/);
assert.match(moduleSource, /conversationRequest\("\/api\/ruby-review-synthetic"\)/);
assert.match(moduleSource, /payload\.exports_enabled !== false/);
assert.match(moduleSource, /payload\.activation_authorized !== false/);
assert.match(moduleSource, /record\.synthetic !== true/);
assert.match(moduleSource, /audit\.identifier_only !== true/);
assert.match(moduleSource, /detail\.textContent = value/);
assert.match(moduleSource, /panel\.hidden = true/);
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

const rubyStart = moduleSource.indexOf("function assertRubySyntheticReview(payload) {");
const rubyEnd = moduleSource.indexOf("\nfunction resetConversationView", rubyStart);
assert.ok(rubyStart >= 0 && rubyEnd > rubyStart, "Ruby synthetic review renderer must exist");
const created = [];
const target = { replaceChildren(...children) { this.children = children; } };
const panel = { hidden: true };
const state = { textContent: "", className: "" };
const fakeDocument = {
  querySelector(selector) {
    return ({ "#ruby-review-synthetic-list": target, "#ruby-review-synthetic-panel": panel, "#ruby-review-synthetic-state": state })[selector];
  },
  createElement() {
    const node = { className: "", textContent: "", children: [], append(...children) { this.children.push(...children); } };
    created.push(node);
    return node;
  },
};
const renderRubySyntheticReview = runInNewContext(
  `${moduleSource.slice(rubyStart, rubyEnd)}\nrenderRubySyntheticReview`,
  { document: fakeDocument, Object, Array, String, Error },
);
const unsafe = '<img src=x onerror="unsafe-marker">';
renderRubySyntheticReview({
  schema: "ruby-review-synthetic.v1", mode: "synthetic_fixture", project_id: "rubys-cake-delights-hq",
  owner_access: "same_origin_session_only", exports_enabled: false, activation_authorized: false,
  records: [{ record_id: unsafe, project_id: "rubys-cake-delights-hq", state: "pending_review", revision_number: 1, synthetic: true }],
  audit: [{ event_id: unsafe, record_id: unsafe, event_type: "record_created", identifier_only: true, synthetic: true }],
  authority_effect: "none", execution_authorized: false, mutation_authorized: false,
});
assert.equal(panel.hidden, false);
assert.equal(state.textContent, "synthetic fixture · no authority");
assert.ok(created.some((node) => node.textContent === unsafe), "fixture data must be assigned as text, not markup");

console.log("Mission Control conversation UI security contract: GREEN");


