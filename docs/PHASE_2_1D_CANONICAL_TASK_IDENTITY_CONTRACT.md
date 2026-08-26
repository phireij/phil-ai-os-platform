# Phase 2.1D — Canonical Task Identity Contract

Status: **DEFINED — READ-ONLY COMPATIBILITY CONTRACT**
Date: 2026-08-27
Program: Phil AI OS Platform

## Canonical identifier

The canonical task identifier is `task_id`.

Compatibility readers may also accept `canonical_task_id` as an alias while migration is incomplete. Writers introduced in a later implementation increment must emit `task_id` as the canonical field.

## Requirements

A canonical task ID must be:

- durable across approval, execution, audit, and closure records
- non-secret
- immutable after task creation
- unique within the Phil AI OS control plane
- carried forward across handoffs without changing authority
- supplemental to existing immutable `approval_id` and `execution_id` values

## Correlation rules

A record is **canonical** only when it contains a genuine `task_id` (or temporary compatibility alias `canonical_task_id`).

Readers must not synthesize task IDs from timestamps, text, approval IDs, execution IDs, hashes of request text, or list position.

Approval and execution IDs remain independently authoritative and immutable.

## Legacy compatibility

Historical records that do not contain a canonical task ID remain unchanged.

They must be classified as:

- `legacy` when records exist but none contain a canonical task ID
- `partial` when canonical and legacy records coexist
- `canonical` when all observed records participating in correlation contain a canonical task ID
- `none` when no approval/execution records are currently available for correlation validation

No historical rewrite is authorized by Phase 2.1D.

## Lifecycle projection

When canonical records exist, Mission Control may project the task lifecycle from authoritative approval/execution state without mutating source records.

Allowed projected states follow the Phase 2.1 operating model:

`RECEIVED -> CLASSIFIED -> ASSIGNED -> PLANNED -> POLICY_CHECK -> APPROVAL_PENDING -> AUTHORIZED -> EXECUTING -> SUCCEEDED | FAILED | BLOCKED | CANCELLED -> AUDITED -> CLOSED`

Exception states: `DENIED`, `EXPIRED`, `REJECTED`, `AMBIGUOUS`, `CONTAINED`.

Projection must never grant or imply authority beyond the underlying source records.

## Agent ownership

`assigned_agent_id` is observational metadata. A handoff may change ownership metadata but must never increase authority.

If ownership is unavailable, the reader must leave it unavailable rather than infer an agent from task text.

## Current Phase 2.1D live evidence

The initial read-source discovery found zero recent approval records and zero recent execution records. Therefore live canonical correlation cannot yet be demonstrated from current recent-history payloads.

This is represented as `correlation_quality=none`, not as a failure and not as synthetic canonical history.

## Safety boundary

This contract does not:

- widen the production allowlist
- alter approval consumption
- change provider routing
- add browser mutation controls
- authorize autonomous delegation
- create provider calls or governed executions

Marker: `PHIL_AI_OS_PHASE_2_1D_CANONICAL_TASK_IDENTITY_CONTRACT_DEFINED`
