# Phil AI OS Platform — Phase 2.2 A2 Isolated Handoff Contract v1

**Phase:** 2.2 A2 — Isolated Handoff Contract  
**Status:** CONTRACT DEFINED — ISOLATED VALIDATION REQUIRED  
**Date:** 2026-08-28  
**Production effect:** NONE

## Purpose

Define a fail-closed, durable handoff contract for transferring coordination ownership of an existing canonical task from one explicitly registered agent to another without expanding authority, changing approval semantics, triggering execution, or introducing automatic delegation.

This contract is off-production. It does not register a second worker and does not authorize a production handoff writer.

## Existing boundaries preserved

- Control API remains the authoritative coordinator/lifecycle writer.
- Agent registry remains the authoritative identity and authority-ceiling source.
- Mission Control remains read-only.
- Assignment is operational ownership only, not an authorization token.
- Worker readiness is evidence only and has no authority effect.
- Production execution allowlist remains `general` only.
- Human approval boundaries and one-time approval consumption remain unchanged.
- Direct provider bypass remains prohibited.

## Canonical handoff envelope

Every handoff proposal MUST have one immutable durable envelope containing:

```text
handoff_id                 opaque unique identifier
handoff_version            "2.2-a2.v1"
task_id                    canonical immutable task identity
source_agent_id            exact registered current owner
target_agent_id            exact registered candidate receiver
task_class                 already-classified task class
required_authority         bounded effective authority required by the task
source_authority_ceiling   registry snapshot at decision time
target_authority_ceiling   registry snapshot at decision time
reason_code                bounded non-secret machine-readable reason
correlation_id             durable unique handoff correlation identifier
requested_by               authorized coordinator/operator identity
requested_at               authoritative UTC timestamp
expires_at                 authoritative UTC expiry timestamp
handoff_approval_required  boolean
handoff_approval_state     not_required | pending | approved | denied | expired
execution_approval_state   observed task execution-approval state; never mutated by handoff
source_readiness           observed advisory readiness state
target_readiness           observed advisory readiness state
state                       requested | accepted | rejected | expired | contained
accepted_or_decided_by     authoritative actor when terminal
accepted_or_decided_at     authoritative UTC timestamp when terminal
containment_reason         bounded reason when contained
```

The durable record MUST NOT contain task text, prompts, model output, provider responses, credentials, bearer tokens, approval link tokens, or other secrets.

## Identity invariants

A handoff is invalid unless all are true:

1. `task_id` exists as a canonical task.
2. `source_agent_id` exactly matches the most recent valid durable `ASSIGNED` event for the task.
3. source and target are different exact `agent_id` values.
4. both identities exist in `agent_registry`.
5. both registry records are enabled.
6. target is assignable.
7. display name, requester, source, approval actor, execution consumer, provider, or model identity is never substituted for `agent_id`.

Missing or conflicting identity evidence => `contained`; no reassignment.

## Authority-containment invariants

Authority ceilings are ceilings, not grants.

A normal handoff is permitted only if:

```text
required_authority <= source_authority_ceiling
required_authority <= target_authority_ceiling
```

A handoff MUST NOT:

- increase the task's effective authority;
- increase either agent's registry authority ceiling;
- widen the production task-class allowlist;
- gain authority by selecting a higher-ceiling target;
- alter routing policy, credentials, provider/model selection, or execution kill switches;
- create self-approval permission.

A transfer that needs authority above the source ceiling is an **escalation**, not a handoff, and is outside A2.

## Task-class invariant

The handoff carries the task's already-classified `task_class`; it may not reclassify the task. Unknown, missing, or conflicting task-class evidence fails closed.

For current production compatibility, `general` is the only execution class in scope. A2 validation may use synthetic isolated examples, but it does not authorize any production class expansion.

## Readiness invariant

Readiness is a prerequisite evidence signal only; it never triggers a handoff.

For a normal accepted handoff, target readiness must be explicitly proven `ready` at decision time. `busy`, `stale`, `unassignable`, or `indeterminate` cannot be automatically rerouted around and cannot become acceptance by inference.

A `ready` target still requires an explicit authorized handoff decision and all remaining contract checks.

## Ownership and lifecycle semantics

### Request

Creating a handoff request MUST NOT append `ASSIGNED` and MUST NOT change current ownership. The source remains the authoritative owner.

### Acceptance

