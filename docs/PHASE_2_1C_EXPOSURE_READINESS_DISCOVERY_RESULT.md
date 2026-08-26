# Phase 2.1C — Authenticated Mission Control Exposure Readiness Discovery Result

**Program:** Phil AI OS Platform  
**Date:** 2026-08-26  
**Status:** DISCOVERY GREEN / AUTH BOUNDARY REQUIRED BEFORE ACTIVATION

## Result

The live read-only discovery gate completed successfully and confirmed that the current VPS ingress foundation is suitable for a future authenticated Mission Control browser route, but **public/browser exposure is not yet authorized** because no reusable authentication middleware is currently present.

## Proven current state

- Traefik stack exists at `/docker/traefik-fhxl`.
- Traefik container is running.
- Traefik has active Docker network membership.
- TLS/ACME/Let's Encrypt configuration signals are present.
- HTTP-to-HTTPS redirection signal is present.
- Docker provider signal is present.
- Traefik dashboard insecure/public exposure signal is absent.
- Reverse-proxy ports 80/443 are present.
- Mission Control prototype has no public listener.
- Production execution allowlist remains `general` only.
- Monitoring, backup timer and backup self-heal remain active.
- No provider call, execution call, approval mutation or production change occurred during discovery.

## Authentication finding

`reusable_auth_middleware_signal=false`

This is the principal Phase 2.1C gap. Mission Control MUST NOT be routed to a public/browser hostname until an explicit authentication boundary exists.

## Security decision

Do not reuse the Control API bearer token, provider API keys, Telegram token, SSH credentials or approval-review tokens as a browser password.

The Mission Control browser credential must be independent and narrowly scoped to Mission Control read access.

## Recommended activation architecture

```text
Internet/browser
      |
      v
Traefik :443 / TLS
      |
      v
Mission Control authentication middleware
      |
      v
read-only Mission Control service
      |
      v
validated Phase 2.1A read model
      |
      v
Control API governed read sources
```

Required properties:

1. HTTPS only.
2. Authentication before proxying to Mission Control.
3. Mission Control backend is not directly published to the Internet.
4. Backend remains read-only; mutation HTTP methods remain blocked.
5. Control API stays the authority source.
6. `general` remains the only production execution class.
7. Existing Telegram approval path remains unchanged.
8. Monitoring/backups remain independent of the dashboard.
9. Rollback removes the Mission Control router/service without disturbing Traefik or Control API.

## Proposed authentication mechanism for first controlled release

Use a dedicated Traefik `basicAuth` middleware for the initial operator-only release, with a dedicated randomly generated Mission Control credential stored outside the public repository. This is intentionally a temporary operator authentication layer and can later be replaced by stronger SSO/identity-aware access without changing Control API authority.

Do NOT activate the route unless the credential hash is available as protected deployment material and the cleartext password is handled outside Git history and workflow logs.

## Activation preflight requirements

A Phase 2.1C activation gate must prove, before applying changes:

- dedicated Mission Control authentication material exists;
- no secret value is printed;
- desired hostname is explicit;
- DNS/TLS route can be validated;
- backend listener remains non-public;
- router includes authentication middleware;
- mutation methods remain blocked;
- rollback bundle is generated;
- Phase 1/2.1A safeguards remain healthy;
- no provider/execution/approval mutation occurs in preflight.

## Discovery evidence marker

`PHIL_AI_OS_PHASE_2_1C_EXPOSURE_READINESS_DISCOVERY_OK`

## CTO decision

**Proceed to authenticated-exposure activation preflight. Do not expose Mission Control until the auth-material gate is GREEN.**
