# Phil AI OS Platform — Phase 2.2 A6.5 Handoff Persistence / Writer Contract v1

**Phase:** 2.2 A6.5 — Handoff Persistence/Writer Isolated Validation  
**Status:** CONTRACT DEFINED — ISOLATED VALIDATION REQUIRED  
**Date:** 2026-08-28  
**Production effect:** NONE

## Architectural decision

Extend the existing authenticated **Control API coordinator boundary**. Do not create a second coordinator service and do not make Mission Control a writer.

Candidate internal routes:

- `POST /internal/coordinator/handoff/request`
- `POST /internal/coordinator/handoff/accept`
- `POST /internal/coordinator/handoff/reject`

All routes inherit authenticated internal Control API semantics. A caller cannot become authoritative merely by supplying coordinator fields.

## Durable table

Additive candidate table: `task_handoffs`.

Required fields:

```text
handoff_id TEXT PRIMARY KEY
handoff_version TEXT NOT NULL
task_id TEXT NOT NULL
source_agent_id TEXT NOT NULL
target_agent_id TEXT NOT NULL
task_class TEXT NOT NULL
required_authority TEXT NOT NULL
source_authority_ceiling TEXT NOT NULL
target_authority_ceiling TEXT NOT NULL
reason_code TEXT NOT NULL
correlation_id TEXT NOT NULL UNIQUE
requested_by TEXT NOT NULL
requested_at TEXT NOT NULL
expires_at TEXT NOT NULL
handoff_approval_required INTEGER NOT NULL
handoff_approval_state TEXT NOT NULL
execution_approval_state TEXT
source_readiness TEXT
target_readiness TEXT
state TEXT NOT NULL
decided_by TEXT
decided_at TEXT
containment_reason TEXT
lifecycle_event_id TEXT UNIQUE
```

Indexes:

- `(task_id, requested_at, handoff_id)`
- `(state, expires_at)`

No task text, prompts, provider payloads, credentials, bearer tokens, approval links, or unrestricted notes may be stored.

## Server-derived fields

The caller may supply only bounded intent:

### Request body

```text
task_id
target_agent_id
reason_code
requested_by
```

The server MUST derive and persist:

- current source owner from latest valid `ASSIGNED` lifecycle evidence;
- task class from authoritative task/classification evidence;
- required authority from authoritative task/policy evidence;
- source and target authority ceilings from `agent_registry`;
- source/target readiness snapshots from authoritative read-model inputs;
- execution-approval state as an observation only;
- handoff approval requirement/state;
- handoff/correlation IDs, timestamps, and expiry.

The caller cannot override these derived values.

## Request semantics

A successful request:

1. authenticates the coordinator caller;
2. proves canonical task identity and current source owner;
3. proves target registry identity exists;
4. snapshots bounded non-secret evidence;
5. creates exactly one `requested` handoff row;
6. creates **no new `ASSIGNED` event**;
7. changes no approval/execution policy.

For initial Phase 2.2 production policy, cross-agent requests default to `handoff_approval_required=true` and `handoff_approval_state=pending` unless a separately governed human-authorization mechanism has already produced authoritative approval evidence.

## Accept semantics

Acceptance is the only handoff operation that may transfer coordination ownership. It MUST execute one database transaction that revalidates:

1. authenticated coordinator caller;
2. handoff state is exactly `requested`;
3. not expired;
4. current durable owner still equals recorded `source_agent_id`;
5. target exists, is enabled, and assignable;
6. target readiness is authoritatively `ready` at decision time;
7. task class remains exactly the recorded class and current production scope is `general`;
8. required authority remains unchanged and fits both source and target registry ceilings;
9. source/target ceiling evidence has not changed ambiguously;
10. required handoff approval is authoritatively `approved`;
11. execution-approval evidence remains separate and is not mutated;
12. correlation/replay constraints remain valid.

Only then may the same transaction:

- append exactly one target `ASSIGNED` lifecycle event with the handoff correlation ID; and
- update the handoff row to `accepted` with the lifecycle event ID and decision actor/time.

If either write fails, neither ownership nor handoff state may partially commit.

## Inert-production property

A future A6.7 activation MUST remain inert with the current specialist registry state:

```text
specialist-worker-01
enabled=false
assignable=false
```

Therefore any attempt to accept a handoff to the specialist MUST fail closed and append zero target assignment events until a separately authorized A6.8 eligibility change occurs.

The existence of the writer surface is not authority.

## Reject / expiry / containment

- `reject`: terminal `rejected`, no target assignment.
- expired request: terminal `expired`, no target assignment.
- owner/identity/authority/class/readiness/approval conflict: terminal or fail-closed `contained`, no target assignment.
- competing ownership never uses last-write-wins.

## Replay / idempotency

- `handoff_id` and `correlation_id` are immutable and unique.
- repeated accept after a successful acceptance returns the already accepted outcome and MUST NOT append another `ASSIGNED` event.
- repeated reject cannot alter an already terminal handoff.
- a later handoff for the same task requires a new ID/correlation and must begin from the then-current durable owner.

## Approval separation

The handoff writer does not create, approve, deny, expire, or consume execution approvals.

A6.5 does not authorize a general agent-accessible method for marking `handoff_approval_state=approved`. Initial production cross-agent authorization remains a distinct human/governance action.

## No-authority / no-execution boundary

These handoff routes MUST NOT:

- widen task classes;
- change registry authority ceilings;
- enable/disable agents;
- create provider credentials;
- call `/v1/execute`;
- call providers;
- self-approve handoff;
- consume execution approval;
- introduce automatic retry/reroute/delegation/execution;
- give Mission Control mutation capability.

## A6.5 isolated acceptance criteria

Validation is GREEN only if it proves:

1. authenticated request persists one request and zero assignment events;
2. unauthenticated request/accept/reject are rejected;
3. valid authorized acceptance atomically creates one target assignment and one accepted decision;
4. disabled/non-assignable specialist is rejected with zero target assignment;
5. target not `ready` is rejected with zero assignment;
6. missing handoff approval blocks acceptance;
7. authority escalation is blocked;
8. task-class drift/non-`general` scope is blocked;
9. source ownership conflict is contained;
10. expiry/rejection preserve source ownership;
11. replayed acceptance creates no duplicate assignment;
12. simulated lifecycle-write failure rolls back accepted state;
13. execution approval remains unchanged;
14. provider/execution calls remain none.

## Production boundary

A6.5 authorizes contract and isolated validation only. It does not authorize the production table, routes, Control API image change, worker eligibility, handoff approval, assignment, or execution.
