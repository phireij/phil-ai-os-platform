# MC-021 — exact read fields and authentication review

**Decision status:** proposed boundary for owner review; not a connected or deployed capability. This refines the merged read-only pilot design. The first pilot is deliberately smaller than the full three-tool candidate.

## First pilot: one tool, one project

`get_mission_control_status` has no caller-supplied project, URL, path, filter, or free-text query. It returns **only** the `phil-ai-os` project and a small, read-only operational posture. No conversation, proposal, decision, notification, or customer record is returned in this first pilot.

| Output field | Source and transformation | Rule |
|---|---|---|
| `project_id` | Fixed string `phil-ai-os` | No project enumeration. |
| `project_name` | Approved project registry display name | Fixed maximum 80 characters. |
| `projection_kind` | Fixed `workspace_snapshot` or `authenticated_live_read` | Never label a static fixture as live. |
| `source_observed_at` | Source's validated timestamp, otherwise `null` | Do not substitute connector call time. |
| `retrieved_at` | Connector's current timestamp | This is retrieval time, not evidence freshness. |
| `source_revision` | Validated source revision/digest when present, otherwise `null` | Never infer a revision from deployment labels. |
| `overall_status` | Conservative connector projection; the current workspace file has no project-level status field | `unknown` for the first pilot. Do not synthesize `ready` from domain rows. |
| `freshness` | Existing approved source-specific freshness classification | `unknown` for absent/unapproved policy; stale and unknown stay distinct. |
| `source_coverage` | At most 12 entries of `{source_id, source_status, freshness, freshness_policy_status, observed_at}` copied from the approved `phil-ai-os` domain rows | Include unknown/missing source statuses; no free-text `source_state`, `reason`, or `evidence_summary`. No synthesized `available` claim. |
| `agent_posture` | At most 32 bounded entries of `{agent_id, presence_state, readiness_state, authority_ceiling}` from the authenticated v2 bridge | Include only if the separate bridge read succeeds and its existing schema validates; otherwise explicit `unavailable`. Do not include handoffs, task counts, or reasons in the first pilot. |
| `authority_effect` | Fixed `none` | Result cannot authorize work. |

**First-pilot exclusions:** all other projects; conversation or message bodies; proposal scope/expected result; CEO decisions/rationales; notification destination, errors, or attempt metadata; customer/personal data; arbitrary URLs; raw snapshot JSON; raw bridge response; external source contents; source evidence summaries; prompt or tool instructions found in upstream data. A later tool for identifier-only audit/proposal state requires a separate data-field approval and negative tests. The existing `project-readiness.json` is a local workspace projection, so the adapter must either label it `workspace_snapshot` with its original `observed_at` or omit it. The existing CEO-session record routes and v2 bridge cannot be treated as one authentication realm.

## Authentication choice to review before implementation

**Recommended:** a dedicated private MCP resource with OAuth 2.1 authorization-code + PKCE using an established identity provider, rather than turning the existing Google browser session or CEO bearer token into connector credentials. A separately approved deployment would expose only the MCP read endpoint and OAuth metadata over HTTPS. The selected provider must support protected-resource metadata, authorization-server discovery, audience/resource binding, read scope, token expiry and revocation. No new identity provider is selected by this document.

For every tool call the resource server must validate token signature, issuer, audience/resource, `exp`/`nbf`, read scope, and the bound CEO principal; then apply the fixed `phil-ai-os` project constraint. An OpenAI client certificate, IP allowlist, tool annotation, or model instruction is **not** an alternative to end-user authorization. Reject missing/invalid/cross-owner tokens before reading any source. Keep access tokens out of tool output and logs. Return 401/403 without revealing whether a private record exists. Rate and byte caps apply even to authenticated reads.

**No credential bridging:** do not forward a Google session cookie, CSRF token, Mission Control CEO bearer, Telegram token, OpenAI API key, protected encryption key, or OAuth refresh token to a tool response or model. If an internal adapter later needs access to both read realms, its service identity and exact per-source mechanism require their own security review. Do not accept arbitrary source URLs or reverse-proxy the existing APIs.

## Reviewable verification gate

1. Contract tests with fixed fixtures prove the exact allowlist and `additionalProperties: false`, limits, timestamps, unknown/stale handling, and no raw-text leakage.
2. Auth tests reject unauthenticated, expired, wrong-issuer, wrong-audience, missing-scope, wrong-owner, and revoked tokens before any upstream read.
3. A static tool-inventory test proves no POST/PUT/PATCH/DELETE, generic HTTP, provider dispatch, notification, approval, assignment, or execution tool exists.
4. Only after owner approval of this field/auth boundary may an **offline** fixture implementation be proposed. Network connection, OAuth enrollment, endpoint exposure, production deployment, and any live read remain separate gates.

## Evidence and unresolved decisions

- Repository inspection: `apps/operations-hub/mission-control/project-readiness.json` declares a workspace `read_only` projection; the browser explicitly says sources are not queried on page load. `contracts/mission-control/agent-posture-bridge-response.v2.schema.json` is bounded but contains more fields than the pilot needs. `ops/mission-control-identity/google_ceo_session.py` uses a browser CEO session for conversation/audit reads; `ops/mission-control-public/read-model-bridge.py` uses a separate bearer boundary.
- [Official OpenAI documentation on MCP authentication](https://developers.openai.com/plugins/build/auth) requires OAuth user authentication for private data and server-side validation of signature, issuer, audience, expiry, and scope.
- [Official OpenAI documentation on MCP tools](https://developers.openai.com/plugins/build/mcp-server) says read-only annotations do not replace authorization and describes private connection controls.
- The owner must approve the **exact first-pilot field list** and the separate OAuth boundary before implementation. The specific identity provider and network exposure/rollback design remain open engineering decisions for review; this document does not authorize selecting or deploying them.
