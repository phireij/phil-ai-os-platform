# Phase 2.1N — N3 Production Preflight Result

Status: **GREEN — WORKLOAD CLOSURE GAP CONFIRMED**
Date: 2026-08-27
Workflow run: `33084104659`
Job: `98558910731`

## Direct production evidence

N3 corrected the N1 direct-DB evidence gap by using stdin-attached container execution and non-empty assertions.

### Registry

Production `agent_registry` contains one worker:
- agent_id: `hermes`
- role: `operational_worker`
- authority_ceiling: `L3`
- enabled: `1`
- assignable: `1`
- source_component: `control-api`

### Canonical lifecycle vocabulary

`task_lifecycle_events` columns:
`event_id, task_id, stage, occurred_at, source_component, actor_id, assigned_agent_id, previous_stage, reason_code, correlation_id`

Observed canonical stages:
- `RECEIVED`
- `CLASSIFIED`
- `APPROVAL_PENDING`
- `ASSIGNED`
- `PLANNED`
- `AUDITED`

No canonical `RUNNING`, `COMPLETED`, `CANCELLED`, `FAILED`, or equivalent worker-workload terminal state was observed.

A historical task has `ASSIGNED` to Hermes followed by `PLANNED` and no later worker-workload terminal event. Therefore the current durable lifecycle cannot safely prove that Hermes has zero active assigned tasks.

### Presence/read model

- authenticated heartbeat age at preflight: 44 seconds
- logical presence: `fresh`
- workload source: `durable_latest_task_lifecycle`
- workload state: `None`
- Mission Control schema: `2.1m.v1`

### Governance

- execution allowlist: exactly `general`
- monitor/backup/self-heal/notification dispatcher/heartbeat/operator services active
- Mission Control mutation methods: blocked
- external operator auth: protected
- no production write occurred
- no assignment/approval/execution/provider call occurred
- no authority expansion occurred

## Decision

N3 is **GREEN**, but it confirms a workload-closure evidence gap.

Per the N2 fail-closed contract, current worker readiness must resolve to `indeterminate`, not `ready` or `busy`, because durable evidence cannot yet distinguish an old unclosed assignment/planning record from genuinely active work.

N4 may expose a read-only readiness projection using this conservative classification. N4 must not invent terminal task states or mutate lifecycle records. A separate future gate is required before adding workload lifecycle closure semantics.
