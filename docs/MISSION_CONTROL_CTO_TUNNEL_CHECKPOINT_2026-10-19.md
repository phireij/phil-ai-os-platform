# MC-021 Secure MCP Tunnel checkpoint (19 October 2026)

## Verified record

The owner approved creation of exactly one non-production OpenAI Secure MCP Tunnel. Platform confirmed the resulting record:

- name: `phil-ai-os-mission-control-cto-read-nonprod`;
- tunnel ID: `tunnel_6ad562a9e7e08191ae10c64acae2db8d`;
- Platform organization: `org-hRtVQUiiWEG9CckI9dlmjenq`;
- ChatGPT workspace: `29ccef25-3e3e-46a8-bc80-fc5978c84981`;
- description: future owner-scoped, read-only Mission Control CTO status tool with no authority.

The owner recorded that Phil is the future restricted runtime-key custodian. A future key is to reside only in the approved Hostinger runtime's protected secret/environment store, with a recovery copy in Phil's password manager; it must not be in Git, chat, screenshots, or plaintext files.

No runtime API key was generated. No `tunnel-client` was downloaded, installed, configured, or run. No MCP listener, ChatGPT custom-MCP connection, Auth0 application/API/client/user/token/setting, Hostinger configuration, live Mission Control read, deployment, provider request, assignment, execution, or authority change occurred.

## Resource-identifier reconciliation

The Platform record supplies a `tunnel_id`; it does not display a canonical HTTPS MCP-resource URI. OpenAI's Secure MCP Tunnel guidance configures a private connection by `tunnel_id`, while the MCP authorization guidance requires the resource server to publish protected-resource metadata at an HTTPS URL and to use the exact canonical HTTPS resource URI as the OAuth `resource` value and token audience.

Therefore the tunnel ID must not be substituted for the resource URI, and no hostname or API audience may be guessed from it. The fixture's synthetic `https://mcp.example.test/cto-proof` remains non-deployable.

### Owner-approved future identifier

On 19 October 2026 JST, the owner approved this exact future non-production canonical resource URI:

`https://miscon.phireij.cloud/mcp`

It is reserved only for the owner-scoped, read-only Mission Control MCP resource. When implementation is separately approved, the resource server must advertise this exact value in its protected-resource metadata; Auth0 must use the same byte-for-byte API identifier/audience; and the authorization and token requests must preserve it as OAuth `resource`. The existing `/api` gateway and `/auth/google/callback` route are not altered by this decision.

The approval is an identifier reservation only. It does not authorize route deployment, runtime-key generation, `tunnel-client` execution, Auth0 configuration, a ChatGPT connection, or a live Mission Control read. The approved Auth0 JP-1 Development tenant remains unchanged.

## Offline verification

Using the workspace-provided Python runtime, the isolated worktree passed all 27 MC-021 fixture, tool-shell, and MCP-facing fixture tests. The checks retain the one closed-input `get_phil_ai_os_status` tool, exact synthetic audience equality, metadata challenge shape, and denial before a fixture read for invalid authentication. These tests are offline only and do not validate OAuth, a network listener, the tunnel, or real Mission Control data.

## Remaining blocker

The resource URI decision is complete. The next gate is still not runtime-key generation. Before credential or transport work, define and review the future resource-server placement, its protected-resource-metadata/challenge behavior for the approved URI, and its compatibility with the private Secure MCP Tunnel path. The identifier must later equal the Auth0 API identifier, OAuth `resource` parameter, and accepted token audience byte-for-byte.

Until that implementation design receives its own approval, do not generate a runtime key, configure `tunnel-client`, create Auth0 objects or tenant settings, add a ChatGPT connection, or read live Mission Control data.

References: [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels); [OpenAI MCP authentication](https://developers.openai.com/plugins/build/auth).
