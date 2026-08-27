# Phil AI OS Platform — Phase 2.1H Persistence Contract v1

**Status:** CONTRACT DEFINED — IMPLEMENTATION NOT YET AUTHORIZED  
**Date:** 2026-08-27

## Decision

Use a dedicated append-only `task_lifecycle_events` ledger for durable task lifecycle evidence. Do not overload `approval_requests.state` or `execution_audit.outcome` into a complete task lifecycle.

Agent assignment, when introduced, is represented as lifecycle evidence and does not grant execution authority.

## Evidence from the current platform

Phase 2.1F established server-generated canonical `task_id` at approval creation and propagates it to execution audit by authoritative `approval_id` lookup. Historical records may retain NULL `task_id`; fabricated backfill is prohibited.

The existing approval and execution tables therefore remain authoritative for their own domains, while a lifecycle ledger can reference the immutable canonical `task_id` without changing approval semantics.

## Proposed append-only event contract

A future isolated candidate may add:

```text
task_lifecycle_events
- event_id TEXT PRIMARY KEY
- task_id TEXT NOT NULL
- stage TEXT NOT NULL
- occurred_at TEXT NOT NULL
- actor_id TEXT NULL
- assigned_agent_id TEXT NULL
- source_component TEXT NOT NULL
- prior_stage TEXT NULL
- reason_code TEXT NULL
- metadata_json TEXT NULL
```

This is a migration candidate contract, not authorization to mutate production.

### Allowed stages

`CREATED`, `APPROVAL_PENDING`, `APPROVED`, `DENIED`, `ASSIGNED`, `PLANNED`, `POLICY_CHECK`, `EXECUTING`, `SUCCEEDED`, `FAILED`, `CLOSED`.

Stage presence means only that an authoritative writer emitted that event. Absence must remain `unavailable`; Mission Control must not infer missing stages from timestamps or neighboring records.

## Writer ownership

- Control API is the only initial writer allowed for lifecycle events that correspond to Control API actions.
- A future task coordinator may become the authoritative writer for `ASSIGNED` and `PLANNED`, but only after a separately gated contract identifies that component.
- Execution boundary code may emit `POLICY_CHECK`, `EXECUTING`, `SUCCEEDED`, or `FAILED` only when those transitions actually occur through the controlled execution path.
- Mission Control is never a lifecycle writer during Phase 2.1H.

## Assignment semantics

`assigned_agent_id` is observational routing/ownership metadata only.

An assignment MUST NOT:

1. change an agent authority level;
2. add task classes to the production allowlist;
3. bypass approval consumption;
4. select a provider outside routing policy;
5. authorize execution;
6. be derived from `requester`, `requested_by`, `source`, or `consumed_by`.

A valid `ASSIGNED` event requires an explicit authoritative assignment writer. Until that exists, assignment remains unavailable.

## Append-only guarantees

Application code must have INSERT-only lifecycle semantics. No lifecycle UPDATE or DELETE endpoint is permitted.

Corrections must be represented by a later event rather than rewriting prior evidence. Database-level hardening against UPDATE/DELETE should be evaluated in isolated validation before production activation.

## Compatibility

- Existing `approval_id` values remain immutable.
- Existing non-null `task_id` values remain immutable.
- Historical NULL `task_id` rows remain valid and are not fabricated/backfilled.
- Existing approval states remain approval states, not lifecycle states.
- Existing execution audit rows remain execution evidence, not a substitute for missing lifecycle events.
- Read models must support tasks with zero lifecycle-ledger rows.

## Candidate emission map

Initial implementation should be incremental rather than attempting the entire lifecycle at once:

1. `CREATED` + `APPROVAL_PENDING` at canonical approval/task creation.
2. `APPROVED` or `DENIED` at authoritative human approval decision.
3. Execution stages only after isolated proof that the controlled execution boundary can emit them without changing execution behavior.
4. `ASSIGNED` and `PLANNED` remain unavailable until an authoritative coordinator/assignment component exists.
5. `CLOSED` remains unavailable until closure semantics are separately defined.

## Migration safety requirements

Before any production schema change:

- copy the live SQLite database to an isolated validation file;
- apply the candidate table/index/trigger migration only to the copy;
- verify `PRAGMA quick_check=ok` before and after;
- verify approval/execution row counts and existing identities are unchanged;
- prove append-only enforcement behavior;
- prove legacy NULL task IDs remain untouched;
- validate candidate application emission on an isolated application/database pair;
- create production backup and rollback artifacts;
- canary production activation separately.

## Authority invariants

Throughout Phase 2.1H:

- production allowlist remains `general` only;
- direct provider bypass remains prohibited;
- human approval remains authoritative;
- one-time approval consumption remains unchanged;
- Mission Control remains read-only;
- no assignment event can authorize execution.

## Next gate

Build and run an **isolated lifecycle-ledger migration validator**. A GREEN validator permits consideration of a production migration candidate; it does not itself authorize production activation.
