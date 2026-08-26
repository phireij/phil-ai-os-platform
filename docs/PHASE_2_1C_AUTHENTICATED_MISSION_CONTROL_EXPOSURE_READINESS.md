# Phase 2.1C — Authenticated Mission Control Exposure & Deployment Readiness

**Program:** Phil AI OS Platform  
**Date:** 2026-08-26  
**Status:** STARTED — DISCOVERY / CONTRACT DEFINITION  
**Predecessor:** Phase 2.1B GREEN / CLOSED

## Objective

Prepare the validated read-only Mission Control dashboard for controlled operator access without creating a new authority path or weakening Phase 1 controls.

Phase 2.1C is not an approval/execution feature phase. Its purpose is to define and validate the deployment boundary, authentication boundary, routing boundary, rollback plan, and observability requirements before any externally reachable Mission Control dashboard is activated.

## Required invariants

1. Mission Control remains read-only.
2. POST/PUT/PATCH/DELETE remain unavailable.
3. Production execution allowlist remains `general` only.
4. Direct provider bypass remains prohibited.
5. Authority expansion remains blocked.
6. Existing Telegram approval flow remains authoritative.
7. Existing Control API approval/execution routes remain authoritative.
8. Monitoring, backups, and self-heal remain independent of the dashboard.
9. No raw Control API token, provider key, Telegram token, SSH key, or approval review token is exposed to the browser.
10. Browser access must be authenticated before external exposure is allowed.

## Discovery workstreams

### 1. Existing ingress / Traefik surface

Read-only discovery must identify:

- currently active Traefik routers/services/middlewares;
- existing TLS/Let's Encrypt configuration;
- whether an existing authenticated operator path can be reused;
- current Mission Control approval-review routing and hostname/path convention;
- any collision risk with existing `/phil-ai-os/approval/*` routes.

No Traefik mutation is authorized during discovery.

### 2. Authentication boundary

The operator dashboard must not depend on exposing the Hermes Control API bearer token to a browser.

Preferred architecture:

`Browser -> authenticated reverse proxy/operator session -> read-only dashboard service -> local Control API/read model`

The browser should receive only rendered/read-model data that has already passed redaction rules.

Authentication options must be evaluated against the existing stack. Selection criteria:

- strong operator authentication;
- no secret embedded in URL query strings;
- short-lived/revocable session where practical;
- auditable access;
- compatible with Traefik and current VPS footprint;
- minimal new operational burden.

### 3. Service boundary

The dashboard service should:

- bind to loopback or private Docker network only;
- never expose port `4881` directly to the public Internet;
- run with a dedicated low-privilege service identity where practical;
- have read-only access to required local state/interfaces;
- have no provider credentials;
- have no SSH key;
- have no arbitrary host-shell endpoint;
- have no approval mutation endpoint;
- have no execution endpoint.

### 4. Read-model refresh behavior

Refresh must remain side-effect free.

Required checks:

- repeated refresh does not change approval count;
- repeated refresh does not change execution-audit count;
- no provider call occurs;
- no execution call occurs;
- stale/unavailable sources produce degraded/unknown state rather than false healthy state;
- refresh rate is bounded to avoid unnecessary control-plane load.

### 5. Operator observability

Before controlled exposure, Mission Control access should have at least:

- dashboard service health/readiness;
- access-log visibility without credential leakage;
- degraded state indication;
- process/service restart behavior;
- monitor awareness of dashboard availability if added later, without making dashboard health a replacement for core monitor health.

### 6. Rollback boundary

Any Phase 2.1C deployment must be independently removable.

Rollback target:

- remove/disable dashboard route;
- stop dashboard service;
- leave Control API, Hermes, Telegram approvals, monitor, backups, and execution governance unchanged;
- preserve `general`-only production execution scope.

## Activation preconditions

No externally reachable dashboard route should be enabled until a dedicated validation gate proves:

1. authentication is required;
2. unauthenticated requests fail closed;
3. authenticated GET access succeeds;
4. mutation methods remain blocked;
5. no browser-visible secret is returned;
6. no direct Control API bearer token is delivered to client-side code;
7. the dashboard backend is not directly Internet-listening;
8. TLS is active for operator access;
9. approval/audit counts remain unchanged during validation;
10. provider/execution/approval mutation and production change remain none except for the explicitly approved dashboard deployment/routing change;
11. rollback is tested or mechanically verified.

## Explicitly not authorized in Phase 2.1C discovery

- enabling a public dashboard route;
- adding Approve/Deny buttons;
- adding Execute/Retry buttons;
- changing provider/model routing;
- adding specialist-agent execution rights;
- changing production allowlist;
- adding autonomous task delegation;
- changing Telegram approval authority;
- weakening TLS/authentication requirements.

## CTO recommendation

Proceed with **read-only ingress/authentication discovery first**, then create a deployment plan and validation workflow. Only after that gate is reviewed should the authenticated dashboard route be activated.

`PHIL_AI_OS_PHASE_2_1C_AUTHENTICATED_EXPOSURE_READINESS_STARTED`