Acceptance is the only A2 outcome that changes coordination ownership. A successful authoritative acceptance MUST atomically:

1. revalidate the current assignment still equals `source_agent_id`;
2. revalidate target registry eligibility and authority containment;
3. revalidate task class, expiry, required handoff approval, and correlation/idempotency constraints;
4. persist the accepted handoff decision;
5. append exactly one new lifecycle `ASSIGNED` event for the same `task_id` with `assigned_agent_id=target_agent_id`, authoritative actor/source, reason code, and handoff correlation ID.

Historical source assignment events remain immutable. Current assignment is derived from the latest valid `ASSIGNED` event.

### Rejection / expiry / containment

`rejected`, `expired`, and `contained` MUST NOT append a target `ASSIGNED` event. The prior authoritative assignment remains in force.

Conflicting ownership detected at acceptance time MUST become `contained`, never last-write-wins reassignment.

## Approval semantics

Handoff and execution approval are separate governance facts.

- A handoff MUST NOT create, approve, deny, expire, consume, or otherwise mutate an execution approval.
- Existing execution-approval requirements continue unchanged after transfer.
- `handoff_approval_required=true` requires a durable `approved` handoff authorization before acceptance.
- missing, pending, denied, expired, or ambiguous required handoff approval => no acceptance.
- handoff approval never substitutes for execution approval.
- execution approval never substitutes for handoff authorization when handoff authorization is required.

Until a production role/capability policy is separately activated, cross-agent production handoff should be treated as requiring explicit human/operator authorization.

## Correlation, idempotency, and replay protection

- `handoff_id` is globally unique and immutable.
- `correlation_id` is required and durably reconstructable.
- A single handoff may reach only one terminal state.
- Replaying the same acceptance MUST NOT append a second `ASSIGNED` event.
- A second handoff for the same task must use a new `handoff_id` and correlation ID and must start from the then-current durable owner.
- Acceptance after expiry, rejection, containment, or prior acceptance fails closed.

## Expiry and containment

Every handoff request has a bounded expiry. Expired requests cannot be revived by retry.

Contain when any of the following is observed:

- current owner no longer matches source;
- target identity disappears or becomes disabled/non-assignable;
- authority evidence changes or conflicts;
- task class changes or cannot be proven;
- required approval evidence is ambiguous;
- durable correlation cannot be proven;
- duplicate/competing handoff acceptance is observed;
- lifecycle append cannot be proven atomic with accepted decision.

Containment requires operator/coordinator review; it never triggers automatic reroute.

## Required audit evidence

A completed handoff must be reconstructable from durable evidence showing:

- immutable handoff ID/version;
- canonical task ID;
- source and target identities;
- source assignment proof before handoff;
- source and target authority-ceiling snapshots;
- task class and required authority;
- reason and requester/decision actor;
- request/decision timestamps and expiry;
- required handoff approval state;
- observed execution-approval state without mutation;
- observed readiness evidence;
- terminal handoff outcome;
- one-and-only-one target `ASSIGNED` event if accepted;
- zero target `ASSIGNED` events if rejected/expired/contained;
- durable correlation between handoff decision and lifecycle event;
- proof of no authority, policy, approval, provider, credential, or execution mutation.

## Isolated validator acceptance criteria

A2 is GREEN only if isolated tests prove at minimum:

1. valid explicit handoff accepts and produces exactly one new target assignment;
2. request alone preserves source ownership;
3. unknown target fails closed;
4. disabled/non-assignable target fails closed;
5. unready target fails closed without reroute;
6. target ceiling below required authority fails closed;
7. required authority above source ceiling fails closed;
8. unknown/non-`general` current production class fails closed under current scope;
9. missing/ambiguous required handoff approval fails closed;
10. expired request fails closed;
11. conflicting current owner is contained;
12. replayed acceptance cannot duplicate assignment;
13. rejection preserves source ownership;
14. containment preserves source ownership;
15. handoff does not mutate execution approval or execute/call a provider.

## Production activation boundary

A2 approval is limited to this contract and isolated validation. It does **not** authorize:

- a production handoff table/schema;
- a production handoff mutation route;
- a second production worker;
- a production handoff canary;
- automatic assignment/delegation/retry/reroute;
- execution by a new worker;
- authority or task-class expansion.

Those remain subject to subsequent Phase 2.2 gates.
