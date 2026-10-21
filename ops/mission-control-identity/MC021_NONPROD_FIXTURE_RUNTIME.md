# MC-021 isolated non-production fixture runtime

This Compose workload is a deliberately dormant synthetic-only placement for
the existing `get_phil_ai_os_status` fixture. It is suitable for a shared VPS
because it has no host networking, published ports, Traefik route, Docker
socket, bind mounts, or access to the VPS's existing applications or data.

The fixture process binds only to `127.0.0.1:8787` **inside its own networkless
container**. The image contains only the committed synthetic readiness fixture.
It starts without an owner-subject credential, therefore every MCP tool call
fails closed before the fixture can be read. The health and metadata handlers
are inaccessible from the host and network.

Run a static validation from the repository root:

```powershell
docker compose -f ops/mission-control-identity/compose.mcp-fixture.nonprod.yml config -q
```

No deployment command is included here. Starting this workload on the VPS is a
separate change to the shared host and must be accompanied by the reviewed
image build and operator change record.

## Explicitly outside this runtime

- no OpenAI runtime API key;
- no `tunnel-client`, tunnel connection, or public `/mcp` route;
- no Auth0 tenant change, token issuance, or owner-subject credential;
- no live Mission Control source, database, Docker socket, or other service
  mount;
- no authority, writes, dispatches, provider calls, or assignments.

The later activation gate remains the concrete combined private-resource-server
and `tunnel-client` design. It must preserve the approved canonical resource
identifier, use an injected runtime key, retain loopback-only MCP transport,
and be approved independently before it is built or run.
