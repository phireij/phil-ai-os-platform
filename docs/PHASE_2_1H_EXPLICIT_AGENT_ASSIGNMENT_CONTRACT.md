# Phil AI OS Platform — Phase 2.1H Explicit Agent Assignment Contract

**Status:** DESIGN CONTRACT — NOT ACTIVE IN PRODUCTION  
**Date:** 2026-08-27

## Purpose

Define how Phil AI OS may persist an authoritative `ASSIGNED` lifecycle event without confusing request provenance, approval ownership, or execution consumers with task ownership.

## Explicit-only rule

An assignment exists only when an authorized assignment operation explicitly names:

- canonical `task_id`
- target `assigned_agent_id`
- assigning actor/coordinator identity
- UTC assignment timestamp
- optional bounded reason code

The following fields must never be treated as assignment by inference:

- `source`
- `requester`
- `requested_by`
- `decision_by`
- `consumed_by`
- provider/model identity

## Assignment does not grant authority

Persisting `assigned_agent_id` must not change:

- authority level;
- production task-class allowlist;
- approval requirements;
- self-approval prohibition;
- execution kill switch;
- provider routing;
- credential access;
- ability to call the provider directly.

Assignment means responsibility/ownership for coordination only.

## Proposed future function

A future Control API/coordinator function may have semantics equivalent to:

`task_assign(task_id, assigned_agent_id, assigned_by, reason_code=None)`

Required validation before it appends an `ASSIGNED` event:

1. task exists as a canonical `task_id`;
2. target agent exists in the declared operating model;
3. target agent's declared authority is sufficient for the already-classified task but is not modified by assignment;
4. the caller is an authorized coordinator/operator path;
5. assignment is not being used to approve, consume approval, or execute;
6. previous assignment remains durable in the event ledger.

## Handoff semantics

A handoff is a new `ASSIGNED` event for the same `task_id`. Historical assignment events are never updated or deleted.

Mission Control derives current assignment from the most recent valid `ASSIGNED` event for a task. It must also expose assignment provenance and history.

## Revocation / unassignment

Do not overload `ASSIGNED` with null values. If unassignment is needed, introduce an explicit future event such as `UNASSIGNED` or `ASSIGNMENT_REVOKED` under a separate contract.

## Browser boundary

Mission Control remains read-only during Phase 2.1H. No browser assignment button or mutation endpoint is authorized by this contract.

## Production status

No explicit assignment writer exists in production yet. `assigned_agent_id` remains authoritative-source-unavailable in the live Phase 2.1G read model until a separately validated writer is activated.
