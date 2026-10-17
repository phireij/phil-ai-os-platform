# MC-021 — CTO connector authentication and exposure review

**Status:** Design decision for owner review only. PR #587's fixture projection is offline; no MCP server, OAuth client, tunnel, public route, credential, or live source connection exists or is authorized by this review.

## What is being protected

The first live-capable tool would return only the approved `phil-ai-os` status projection. Even identifier-only operational posture is owner-scoped private data. Existing Mission Control paths have distinct credentials and containers: Google OIDC establishes a browser CEO session for conversations and audit, while the read-model bridge uses its own CEO bearer. Neither is an MCP OAuth authorization server, and neither credential may be copied into a ChatGPT/Codex tool result, manifest, tunnel configuration, or model context.

The resource server must expose one read tool and **no** URL/path selector, arbitrary HTTP client, write tool, provider call, or raw pass-through to either existing API. It will validate a new user-scoped OAuth token on every request, then apply the fixed project restriction before using a separately reviewed internal read identity. The merged fixture projection is not an authorization or live-source adapter.

## Authentication boundary required for either transport

1. Use an established identity provider that supports OAuth 2.1 authorization-code + PKCE, protected-resource and authorization-server discovery, exact resource/audience binding, an `mission_control:cto_read`-equivalent scope, expiry, revocation, and stable CEO-principal mapping. Do not implement a custom authorization server merely to reuse the existing Google sign-in. The particular provider and its account terms/cost are **not selected**.
2. Validate access-token signature, issuer, audience/resource, validity window, scope, and the mapped CEO principal server-side on every call. Reject before any source read when missing, revoked, expired, cross-owner, or wrong-audience. Tool annotations and mTLS/IP restrictions supplement but do not replace this check.
3. Keep the OAuth resource separate from `miscon.phireij.cloud`'s current Google-cookie routes and bearer read bridge. Do not introduce a reverse proxy that accepts caller-chosen destinations or forwards browser cookies, CEO bearer values, encryption keys, or OAuth refresh tokens.
4. Record a content-free access audit (tool name, opaque connection/principal ID, time, outcome, source revision or unknown). Enforce request rate/response byte caps, a kill switch, credential revocation, and a tested rollback. A disconnected tool must cease returning new data.

These requirements follow [official OpenAI documentation for plugin authentication](https://developers.openai.com/plugins/build/auth): private data needs user auth, OAuth metadata and PKCE must be compatible, and the resource server must verify tokens. OpenAI's client mTLS proves a client transport identity, not the CEO's permission.

## Private connection options

| Option | Benefit | New dependency / risk | Decision |
|---|---|---|---|
| **A. Secure MCP Tunnel, owner-only pilot** | Outbound-only connection from a private host; no new public inbound route to the tool. Supported for private custom MCP testing, not public plugin distribution. | Requires a Platform-owned `tunnel_id`, tunnel permissions, a runtime API key for `tunnel-client`, workspace access to custom MCP servers, and a private MCP process reachable from the tunnel client. The runtime key is infrastructure credentialing, **not** authorization to make OpenAI inference calls or use a ChatGPT plan. OAuth owner auth is still required. Credential custody, cost/terms, isolation from existing workloads, and rollback must be reviewed separately. | **Preferred transport to evaluate for a first private pilot**, subject to confirming account availability and approving the additional credential and container. Do not provision it in this review. |
| **B. Stable public HTTPS proxy to private MCP service** | Does not depend on the Platform tunnel service; can support later public distribution if needed. | New internet-facing route and OAuth metadata; must verify TLS/mTLS client identity, user OAuth, routing isolation, rate limits, domain verification where applicable, and unchanged existing Traefik routes/workloads. Current repo routing text does not prove live Traefik compatibility. | Defer unless the tunnel is unavailable or a later distribution requirement justifies the larger exposure. No route approved. |
| **C. No live connector yet** | Use the merged fixture projection and manually reviewed status artifacts while continuing CTO planning in Codex/ChatGPT. No new credential or network exposure. | Not live and not “residing” inside Mission Control. | Safe default while A/B prerequisites remain unresolved. |

[Official OpenAI Secure MCP Tunnel guidance](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) confirms the outbound-only model, private-testing scope, runtime API-key and permission prerequisites. [Official connection guidance](https://developers.openai.com/plugins/deploy/connect-chatgpt) lists public HTTPS or tunnel and warns that workspace policies apply. [Official MCP server guidance](https://developers.openai.com/plugins/build/mcp-server) requires private-data authorization even for read-only tools.

## Phased verification and stop conditions

| Gate | Required evidence | Authority now |
|---|---|---|
| 1. Offline tool shell and auth contract | One tool descriptor, closed input/output schema, mocked authorization failures, no network use. It may wrap only the fixture projection and must not assert real OAuth or source acceptance. | Not yet implemented; may be proposed after this review. |
| 2. Identity provider choice | Verified discovery/PKCE/resource/scope support, CEO subject mapping, revoke behavior, terms/cost and protected credential plan. | Requires owner selection/approval. |
| 3. Transport choice | For tunnel: Platform availability/permissions and scoped runtime key plan. For proxy: live routing inventory, TLS/mTLS termination plan, exact path, and rollback. | Requires owner selection/approval; neither is provisioned. |
| 4. Private live acceptance | Exact image/revision, one authenticated read, wrong-owner/expired/revoked negatives, source provenance, logs without content/secrets, unchanged workloads, disconnect and rollback. | Separate deployment and live-read approval. |
| 5. Mission Control-hosted ChatGPT-plan inference | Independent eligibility for this remotely hosted/private app and explicit owner consent. | Unresolved and outside the read connector. Do not recommend Pro $100 for this gate. |

**Recommendation:** keep Option C until a separate owner decision on transport and identity provider. If the owner wants a private live pilot, evaluate Option A first without creating the tunnel or handling its runtime key during this design phase. A tunnel key must not be confused with the separately paused MC-010 inference API key; neither key is present in this design.
