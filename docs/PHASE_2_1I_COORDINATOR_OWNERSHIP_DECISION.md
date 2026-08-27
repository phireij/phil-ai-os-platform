# Phil AI OS Platform — Phase 2.1I Coordinator Ownership Decision

**Status:** DECISION RECORDED — IMPLEMENTATION NOT YET AUTHORIZED  
**Date:** 2026-08-27

## Discovery evidence

Read-only runtime discovery run `33041692943` completed GREEN with marker:

`PHIL_AI_OS_PHASE_2_1I_COORDINATOR_OWNERSHIP_DISCOVERY_OK`

Observed state:

- lifecycle ledger rows: `0`;
- canonical approval rows: `0`;
- canonical execution-audit rows: `0`;
- Control API coordination-related symbol: `lifecycle_event_insert` only;
- Hermes Mission Control client: present;
- Hermes execution client: present;
- Hermes coordination environment names: none;
- Mission Control writer: none;
- no production/provider/execution/approval mutation occurred.

## Ownership decision

**Control API is the authoritative coordination owner.**

This is a logical control-plane responsibility, not permission for unrestricted task orchestration.

Rationale:

1. Control API already owns canonical `task_id` creation and durable approval/execution correlation.
2. Control API already owns the append-only lifecycle writer surface.
3. Hermes is an execution/gateway worker and currently has no authoritative coordination identity or persistence surface.
4. Mission Control is explicitly read-only and must not become a second authority path.
5. A new independent coordinator service would duplicate authority and persistence boundaries without evidence that a separate service is required yet.

## Role boundaries

### Control API — coordinator authority

May eventually validate and persist explicit coordination metadata for a known canonical task:

- `ASSIGNED` event;
- `PLANNED` event;
- future reassignment/replanning events.

It MUST validate task identity, agent identity, current policy boundary, and event semantics before persistence.

### Hermes — worker / candidate assignee

Hermes may be selected as an assignee only through an explicit coordinator decision. Hermes cannot assign itself, increase its authority, or infer assignment from requester/source fields.

### Mission Control — observer

Mission Control remains read-only. It may display authoritative assignment/planning events but cannot create, edit, approve, or execute them.

## Assignment contract candidate

A future coordinator candidate may accept only bounded coordination data such as:

```text
task_id
agent_id
reason_code
requested_by
```

The coordinator must reject:

- unknown/nonexistent canonical task IDs;
- unknown agent IDs;
- agent identity supplied only through requester/source inference;
- assignments that would imply an authority level above the agent's registered ceiling;
- assignment requests that attempt to change the production task-class allowlist;
- any request that attempts to authorize or execute the task.

A successful assignment appends an `ASSIGNED` lifecycle event. It does not alter approval state.

## Planning contract candidate

A future `PLANNED` event must reference a bounded durable plan representation. The plan representation must avoid exposing sensitive task text, model output, provider responses, or credentials to Mission Control.

A planning event does not imply approval, authorization, or execution readiness.

## Identity requirement

Phase 2.1I cannot safely enable assignment until there is an authoritative **agent registry / agent identity contract**. Current Hermes runtime proves the worker exists, but no durable coordinator-grade agent identity registry was discovered.

Therefore the next implementation gate is:

1. define a minimal agent registry contract;
2. validate it in isolation;
3. validate assignment/reassignment against that registry and the append-only lifecycle ledger;
4. keep production unchanged until those isolated tests are GREEN.

## Authority invariants

Throughout Phase 2.1I:

- production allowlist remains `general` only;
- human approval remains authoritative;
- approval consumption remains one-time;
- assignment does not authorize execution;
- planning does not authorize execution;
- direct provider bypass remains prohibited;
- Mission Control remains read-only.
