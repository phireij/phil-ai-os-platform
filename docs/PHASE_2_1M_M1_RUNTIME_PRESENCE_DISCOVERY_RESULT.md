# Phase 2.1M M1 — Runtime Presence Discovery Result

Status: **GREEN / M2 REQUIRED**

Date: 2026-08-27

## Run

- Workflow: `Phase 2.1M M1 Runtime Presence Discovery`
- Run: `33073012776`
- Job: `98519851170`
- Result: success

## Production safety baseline

- Control API health: OK
- readiness: OK
- monitor: active
- backup timer: active
- backup self-heal: active
- approval notification dispatcher timer: active
- production execution allowlist: exactly `general`
- SQLite quick check: OK
- production mutation: none
- approval creation/decision/consumption: none
- notification send: none
- execution/provider call: none

## Agent identity evidence

`agent_registry` exists with columns:

`agent_id, display_name, role, authority_ceiling, enabled, assignable, created_at, source_component`

Exactly one row exists:

- agent_id: `hermes`
- display_name: Hermes
- role: `operational_worker`
- authority_ceiling: `L3`
- enabled: true
- assignable: true

No heartbeat, `last_seen`, presence, or runtime-freshness field exists in the canonical registry.

## Runtime evidence

Hermes container was observed:

- status: running
- running: true
- restart count: 0
- container healthcheck: none configured
- runtime stats obtainable from Docker

This is **container/runtime liveness evidence only**. It is not a canonical logical agent heartbeat and must not be presented as proof that Hermes is logically present/ready to accept work.

## Durable workload evidence

Canonical task/lifecycle primitives exist:

- `task_plans`
- `task_lifecycle_events`
- `approval_requests`
- `execution_audit`

`task_lifecycle_events` includes `assigned_agent_id`, allowing workload correlation to a registered agent without introducing a new authority source.

## Discovery decision

M1 is GREEN as a read-only discovery gate.

A real gap remains: no canonical heartbeat/freshness primitive exists. Therefore **M2 is REQUIRED**.

M2 must define deterministic semantics that keep these signals separate:

1. **registry status** — enabled/assignable/authority identity;
2. **runtime liveness** — container/process evidence;
3. **logical presence** — explicit heartbeat freshness only;
4. **workload** — derived from durable task/lifecycle state.

Until a heartbeat exists, logical presence must be `unknown`, never inferred as `online` merely because the container is running.

No authority change is authorized by this result.

`PHIL_AI_OS_PHASE_2_1M_M1_DISCOVERY_GREEN_M2_REQUIRED`
