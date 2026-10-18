# MC-021 next identity and transport gate (18 October 2026)

PR #595 merged the offline MCP-facing fixture contract. This did not create a network server, OAuth verifier, Auth0 object, tunnel, ChatGPT connection, or live read. The next action is an owner decision, not deployment.

## Sequence and exact values

1. **Transport/resource identifier:** choose an owner-approved private OpenAI Secure MCP Tunnel endpoint before finalizing the canonical HTTPS MCP resource URI. No literal endpoint or API audience exists yet. Do not use the synthetic `mcp.example.test` test URI or `mission-control-cto-read` sentinel. Tunnel creation, runtime key, workspace association, and any local tunnel-client execution require their own approval and cost/permissions review.
2. **Auth0 resource server (later gate):** in the existing Free Development tenant `dev-81f0leykwbfdtibz` / JP-1, register exactly one API whose identifier equals the approved canonical MCP resource URI; expose only the `get_phil_ai_os_status` read scope. The exact scope string is the code constant `mission_control:cto_read`. Do not use a broad default API or production tenant.
3. **Auth0 client (later gate):** evaluate one pre-registered public OAuth client, authorization-code + PKCE S256, with no client secret. Copy the exact callback URL from the ChatGPT connection's management page at that future step; do not guess it. No DCR or CIMD tenant setting is authorized. ChatGPT compatibility of this path is not yet proven.
4. **Audience mapping (later gate):** OpenAI sends the exact protected-resource `resource` in the authorization and token requests. Auth0 documents that the Resource Parameter Compatibility Profile may need to be enabled to map that parameter to the API audience. This is a tenant-setting change and needs separate owner approval and verification. Without it, stop on any opaque, userinfo-audience, or mismatched-audience token; never weaken per-call checks.
5. **Runtime (later gates):** implement and test real signature, issuer, audience, expiry, subject, and scope validation; then seek separate approval for any test identity, credentials, tunnel connection, live Mission Control read, and deployment. Keep ChatGPT-subscription plan eligibility distinct from MCP connectivity; the read connector does not make Mission Control-hosted inference use the subscription.

## Approval needed next

The current offline approval does **not** authorize creating a tunnel, application, API, client, user, credential, token, or changing tenant settings. The next meaningful external step is a narrow non-production tunnel/endpoint decision so the canonical resource identifier can be fixed. Before that decision, present the exact OpenAI organization/workspace, tunnel permissions, runtime-key handling, and any price/usage implications. If these cannot be confirmed read-only, remain offline.

References: [OpenAI MCP authentication](https://developers.openai.com/plugins/build/auth), [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels), [Auth0 MCP resource/audience compatibility](https://support.auth0.com/center/s/article/mcp-audience-error-with-auth0).
