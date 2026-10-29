# MC-021 live-status tunnel activation

This overlay is a separate, non-production, outbound-only connector for the
read-only live-status MCP server. It adds no host port, Traefik route beyond
the base file's two approved OAuth-protected MCP/metadata paths, or mutation
capability.

## VPS custody

`/etc/phil-ai-os/secrets/mc021-live-status-tunnel.env` is root-owned with mode
`0600`.  It is the only location for these runtime values:

- `CONTROL_PLANE_API_KEY` — a 30-day restricted key with Tunnels Read + Use.
- `CONTROL_PLANE_TUNNEL_ID` — the distinct live-status tunnel identity.

Neither value belongs in Git, an image, a container mount, a Compose file, or
terminal output.

## Deploy

From `/opt/phil-ai-os-platform/mc021-main-runtime`, source the root-only file
for the single Compose invocation:

```sh
set -a
. /etc/phil-ai-os/secrets/mc021-live-status-tunnel.env
set +a
docker compose \
  -f ops/mission-control-identity/compose.mcp-live-status.nonprod.yml \
  -f ops/mission-control-identity/compose.mcp-live-status.tunnel.nonprod.yml \
  up -d --build
unset CONTROL_PLANE_API_KEY CONTROL_PLANE_TUNNEL_ID
```

The only startup checks are the local MCP health endpoint and the tunnel-client
health endpoint.  A live Mission Control status request occurs only after a
valid owner credential invokes the sole read-only MCP tool.

## Discovery target boundary

The runtime permits plaintext HTTP only for its trusted container-local MCP
origin so tunnel-client can auto-register the protected-resource metadata
endpoint as its Harpoon discovery target. This enables ChatGPT's internal
discovery channel without adding a route beyond the base file's two approved
OAuth-protected paths, permitting arbitrary URLs, supplying credentials to
Harpoon, or authorizing a live-status request. No host port is published, and
the tunnel-client health listener remains loopback-only.

OAuth discovery trusts only the existing Auth0 issuer origin for its public
metadata documents. This does not grant that issuer MCP, source, or tunnel
authority; it lets tunnel-client complete the metadata resolution required by
the already-configured OAuth connection.
