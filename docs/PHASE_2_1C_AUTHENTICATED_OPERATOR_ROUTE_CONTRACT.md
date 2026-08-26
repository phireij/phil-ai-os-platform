# Phase 2.1C — Authenticated Operator Route Contract

**Program:** Phil AI OS Platform  
**Date:** 2026-08-26  
**Status:** ROUTE CONTRACT DEFINED / AUTH MATERIAL PENDING

## Live routing evidence

Read-only production discovery confirmed the existing Phil AI OS browser routing convention:

- secure host: `hermes-agent-whow.srv1833510.hstgr.cloud`
- approval route: `Host(...) && PathPrefix(`/phil-ai-os/approval/`)`
- existing Mission Control route: `Host(...) && PathPrefix(`/phil-ai-os/mission-control`)`
- entrypoint: `websecure`
- TLS certificate resolver: `letsencrypt`
- existing Phil AI OS service target: Control API port `4870`

The existing `philaios-mission-control` router MUST NOT be repurposed or weakened by Phase 2.1C because it is already part of the validated Phase 1 approval/control surface.

## Selected operator-dashboard route

Phase 2.1C will use the existing secure hostname and a distinct path:

`https://hermes-agent-whow.srv1833510.hstgr.cloud/phil-ai-os/operator/`

This avoids a new DNS dependency while keeping the new read-only operator dashboard logically separate from the existing approval and Mission Control routes.

## Authentication

The first controlled operator release will use a dedicated Traefik `basicAuth` middleware.

Requirements:

- dedicated Mission Control/operator credential only;
- credential hash stored as protected deployment material, never Git;
- no reuse of Control API bearer token, provider keys, Telegram token, SSH credentials or approval-review tokens;
- unauthenticated requests fail closed;
- authentication occurs before proxying to the dashboard backend.

The only new protected value required for the first route is:

`MC_BASIC_AUTH_HASH`

The hostname is not treated as secret and is fixed by the proven live routing convention above.

## Backend isolation

The operator dashboard backend must remain non-public and must not publish port `4881` to the Internet. The route may only be activated once the deployment gate proves Traefik can reach the backend through a private/local service boundary.

The dashboard must remain read-only:

- GET/HEAD only for operator content/read model;
- POST/PUT/PATCH/DELETE return 405;
- no approval mutation endpoint;
- no execution endpoint;
- no provider credentials;
- no arbitrary host-shell endpoint.

## Route collision rules

The new route MUST NOT shadow or modify:

- `/phil-ai-os/approval/`
- `/phil-ai-os/mission-control`
- Hermes root/application routes

The operator router should use an explicit distinct router/service/middleware name, for example:

- router: `philaios-operator`
- middleware: `philaios-operator-auth`
- service: `philaios-operator`

## Activation sequence

1. validate `MC_BASIC_AUTH_HASH` exists without printing it;
2. verify current Phase 1/2 safeguards;
3. verify existing approval and Mission Control routes are unchanged;
4. establish private dashboard backend service;
5. add authenticated `/phil-ai-os/operator/` Traefik route;
6. prove unauthenticated request is rejected;
7. prove authenticated GET succeeds;
8. prove mutation methods remain blocked;
9. prove browser output contains no secret material;
10. prove approval/audit counts unchanged by dashboard access;
11. retain rollback bundle that removes only operator route/backend.

## Rollback target

Rollback must restore the state that existed before operator-dashboard activation:

- no `/phil-ai-os/operator/` route;
- no operator dashboard backend service;
- existing `/phil-ai-os/approval/` and `/phil-ai-os/mission-control` routes unchanged;
- Control API, Hermes, Telegram approval flow, monitoring, backups and self-heal unchanged;
- production execution allowlist remains `general` only.

## Current decision

**Route design is ready. Activation remains blocked only on dedicated browser authentication material and final private-backend deployment validation.**

`PHIL_AI_OS_PHASE_2_1C_AUTHENTICATED_OPERATOR_ROUTE_CONTRACT_DEFINED`
