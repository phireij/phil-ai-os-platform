# Phil AI OS Platform — Phase 2.1H Lifecycle Writer Ownership Contract

**Status:** DESIGN APPROVED FOR ISOLATED VALIDATION ONLY  
**Date:** 2026-08-27

## Discovery basis

Read-only writer-hook discovery run `33036118620` completed GREEN with marker `PHIL_AI_OS_PHASE_2_1H_WRITER_HOOK_DISCOVERY_OK`.

Relevant live Control API functions include:

- `classify_task(text_value)`
- `evaluate_route(task_class)`
- `approval_create(task_text, source, requester, requested_by)`
- `approval_decide(approval_id, decision, decision_by, note)`
- `approval_consume(approval_id, task_text, consumed_by)`
- `routed_execute(task_text, source, approval_id)`
- `execution_audit_write(..., approval_id)`

## Writer ownership decision

Lifecycle ledger writes remain inside the Control API boundary for events that are already made authoritative by existing Control API operations.

Approved isolated-candidate mappings:

- `RECEIVED` — append in `approval_create` after canonical `task_id` exists and before returning success.
- `CLASSIFIED` — append in `approval_create` after `classify_task` has returned a durable task class.
- `APPROVAL_PENDING` — append in `approval_create` only when the durable approval row is successfully created in pending state.
- `AUTHORIZED` — append in `approval_decide` only after the durable approval state transitions to approved.
- `DENIED` — append in `approval_decide` only after durable state transitions to denied.
- `EXPIRED` — may be appended by the approval-expiry path only when a durable state transition to expired actually occurs; this needs isolated validation before inclusion.
- `AUDITED` — append only after `execution_audit_write` has successfully persisted the audit row.

Candidate-only mappings requiring additional care:

- `POLICY_CHECK` — may be emitted inside `routed_execute` only if tied to an explicit route/policy evaluation result, not merely inferred from function entry.
- `EXECUTING` — may be emitted immediately before `_provider_execute` only if failure-before-provider-call semantics are made explicit and testable.
- terminal execution stage (`SUCCEEDED`, `FAILED`, `BLOCKED`, `CANCELLED`) — may be emitted only from authoritative execution outcome paths and must not replace `execution_audit` as the execution record of truth.

Not authorized in this increment:

- `PLANNED` — no authoritative planner persistence exists.
- `CLOSED` — no explicit close operation exists.
- `ASSIGNED` — no current Control API field proves assignment. It requires a distinct explicit assignment writer/interface.

## Assignment writer contract

A future explicit assignment function may append an `ASSIGNED` event only when all of the following are true:

1. canonical `task_id` exists;
2. `assigned_agent_id` is explicitly supplied by an authorized coordinator/operator path;
3. the target agent exists in the declared operating model;
4. assignment does not widen authority level or allowed task classes;
5. assignment does not imply approval or execution authorization;
6. prior assignment/handoff remains auditable through another append-only event.

Mission Control/browser remains a reader, not a writer.

## Transaction semantics

Lifecycle events tied to a domain mutation should be written in the same SQLite transaction where practical. If the domain mutation succeeds but lifecycle append fails, the candidate must fail closed or expose the partial condition explicitly; silently dropping audit lifecycle events is not acceptable.

Lifecycle persistence must never cause a provider call, approval decision, execution authorization, or authority expansion that would not otherwise occur.

## Isolated candidate exit criteria

Before production is considered, an isolated candidate must prove:

- application compiles;
- ledger migration is additive;
- `approval_create` generates canonical `task_id` and appends truthful creation lifecycle events;
- approval decision appends only matching approved/denied events;
- audit append occurs only after execution audit persistence;
- no assignment is inferred;
- existing approval/execution semantics and return shapes remain backward compatible;
- legacy DB rows remain unchanged;
- no live DB/application mutation occurs during validation.
