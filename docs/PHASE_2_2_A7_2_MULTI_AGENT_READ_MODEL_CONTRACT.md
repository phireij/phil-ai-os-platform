# Phil AI OS Platform — Phase 2.2 A7.2 Multi-Agent Read Model Contract

**Phase:** 2.2 A7.2  
**Status:** CONTRACT / ISOLATED VALIDATION  
**Schema:** `2.2-a7.v1`  
**Date:** 2026-08-28

## Authority model

Mission Control is a read-only projection. It does not own registry, presence, lifecycle, handoff, approval, execution, or provider state and must not create authority by projection.

Authoritative inputs remain:

- `agent_registry` for identity, role, authority ceiling and eligibility;
- dedicated agent presence evidence for liveness/attribution;
- `task_lifecycle_events` for durable workload ownership and terminality;
- `task_handoffs` for durable handoff request/decision/correlation history;
- approval/execution evidence only for reporting decision state, never for granting through Mission Control.

## Top-level projection

```json
{
  "schema": "2.2-a7.v1",
  "generated_at": "<iso8601>",
  "evidence_complete": true,
  "agents": [],
  "handoffs": [],
  "governance": {
    "mission_control_authority": "read_only_observer",
    "automatic_assignment": false,
    "automatic_retry": false,
    "automatic_reroute": false,
    "automatic_delegation": false,
    "automatic_execution": false
  }
}
```

## Agent projection

Each registered worker is projected independently:

```json
{
  "agent_id": "specialist-worker-01",
  "display_name": "Specialist Worker 01",
  "role": "specialist_worker",
  "authority_ceiling": "L1",
  "registry": {
    "enabled": false,
    "assignable": false,
    "evidence_complete": true
  },
  "presence": {
    "state": "fresh|stale|offline|unknown",
    "observed_at": "<iso8601|null>",
    "age_seconds": 0,
    "source_component": "<string|null>",
    "identity_verified": true,
    "evidence_complete": true
  },
  "workload": {
    "active_task_count": 0,
    "active_tasks": [],
    "latest_owned_stage": "COMPLETED|null",
    "evidence_complete": true
  },
  "readiness": {
    "state": "unassignable|busy|ready|stale|offline|indeterminate",
    "reason": "<stable reason code>",
    "grants_authority": false
  },
  "evidence_complete": true
}
```

### Registry precedence

Registry eligibility is authoritative for whether a worker can be considered assignable:

- `enabled=false` OR `assignable=false` => readiness `unassignable` regardless of fresh presence;
- authority ceiling is informational maximum only, never a grant;
- unknown/missing registry row is not projected as a usable worker.

### Presence semantics

Presence is identity-specific.

- Hermes uses its authenticated Control API round-trip evidence.
- `specialist-worker-01` uses its dedicated Ed25519-signed evidence.
- Freshness thresholds remain those established in Phase 2.2 A6.2: <=120 seconds fresh, 121–300 stale, >300 offline.
- Signature/identity verification failure => `unknown`, `identity_verified=false`, `evidence_complete=false`.
- Presence freshness never overrides disabled/non-assignable registry state.

### Workload semantics

Ownership is reconstructed from durable lifecycle evidence, preserving assignment across later rows where `assigned_agent_id` may be null.

A task is active only if its latest legal lifecycle state is non-terminal. Terminal stages include at minimum `COMPLETED`, `FAILED`, `CANCELLED`, `DENIED`, and `EXPIRED`.

Historical assignment remains auditable but does not count as active workload once the task is terminal.

Conflicting or impossible ownership evidence => workload `evidence_complete=false` and readiness `indeterminate` for an otherwise eligible worker.

## Handoff projection

Each durable handoff row is projected as historical/active evidence:

```json
{
  "handoff_id": "hof_...",
  "task_id": "tsk_...",
  "source_agent_id": "hermes",
  "target_agent_id": "specialist-worker-01",
  "task_class": "general",
  "required_authority": "L1",
  "source_authority_ceiling": "L3",
  "target_authority_ceiling": "L1",
  "reason_code": "phase_2_2_a6_8_controlled_canary",
  "correlation_id": "hofcorr_...",
  "state": "accepted",
  "handoff_approval_required": true,
  "handoff_approval_state": "approved",
  "execution_approval_state": "not_consumed|<stored state>",
  "requested_at": "<iso8601>",
  "decided_at": "<iso8601|null>",
  "lifecycle_event_id": "evt_...|null",
  "task_latest_stage": "COMPLETED",
  "active_ownership": false,
  "evidence_complete": true
}
```

A completed accepted handoff remains visible with `active_ownership=false`.

Handoff evidence is incomplete when canonical task identity, source/target identity, correlation, required authority, decision state, or lifecycle linkage cannot be reconciled.

## Evidence-completeness rules

Top-level `evidence_complete` is true only when:

- every projected registered worker has complete registry evidence;
- presence evidence failures are explicitly represented rather than silently omitted;
- workload reconstruction has no unresolved ownership conflict;
- every projected handoff has a canonical task/correlation and reconcilable source/target identities;
- no secret/credential material is included.

Incomplete evidence must not cause automatic reassignment or reroute.

## A6.8 expected projection

The durable completed canary must project:

- Hermes: L3 enabled/assignable;
- specialist: L1 disabled/non-assignable;
- specialist readiness: `unassignable` even when signed presence is fresh;
- specialist active workload: `0`;
- one accepted Hermes -> specialist handoff row;
- one historical specialist assignment for the canary;
- canary latest stage `COMPLETED`;
- handoff `active_ownership=false`;
- replay does not create a second assignment/handoff;
- no execution approval consumption represented as execution authority.

## Secret exclusion

The projection MUST NOT contain:

- bearer tokens;
- provider/API keys;
- private keys;
- raw authorization headers;
- Docker socket access details;
- secret file contents;
- reusable approval credentials.

## Mutation boundary

A7 adds no Mission Control mutation surface. POST, PUT, PATCH and DELETE against the read-model endpoint remain HTTP `405`.
