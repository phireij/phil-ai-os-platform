# MC-021 live-status connector manifest

This connector is a separate, non-production, loopback-only workload.  It has
one read-only tool, `get_mission_control_live_status`, and no mutation,
approval, execution, delegation, credential-issuance, or public-listener path.

## Fixed source allowlist

| Source | Request | Returned facts |
| --- | --- | --- |
| Mission Control UI health | `GET https://miscon.phireij.cloud/healthz` | HTTP status, derived health state, collection timestamp |
| Mission Control gateway health | `GET https://miscon.phireij.cloud/api/healthz` | HTTP status, derived health state, collection timestamp |

The manifest rejects every other source ID or URL, all credentials, redirects,
non-GET methods, response bodies, headers, and response persistence.  It caps
each discarded response at 16 KiB and each call at five seconds.

## Custody and activation boundary

The base Compose file deliberately has no public port, tunnel client, OpenAI
runtime key, or live credential.  The live-status connector uses the existing
MC-021 Auth0 resource `https://miscon.phireij.cloud/mcp` and its already
approved read scope.  Its isolation comes from the separate tunnel workload,
one-tool contract, root-managed owner-subject file, and fixed source allowlist;
it does not create an additional audience, scope, or public route.  The runtime
key and owner-subject file remain VPS-managed secrets; they must never be
committed or printed.
