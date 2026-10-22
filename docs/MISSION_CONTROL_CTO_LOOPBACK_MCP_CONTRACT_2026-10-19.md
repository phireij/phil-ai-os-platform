# MC-021 private loopback MCP resource contract (19 October 2026)

## Approved offline design boundary

The owner approved an **offline-only** design and contract update for one future
owner-scoped, read-only MCP service. This document and the associated Python
contract do not create a Hostinger route, listener, runtime key, tunnel-client
profile, Auth0 object or setting, ChatGPT connection, or live Mission Control
read.

The approved canonical OAuth protected-resource identifier is exactly:

```text
https://miscon.phireij.cloud/mcp
```

It is an external resource identity and future token audience, not the address
on which the private service will listen. The offline contract uses the
resource-specific protected-resource metadata location:

```text
https://miscon.phireij.cloud/.well-known/oauth-protected-resource/mcp
```

This is a design contract only. Its discoverability through the future tunnel
and any HTTP route are unproven until a separately approved activation test.

## Private transport model

The future MCP process and future `tunnel-client` must share the approved
Hostinger runtime trust boundary. The MCP process is constrained to an injected
local endpoint matching this shape:

```text
http://127.0.0.1:<owner-approved-port>/mcp
```

The contract rejects `0.0.0.0`, public hostnames, non-loopback listeners,
alternate paths, query strings, fragments, and an implicit port. It does not
choose a port, start a process, or configure the tunnel. The only intended
future path from OpenAI products to that process is the already-created private
Secure MCP Tunnel after a later explicit runtime-key and execution approval.

## One-tool authorization contract

The proposed server advertises exactly one tool:

| Property | Offline contract |
| --- | --- |
| Tool | `get_phil_ai_os_status` |
| Inputs | none; the input schema is closed |
| Effect | fixed fixture-only Phil AI OS status projection |
| Tool policy | OAuth 2.1 with `mission_control:cto_read` only |
| Authority | none; no writes, dispatch, provider calls, assignments, or arbitrary URLs |
| Owner identity | a future trusted verifier must prove the separately configured owner subject; the current value is synthetic test data only |

The per-call authorization boundary remains fail-closed. Before a fixture is
loaded, a future trusted verifier must establish exact audience equality with
the canonical resource URI, required scope, expected owner subject, non-expiry,
and non-revocation. The offline code never parses a caller-controlled token or
contacts an identity provider.

## Protected-resource metadata and challenge behavior

The metadata document must declare the exact canonical `resource`, one
injected HTTPS authorization-server issuer, and the one read-only scope. The
issuer is deliberately not hard-coded because choosing or altering Auth0 remains
outside this approval.

An absent, expired, revoked, wrong-owner, wrong-audience, or insufficient-scope
credential returns only `authentication_required`. It must include
`_meta["mcp/www_authenticate"]` with a Bearer challenge pointing to the explicit
protected-resource metadata URI, `error="invalid_token"`, and a generic error
description. It must not expose a supplied credential, fixture contents, an
issuer secret, or identity-provider detail.

Official OpenAI documentation requires protected-resource metadata and tool
metadata as well as this MCP authentication challenge to trigger the ChatGPT
linking flow. It also requires the canonical resource identifier to be carried
through the OAuth flow and verified as the token audience. Secure MCP Tunnel can
keep the MCP service private and route OAuth discovery through the tunnel, but
the authorization server must remain reachable for OAuth. See [OpenAI MCP
authentication guidance](https://developers.openai.com/plugins/build/auth) and
[Secure MCP Tunnel guidance](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).

## Offline evidence

`apps/operations-hub/src/operations_hub/mission_control_cto_mcp_fixture.py`
now has an explicit protected-resource metadata URI rather than deriving one
from a resource host. Its `OfflineApprovedLoopbackMcpPlan` pins the approved
external resource identity to a supplied loopback-only local MCP URI. It has no
listener, credential loading, environment access, subprocess, network client,
or live source.

The associated isolated test suite passed **29 tests** on 19 October 2026. It
verifies the one-tool boundary, exact canonical resource, explicit metadata
location, loopback-only transport shape, denied non-loopback inputs, generic
challenge response, denial before a fixture read, and absence of network or
secret-source dependencies.

## Still prohibited and next activation gate

This approval does not authorize deployment, creation of a public `/mcp` route,
runtime-key generation, tunnel-client download/configuration/execution, Auth0
configuration, ChatGPT connection, token issuance, or live data access.

Before activation, the owner must separately approve the concrete Hostinger
runtime placement and local port, restricted runtime-key generation and storage,
Auth0 API/audience/scope configuration, resource-server token-verification
implementation, tunnel-client execution, and a non-production end-to-end test.
