# Phase 2.1F — Controlled Production Activation Contract

Status: **DEFINED — ACTIVATION REQUIRES GREEN PREFLIGHT**

## Purpose

Introduce genuine canonical `task_id` persistence into the existing approval → execution → audit chain without changing provider routing, execution authority, approval authority, production allowlists, or Mission Control mutation capabilities.

## Verified deployment shape

- Control API container: `phil-ai-os-core-control-api-1`
- Current image: `phil-ai-os/control-api:0.20.0`
- Current image ID observed during readiness discovery: `sha256:18f5afa07b213a8b74c21e3eca08676089530b008bb4830f3be53a45177ba513`
- Container app path: `/app/app.py`
- App is baked into the image; it is not bind-mounted.
- SQLite state is persisted on Docker volume `phil-ai-os-core_control-api-state` at `/app/state`.
- Compose working directory: `/opt/phil-ai-os-platform/phil-ai-os-platform-phase1/infrastructure/core`
- Compose file: `/opt/phil-ai-os-platform/phil-ai-os-platform-phase1/infrastructure/core/compose.yml`

## Activation architecture

The production change must be durable across container recreation. Therefore activation will:

1. verify the current image/app hash and existing production invariants;
2. create rollback copies of the Compose file and SQLite database;
3. build a local child image from `phil-ai-os/control-api:0.20.0` containing only the previously validated canonical-task application patch;
4. apply the nullable `task_id` schema migration transactionally to the live SQLite database:
   - `approval_requests.task_id TEXT NULL`;
   - `execution_audit.task_id TEXT NULL`;
   - unique partial index on non-null approval `task_id`;
5. leave all historical rows `NULL` (no speculative backfill);
6. change only the Control API service image reference in Compose to the new local Phase 2.1F image;
7. recreate only the Control API service;
8. verify health/readiness and existing approval/execution/read-only Mission Control behavior;
9. run a bounded canonical-task canary that does **not** invoke a provider;
10. automatically rollback application + database state if any post-change gate fails.

## Canonical task authority

- `task_id` is generated once by the Control API inside `approval_create()`.
- Format: `tsk_<uuid4 hex>`.
- Callers cannot supply or override canonical `task_id`.
- Execution audit derives `task_id` from the persisted approval selected by `approval_id`.
- `approval_id` remains the approval authority/correlation identifier; it is not replaced by `task_id`.

## Hard preflight gates

Activation must not begin unless all are true:

- Control API health and readiness are OK;
- current Control API image is the expected baseline;
- current `/app/app.py` hash matches the discovered baseline;
- live DB `quick_check=ok`;
- live DB has no `task_id` columns yet;
- production allowed task classes are exactly `general`;
- monitor active;
- backup timer active;
- backup self-heal active;
- Mission Control operator dashboard remains read-only and authenticated;
- existing approval and Mission Control routes remain reachable in their current states;
- no provider call;
- no governed execution call;
- no approval mutation;
- no authority expansion.

## Rollback

Rollback must restore:

1. the original Compose file;
2. the pre-activation SQLite database copy;
3. the original `phil-ai-os/control-api:0.20.0` service image via Compose recreation.

The new local child image may remain unused after rollback or be removed after rollback verification.

Rollback verification requires:

- Control API health/readiness OK;
- DB `quick_check=ok`;
- approval/execution row counts restored;
- original schema restored without `task_id` columns;
- production allowlist still `general` only;
- monitoring/backups/self-heal active.

## Explicit non-goals

Phase 2.1F does not:

- widen production task classes;
- change provider/model routing;
- enable direct provider bypass;
- change approval decisions or Telegram authority;
- add browser mutation controls;
- grant Hermes or specialist agents additional authority;
- backfill historical canonical task IDs;
- autonomously execute a provider call as part of migration validation.

Marker:

`PHIL_AI_OS_PHASE_2_1F_CONTROLLED_PRODUCTION_ACTIVATION_CONTRACT_DEFINED`
