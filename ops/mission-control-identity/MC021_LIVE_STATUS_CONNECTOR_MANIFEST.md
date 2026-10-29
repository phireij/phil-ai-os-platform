# MC-021 live-status connector manifest

This connector is a separate, non-production workload. It has one read-only
tool, `get_mission_control_live_status`, and no mutation, approval, execution,
delegation, or credential-issuance path. It publishes no host port. Its only
public entrypoints are the existing OAuth-protected Traefik paths
`/mcp/live-status` and
`/.well-known/oauth-protected-resource/mcp/live-status`; no other public route
is permitted.

## Fixed source allowlist

| Source | Request | Returned facts |
| --- | --- | --- |
| Mission Control UI health | `GET https://miscon.phireij.cloud/healthz` | HTTP status, derived health state, collection timestamp |
| Mission Control gateway health | `GET https://miscon.phireij.cloud/api/healthz` | HTTP status, derived health state, collection timestamp |

The manifest rejects every other source ID or URL, all credentials, redirects,
non-GET methods, response bodies, headers, and response persistence.  It caps
each discarded response at 16 KiB and each call at five seconds.

## Custody and activation boundary

The base Compose file deliberately has no host port, tunnel client, OpenAI
runtime key, or live credential. It defines only the two approved Traefik
paths above, both bound to the dedicated MC-021 Auth0 resource
`https://miscon.phireij.cloud/mcp/live-status` and the read-only scope. Its
isolation comes from the separate tunnel workload, dedicated resource audience,
one-tool contract, root-managed owner-subject file, and fixed source allowlist.
The runtime key and owner-subject file remain VPS-managed secrets; they must
never be committed or printed.
