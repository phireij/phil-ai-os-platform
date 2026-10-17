# MC-021 — governed CTO read-only pilot design

**Status:** Design for owner review only. No connector, credential, OAuth registration, provider call, deployment, or authority change is authorized.

## Product outcome

Codex/ChatGPT can act as the CEO's CTO by reading a bounded, attributable Mission Control brief and citing its evidence. The CEO still makes decisions in Mission Control. A proposal returned by the CTO is advice, not a Mission Control draft, decision, assignment, execution, or notification. A read-only connection does not mean an agent resides in the production server or runs continuously.

The first pilot should run from the CEO's existing Codex/ChatGPT surface using the present subscription allowance. It does **not** require Pro $100 or Mission Control-hosted inference. The latter is a separate product capability whose ChatGPT-plan eligibility is unresolved.

## Trust boundary and sequence

1. The CEO explicitly connects a private Mission Control read tool to Codex/ChatGPT. The connector authenticates the person to a **new, narrowly scoped read-only resource**; it does not reuse or reveal the browser session cookie, Google client secret, CEO bearer token, Telegram token, API key, or protected storage key to the model or plugin manifest.
2. The server validates the caller and owner scope **on every call**. It reads only approved existing projections. The current CEO-session routes (`/api/conversations`, per-conversation audit timeline, and `/api/notifications`) and the separate snapshot/posture bridge have different authentication and routing boundaries; the adapter must not collapse them by forwarding arbitrary paths or credentials.
3. The adapter returns a bounded allowlist with source, observation time, and availability. It never infers `ready` from missing or stale evidence. The CTO may summarize and cite the returned identifiers but cannot request hidden fields or turn a read into a write.
4. Disconnecting the tool or revoking its scoped authorization prevents subsequent calls. Existing Mission Control sessions and Telegram delivery remain unaffected.

## Pilot tool contract (proposal)

All tools are GET-equivalent, `readOnlyHint: true`, `destructiveHint: false`, and `openWorldHint: false`; annotations are hints, not authorization. No generic URL/path/query, SQL, shell, search-across-all-content, mutation, or notification tool is exposed.

| Tool | Input cap | Output allowlist | Explicit exclusions |
|---|---|---|---|
| `get_mission_control_status` | No input; one owner, one snapshot | Project IDs/names, supported status and freshness, source/provenance, observed-at, unavailable-source markers, authority posture | Conversation/message bodies, decision rationale, secrets, credentials, unsupported readiness assertions |
| `list_governed_evidence` | One approved project ID; maximum 20 items and fixed cursor length | Evidence type, opaque ID, source, observed-at, freshness/availability, owner-safe URL where one exists | Raw payloads, customer/personal data, free-text search, cross-project enumeration |
| `get_proposal_state` | One proposal ID from prior result | Proposal ID, correlated conversation ID, lifecycle state, expiry, decision-recorded flag, assignment/execution-disabled flags | Proposal narrative, CEO rationale, unbounded conversation history, a decision or approval action |

**Fail-closed response:** `unavailable`, `stale`, `unauthorized`, and `not_configured` remain distinct from an empty successful result. Each response declares `authority_effect: none`, `source_revision` or `unknown`, and `observed_at` or `null`. Truncate or reject responses above a fixed byte cap; never return partial JSON as if complete. Display source age and a link back to the CEO-visible record when possible.

**Audit:** Record tool name, authenticated principal/connection identifier, request ID, result category, source revision, and timestamp. Exclude returned content, bearer material, message text, rationale, and secret values. Bound retention to the approved audit policy; do not create a second unreviewed content store.

## Acceptance and negative tests before any real connection

- Fixture-only contract tests cover each allowed tool, output schema, record ownership, missing source, stale evidence, pagination cap, oversize upstream, and redaction.
- Unauthorized, expired, revoked, cross-owner, cross-project, unknown-ID, non-GET, and forged write-tool requests fail closed and produce no state change.
- Verify that tool metadata lists **no** write, provider-dispatch, approval, assignment, execution, notification, or arbitrary network capability.
- A later separately approved private connection must demonstrate one owner-authenticated read, provenance/freshness display, disconnect/revocation, and unchanged production state/workloads. It must not send a Telegram message or call the inactive API provider.

## Open decision gates

| Gate | Evidence needed | Current state |
|---|---|---|
| Connector exposure | Review private endpoint/tunnel, OAuth 2.1 user authentication, per-call owner authorization, network/client authentication, and rollback. | Design only; no endpoint chosen or deployed. |
| Data approval | Approve the exact field allowlist and whether even identifier-only proposal/audit records may be exposed to the CTO surface. | Not approved for a connection. |
| Mission Control-hosted ChatGPT-plan inference | Confirm eligibility for this remotely hosted/private service and its intended distribution; review OAuth consent, token custody, usage controls, and model capabilities. | Unverified. Official OpenAI documentation directs paid/remotely hosted app developers to an interest process; no application or token request has been made. |
| Pro $100 purchase | Compare measured usage of the existing plan and an eligible pilot against current Pro allowances and price. | No recommendation to upgrade solely for Mission Control. |
| API fallback | Owner explicitly selects the API path and separately approves credential staging, deployment, and live-call acceptance. | Paused; code merged but inactive. |

## Official OpenAI documentation

- [MCP server design](https://developers.openai.com/plugins/build/mcp-server): focused read tools, accurate annotations, per-call authorization, and private endpoint considerations.
- [Plugin authentication](https://developers.openai.com/plugins/build/auth): OAuth 2.1 for user-scoped data; client mTLS does not replace end-user authorization.
- [ChatGPT-plan usage overview](https://developers.openai.com/siwc/token-sharing-open-source): open-source/local path and eligibility warning for paid or remotely hosted apps.
- [Codex app-server](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server): an OAuth-token route for eligible host apps, not proof that this private production app is eligible.
