# AO-MVP Hosted Orchestrator Runtime Plan

Status: PLAN ONLY — NO DEPLOYMENT AUTHORITY

## Goal
Run the already-tested bounded service loop outside Chat so it can wake on a recurring cadence, select authorized A1 engineering work, persist lifecycle/replay state, verify outcomes, and escalate anything outside authority.

## Proposed runtime shape
1. One orchestrator service instance with a durable writable state volume.
2. Minimum scheduler cadence of 60 seconds; initial operating cadence should be conservative rather than continuous busy-looping.
3. Single-worker lease with heartbeat and expiry recovery.
4. Durable dispatch ledger plus per-work terminal state.
5. Read-only project/evidence adapters by default.
6. Provider executors absent until separately authorized and individually allowlisted.
7. Structured logs/health/readiness metrics; no Mission Control mutation.
8. Restart policy must preserve state volume and fail closed if state cannot be read.
9. Secrets supplied only at runtime and never committed; initial bounded service should require no production credentials.
10. Rollback = stop service and revert autonomy to A0 without deleting evidence.

## Deployment gates
Before any hosted activation:
- choose approved host/runtime;
- verify persistent-volume behavior across restart;
- verify single-worker exclusion under concurrent start;
- verify corrupted/missing state fails closed;
- verify logs contain no secrets/customer data;
- verify network egress is unnecessary or explicitly allowlisted;
- verify A1 denylist remains enforced end-to-end;
- verify stop/rollback procedure;
- record exact image/revision and CI evidence;
- obtain separate approval if activation changes infrastructure or creates a continuously running external service.

## Explicitly out of scope
Production publish/cutover, DNS, payments/refunds/orders, customer messaging, inventory/slot mutation, credentials mutation, Twilio, KCFC production action, PR merge, or authority widening.
