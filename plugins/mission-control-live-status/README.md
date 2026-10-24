# Phil AI OS Mission Control — Live Status plugin

This portable plugin package connects only to the public HTTPS MCP endpoint:

`https://miscon.phireij.cloud/mcp/live-status`

It declares the sole OAuth scope `mission_control:cto_read` as a base scope so
ChatGPT requests it during every authorization flow. The package contains no
credentials. The server exposes one owner-scoped, read-only tool and retains
no live Mission Control response content.

Upload this directory as the plugin package only after the HTTPS endpoint and
its protected-resource metadata both pass the deployment verification.
