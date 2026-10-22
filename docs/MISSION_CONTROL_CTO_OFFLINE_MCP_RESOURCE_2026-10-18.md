# MC-021 offline MCP resource and registration decision (18 October 2026)

This is a fixture-only design and test implementation, not a deployable MCP server or authentication proof. It exposes no listener, route, token verifier, Auth0 client, tunnel, ChatGPT connection, or live Mission Control source.

## Canonical protected resource identifier

The canonical identifier must be the **exact HTTPS MCP endpoint URL eventually exposed to ChatGPT by an owner-approved transport**. That same byte-for-byte URI must be used as the OAuth `resource` parameter, the protected-resource metadata `resource`, and the token audience checked on every tool call. It must not be the existing internal `mission-control-cto-read` sentinel, the Auth0 issuer URL, or a guessed tunnel hostname. The owner subsequently approved the exact future non-production identifier `https://miscon.phireij.cloud/mcp` on 19 October 2026 JST. This records a future resource identity only; it does not create a route, listener, runtime key, tunnel-client configuration, Auth0 object, ChatGPT connection, or live source read. The offline contract continues to require an injected HTTPS URI and has no default. Its `mcp.example.test` test URI is synthetic and must never be deployed.

At an eventual separate transport gate, record the approved endpoint URL, its protected-resource metadata location, and the audience mapping, then re-run exact-match negative tests before any external connection. The offline metadata builder advertises only the approved `get_phil_ai_os_status` scope/tool and the authorization issuer supplied by the caller. The proposed issuer for a later non-production proof is `https://dev-81f0leykwbfdtibz.jp.auth0.com/`; this is an identity-provider address, not the MCP resource identifier. No issuer is contacted here.

## ChatGPT-compatible OAuth registration approach

OpenAI documents three client registration paths: Client ID Metadata Document (CIMD), Dynamic Client Registration (DCR), and a pre-registered OAuth client. The read-only Auth0 discovery checkpoint did not advertise CIMD support or a DCR registration endpoint. Therefore the bounded candidate is a **separately approved, pre-registered public client using authorization-code PKCE S256** with the exact callback and client settings supplied by the ChatGPT connector configuration at that future gate. No client secret should be embedded in this resource or browser. This is a candidate, not a compatibility claim: the registration must be reviewed against the then-current ChatGPT UI and Auth0 Free/JP-1 settings before creating anything. If ChatGPT requires CIMD or DCR for this connection, or Auth0 cannot accept and issue the exact resource audience without a separately approved change, stop; do not enable DCR, alter tenant settings, or fall back to an unreviewed client.

The future server must verify token signature and issuer, exact resource audience, owner subject binding, expiry/revocation, and single read scope on **every** call. It must serve protected-resource metadata, return an MCP authentication challenge, and expose only the closed-input, read-only `get_phil_ai_os_status` tool. The present fixture builder models metadata, listing, challenge, audience equality, and response shape using an injected synthetic verification result. It is not an OAuth implementation, HTTP/MCP transport, live security boundary, or authorization to read real data.

## Gates and acceptance

1. Offline tests: one tool, no caller-selected arguments, HTTPS identifier injection, metadata/audience equality, positive committed-fixture projection, and denial before fixture read for missing or wrong authentication.
2. Separately approve Auth0 application/API/client configuration after reviewing the exact ChatGPT registration fields, terms, region, and US$0/month ceiling. Do not create users, credentials, or tokens under this checkpoint.
3. Separately approve any tunnel, production connection, live source read, and deployment. The canonical literal URI cannot be finalized before the transport decision. ChatGPT subscription-backed inference eligibility is a separate question and is not proven by an MCP read tool.

References: [OpenAI MCP authentication](https://developers.openai.com/plugins/build/auth); [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).
