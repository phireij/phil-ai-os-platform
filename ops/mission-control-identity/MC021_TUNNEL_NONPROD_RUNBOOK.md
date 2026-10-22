# MC-021 Synthetic Tunnel Acceptance Runbook

## Scope
This runbook covers only the isolated non-production Mission Control CTO fixture. It is read-only and does not establish production health.

## Verified acceptance - 2026-10-23 JST
- The private Secure MCP Tunnel connection completed in ChatGPT.
- OAuth authorization was refreshed for the read-only scope `mission_control:cto_read`.
- The synthetic-only status request completed successfully in ChatGPT.
- The response confirmed: no live production data, no writes, and no authority changes.
- The fixture reported overall status as `unknown`; this is expected and is not an operational-health result.
- Fixture tests passed: 16 tests in 0.005 seconds.

## Repeatable preflight
1. Run `python3 apps/operations-hub/tests/test_mission_control_cto_mcp_fixture.py` from the isolated checkout.
2. Verify the synthetic container is healthy and exposes no host ports.
3. Verify an unauthenticated request receives HTTP 401 with a `WWW-Authenticate` scope challenge.
4. In a new ChatGPT conversation, select the read-only plugin and request the synthetic-only status check.
5. Record the prompt, result, date, and safety assertions. Stop if any live-data or mutation path appears.

## Guardrails
- Keep the runtime key only in the root-owned VPS secret; never commit, display, or paste it into logs.
- Do not add public ingress, published ports, host networking, source-data mounts, or write-capable tools.
- Production access, operational health assertions, and any mutation require a separate reviewed change and approval.

## Evidence retained
- ChatGPT completed the synthetic status check with authority effect `none`.
- The synthetic container remained healthy with no published ports.
- The OAuth scope challenge fix is committed as `6c92ea6`.
