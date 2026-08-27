# Phil AI OS Platform — Phase 2.1I Controlled Production Activation Contract

**Status:** ACTIVATION CONTRACT DEFINED  
**Date:** 2026-08-27

## Scope

Activate the already isolated-validated Control API coordinator capability without creating a production task, assignment, plan, execution, provider call, or approval decision.

## Baseline

The GREEN production preflight (`33042828172`) established:

- Control API image `phil-ai-os/control-api:0.20.2-phase21h`;
- health/readiness GREEN;
- durable lifecycle ledger present with zero rows;
- no live `agent_registry` or `task_plans` tables;
- candidate builds and compiles from the exact live app;
- coordinator routes are behind the existing Control API auth gate;
- Mission Control `2.1h.v1`, read-only;
- production allowlist `general` only;
- operator auth `401` when unauthenticated;
- dashboard mutation methods `405`;
- monitor, backup timer and backup self-heal active.

## Candidate production state

Target image:

`phil-ai-os/control-api:0.20.3-phase21i`

Candidate schema additions:

- `agent_registry`;
- `task_plans`;
- immutable `agent_id` trigger;
- append-only `task_plans` UPDATE/DELETE blockers.

Initial registry seed:

- `agent_id=hermes`;
- role `operational_worker`;
- authority ceiling `L3`;
- enabled=true;
- assignable=true;
- source component `control-api`.

The seed is identity/capability metadata only. It does not authorize execution.

## Activation sequence

1. Verify exact baseline image, DB integrity, absence of new coordinator tables, zero lifecycle rows, `general`-only policy and recovery services.
2. Record existing public operator/approval/Mission Control route statuses.
3. Back up the exact Compose file and SQLite database.
4. Build the candidate app from the exact live `/app/app.py` using the validated Phase 2.1I builder.
5. Build a local child image from `0.20.2-phase21h` containing only the candidate app.
6. Apply the validated coordinator schema to the live SQLite database.
7. Verify `agent_registry` contains exactly the intended Hermes seed and `task_plans` is empty.
8. Change only the Control API image reference in Compose to `0.20.3-phase21i`.
9. Recreate only the Control API service.
10. Require health/readiness GREEN and exact candidate image/app hash.
11. Require lifecycle row count, approval row count and execution-audit row count unchanged from pre-activation.
12. Require unauthenticated `/v1/tasks/assign` and `/v1/tasks/plan` requests to return `401` without side effects.
13. Require production allowlist to remain exactly `general`.
14. Require monitor, backup timer, backup self-heal and operator service active.
15. Require existing public operator/approval/Mission Control statuses to converge back to their pre-activation values.
16. Require Mission Control browser mutation methods to remain `405`.

## Canary non-actions

The production activation MUST NOT:

- create a canonical task or approval request;
- emit `ASSIGNED` or `PLANNED`;
- insert a production `task_plans` row;
- call `/v1/execute`;
- call any provider;
- approve, deny or consume an approval;
- alter provider/model/routing configuration;
- change the `general`-only allowlist;
- increase Hermes authority above its existing L3 ceiling;
- add Mission Control mutation controls.

## Rollback

Any failure after the first mutation automatically:

1. restores the pre-2.1I Compose file;
2. stops only Control API;
3. restores the pre-2.1I SQLite snapshot;
4. recreates Control API on `0.20.2-phase21h`;
5. waits for health/readiness.

Rollback must restore absence of `agent_registry` and `task_plans` because the database snapshot predates their creation.

## GREEN criteria

Phase 2.1I production coordinator capability is GREEN only when all activation checks pass with:

- new image active;
- coordinator schema present;
- exactly the bounded Hermes registry seed;
- zero task plans;
- zero lifecycle events created by activation;
- coordinator routes fail closed without auth;
- existing approval/execution counts unchanged;
- `general`-only and recovery/security boundaries preserved;
- no provider/execution/approval side effects;
- no authority expansion.

Mission Control read-model/dashboard visibility for registry/plans remains a separate read-only follow-up after the canary is GREEN.
