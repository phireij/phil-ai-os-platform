# MC-021 — owner-only CTO connector identity and cost review

**Decision state:** read-only assessment, not provider selection or setup. No Auth0 account, OAuth application, tunnel, runtime key, MCP endpoint, live source read, or production change is authorized by this document.

## Verified starting point

- The signed-in ChatGPT Plus Plugins UI offered **Add custom MCP server** with **Tunnel** and **OAuth** options on 17 October 2026. This proves the controls were visible, not that an end-to-end connection works or that future workspace policy cannot change.
- The signed-in PhilReij OpenAI Platform organization exposed tunnel settings and one selectable ChatGPT workspace; it showed **No tunnels yet**. Opening and cancelling the creation form did not create a tunnel. The UI did not establish actual create/use permissions or tunnel billing.
- PR #589 merged the one-tool offline fixture shell and synthetic denial tests. It has no MCP server, token verifier, network listener, or live read.
- Repository inspection found Google OIDC browser-session code, not an MCP authorization server or Auth0 integration. The website cookie and internal CEO bearer are not connector credentials.

## Candidate architecture, not an activation plan

ChatGPT (existing Plus account) → private Secure MCP Tunnel → isolated, read-only Mission Control MCP resource → fixed `phil-ai-os` status projection. Auth0 is a **candidate** authorization server for the CEO's OAuth 2.1 authorization-code/PKCE flow. The OAuth authorization endpoint must be browser-reachable even when the MCP resource is private; the tunnel does not automatically carry that endpoint.

Only `get_phil_ai_os_status` would be exposed. It has no caller-selected URL, project, path, or write operation. The resource would require a token scoped to `mission_control:cto_read`, validate signature/issuer/audience/expiry/scope and an exact approved CEO-subject mapping on every invocation, and reject before any source access. The synthetic `phil-ai-os-ceo` value in the offline shell is **not** a live principal. The existing Google login may remain for the website, but must not be forwarded or silently equated with a newly issued Auth0 subject. Auth0 discovery, CIMD or DCR compatibility, resource/audience binding, revocation behavior, and the CEO mapping must be proved with negative tests before a live read.

OpenAI's [MCP authentication guidance](https://developers.openai.com/plugins/build/auth) names Auth0 as a provider example and recommends an established identity provider. It requires protected-resource and authorization-server metadata, user authorization, and resource-server token validation. Its [Secure MCP Tunnel guidance](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) requires a tunnel ID, runtime API key, Platform tunnel permissions, workspace association, and a client host that can reach the private MCP service. Tunnel transport does not replace user OAuth.

## Published price, plan caveats, and unresolved total

| Item | What is known | Must be confirmed before procurement or activation |
|---|---|---|
| ChatGPT | The owner currently has Plus and the custom MCP controls were visible. The ChatGPT-side connector uses ChatGPT as the interaction surface; this does not establish eligibility for Mission Control-hosted ChatGPT-plan inference. | Any workspace restriction or usage limit relevant to this connection. Do not buy Pro solely for this pilot. |
| Auth0 | On 17 October 2026, [Auth0's B2C monthly pricing](https://auth0.com/pricing) listed Free at **US$0/month** (up to 25,000 monthly active users), Essentials from **US$35/month** (500 MAU), and Professional from **US$240/month** (500 MAU). Its comparison table lists **Auth for MCP as included on Free**. This is published list pricing, not a tenant quote or approval to subscribe. | Confirm the owner-only use fits the Free plan and current terms. Free shows one-day log retention, no role management, and no Private Key JWT (Enterprise-only); a custom domain needs credit-card verification. If the pilot needs those features or longer provider-side logs, re-price and obtain separate approval. No Auth0 tenant or approved data-processing region exists. |
| OpenAI tunnel | Platform and ChatGPT UIs expose the feature; none exists. Official docs require a runtime API key but state no account-specific tunnel charge in the reviewed guidance. | Verify Platform billing/terms and least-privilege runtime-key permissions; do not assume a zero bill or use the separate inactive MC-010 inference key. |
| Isolated runtime | The design needs a private MCP process and continuously running tunnel client. No host/container resources or deployment approved. | Incremental VPS/container operation and monitoring cost, image supply chain, secret storage, backup and rollback scope. |

**Budget conclusion:** A one-owner Auth0 Free *evaluation* may have a US$0/month Auth0 subscription line if its terms and feature limits fit; that is not a zero-cost claim for the full connector. OpenAI tunnel account-specific billing and incremental runtime cost remain unverified, so no numerical end-to-end total is defensible. No paid plan, purchase, subscription change, or tenant creation is part of this review.

**Compatibility caveat:** [Auth0's MCP audience guidance](https://support.auth0.com/center/s/article/mcp-audience-error-with-auth0) says MCP's `resource` parameter can otherwise fall back to the wrong audience; its Resource Parameter Compatibility Profile must be enabled for that flow. This is a future tenant-setting change, not performed here. The [Auth0 MCP overview](https://auth0.com/ai/docs/mcp/overview) confirms client registration and resource-scoped tokens, but an actual Free tenant still must prove CIMD or DCR, `resource` → exact API audience, PKCE, read scope, token validation, and revocation. Prefer CIMD with a public-client method if verified; [Auth0 states Private Key JWT is Enterprise-only](https://auth0.com/docs/secure/application-credentials). Do not purchase Enterprise by default.

## Recommended decision sequence

1. Owner decides whether to **evaluate Auth0 Free as the identity provider** for this owner-only connector, with a **US$0/month Auth0-plan ceiling and no automatic paid upgrade**. This document is not approval to create an account. If selected, review Auth0 terms/data region and verify discovery, registration method, resource parameter, read scope, token validation, revocation, and subject mapping in a non-production proof.
2. Separately approve a private tunnel implementation plan: exact Platform organization/workspace, permission roles, restricted runtime key custody, isolated client host, no inbound route, fail-closed disconnect and rollback.
3. Build and review the real MCP resource and verifier offline first. Distinguish protocol/discovery tests from authorization tests; use synthetic or test-only tokens and fixture data.
4. Ask separately for credential creation, connection, any live source access, and deployment. No acceptance claim until an owner-authenticated read and wrong-owner/expired/revoked negatives pass on the exact candidate.

**Stop conditions:** unknown provider terms/cost, unavailable tunnel permissions, an OAuth server that cannot satisfy the MCP contract, ambiguous CEO identity mapping, any credential reuse across the browser/bridge/connector boundaries, or accidental exposure of a public/write endpoint. On any of these, remain offline and keep MC-010 inactive.
