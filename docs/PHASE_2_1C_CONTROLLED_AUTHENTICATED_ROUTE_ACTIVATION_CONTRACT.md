# Phase 2.1C — Controlled Authenticated Operator Route Activation Contract

**Program:** Phil AI OS Platform  
**Date:** 2026-08-27  
**Status:** READY FOR ACTIVATION AFTER PREFLIGHT GREEN  
**Predecessor:** Phase 2.1C authenticated-exposure preflight

## Objective

Activate the validated read-only Mission Control dashboard for authenticated operator browser access using the existing secure Phil AI OS host, without widening execution authority or creating a second control-plane authority path.

## Fixed operator route

- Host: `hermes-agent-whow.srv1833510.hstgr.cloud`
- Path: `/phil-ai-os/operator/`
- TLS entrypoint: `websecure`
- Certificate resolver: existing `letsencrypt`
- Authentication: dedicated Traefik `basicAuth` middleware using protected `MC_BASIC_AUTH_HASH`

The route is intentionally separate from:

- `/phil-ai-os/approval/`
- `/phil-ai-os/mission-control`

## Hard activation gate

Activation MUST NOT run until the corrected Phase 2.1C authenticated exposure preflight is GREEN.

Required preflight evidence:

1. dedicated auth material present without being logged;
2. SSH and Traefik baseline healthy;
3. existing approval and Mission Control routes preserved;
4. operator route absent before activation;
5. backend port `4881` not publicly listening;
6. production execution allowlist remains `general` only;
7. monitor, backup timer and backup self-heal active;
8. no provider call, execution call, approval mutation or production change during preflight.

## Deployment boundary

The first controlled activation may make only the following additive changes:

1. install the already-validated read-only dashboard service artifact;
2. bind the backend only to loopback/private service boundary, never `0.0.0.0:4881`;
3. add a dedicated Traefik service/router for `/phil-ai-os/operator/`;
4. add dedicated `basicAuth` middleware using protected deployment material;
5. preserve existing Control API, Hermes, Telegram approval, monitoring, backup and execution-governance configuration.

No provider/model migration, allowlist widening, specialist-agent authority, approval mutation behavior, execution retry mechanism, or autonomous task delegation is authorized.

## Application-layer read-only boundary

The current dashboard prototype accepts GET requests only for its UI/read model. POST/PUT/PATCH/DELETE respond with HTTP 405 and `mutation_not_available`.

The deployment must preserve this behavior. Reverse-proxy authentication is an additional perimeter control, not a replacement for application-layer read-only behavior.

## Post-activation validation

A GREEN activation must prove:

- unauthenticated browser request fails closed with authentication challenge;
- authenticated GET succeeds over HTTPS;
- TLS certificate is valid on the existing host;
- dashboard backend remains non-public;
- POST/PUT/PATCH/DELETE remain 405 after authentication;
- browser response does not expose Control API bearer tokens, provider keys, Telegram tokens, SSH material, BasicAuth hash or approval-review tokens;
- repeated dashboard reads do not change approval or execution-audit counts;
- existing `/phil-ai-os/approval/` and `/phil-ai-os/mission-control` routes remain functional;
- `PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=general` remains unchanged;
- monitor, backup and self-heal remain active;
- no provider call or governed execution is invoked by dashboard validation.

## Rollback contract

Before activation, snapshot the current route/service configuration required to restore the pre-2.1C state.

Rollback must:

1. remove/disable only the `philaios-operator` router/service/middleware;
2. stop/remove only the operator dashboard service if newly installed;
3. leave existing Traefik, Control API, Hermes and approval routes unchanged;
4. leave Telegram approvals unchanged;
5. leave monitoring/backups/self-heal unchanged;
6. preserve `general`-only execution scope;
7. verify the operator route is no longer externally reachable.

## Phase 2.1C closure condition

Phase 2.1C may close GREEN only after both the authenticated activation and the post-activation validation pass with rollback evidence available.

`PHIL_AI_OS_PHASE_2_1C_CONTROLLED_AUTHENTICATED_ROUTE_ACTIVATION_CONTRACT_DEFINED`
