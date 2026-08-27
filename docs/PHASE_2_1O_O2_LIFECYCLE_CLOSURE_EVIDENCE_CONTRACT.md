# Phase 2.1O — O2 Lifecycle Closure Evidence Contract

Status: **PROPOSED FOR ISOLATED VALIDATION**

## Purpose
Define a conservative, read-only contract for determining whether durable task-lifecycle evidence is complete enough to support worker workload closure and Phase 2.1N readiness classification.

This contract does **not** add or mutate production lifecycle stages. It only defines how existing durable evidence may be interpreted and when the system must fail closed.

## Scope
Applies only to the current governed production scope:
- task class: `general`
- worker: Hermes
- authority ceiling: L3

## Inputs
For each governed task, the classifier may use only durable evidence already present in the Control API state store:
1. task identity
2. ordered `task_lifecycle_events`
3. assignment identity (`assigned_agent_id`)
4. approval state/consumption evidence where relevant
5. durable execution audit/correlation evidence where relevant

Runtime container state, heartbeat freshness, elapsed wall-clock time, or absence of recent provider calls must **not** be used to manufacture lifecycle closure.

## Closure model
A task is not considered durably closed merely because its latest lifecycle event is old.

### Explicitly open evidence
The following observed stages are non-terminal for worker workload purposes:
- `RECEIVED`
- `CLASSIFIED`
- `APPROVAL_PENDING`
- `ASSIGNED`
- `PLANNED`

`ASSIGNED` and `PLANNED` are especially important: without later durable closure evidence, they remain historically unclosed and cannot prove zero active workload.

### `AUDITED`
`AUDITED` must not automatically be treated as worker-workload terminal unless its correlation proves that the governed execution associated with the task reached an execution outcome that is durably recorded and uniquely linked to that task.

If the correlation is missing, ambiguous, contradictory, or refers only to a non-execution audit event, closure evidence is incomplete.

## Classification outputs
For each task, the isolated classifier returns one of:
- `open_proven` — durable evidence proves the task remains open for worker workload accounting.
- `closed_proven` — durable correlated evidence proves worker work for the task has completed or otherwise ceased under an already-established governed outcome.
- `closure_indeterminate` — evidence is insufficient or contradictory.

## Worker workload evidence
Worker-level workload evidence is **complete** only if every task relevant to Hermes assignment/workload is classified `open_proven` or `closed_proven` with no `closure_indeterminate` records.

Then:
- `active_task_count` = count of `open_proven` tasks assigned to Hermes.
- `active_states` = durable latest lifecycle stages of those open tasks.
- `evidence_complete` = `true` only when there are zero indeterminate task records.

If any relevant task is indeterminate:
- `evidence_complete = false`
- worker readiness must remain `indeterminate`
- the classifier must not infer `ready` or `busy` from partial evidence.

## Correlation requirements for `closed_proven`
A task may be `closed_proven` only when all required durable identifiers resolve uniquely and consistently. At minimum:
1. task identity is unambiguous;
2. assignment, approval, execution, and audit identifiers—where present—do not conflict;
3. the evidence proves an established governed outcome rather than simply an attempted transition;
4. no later durable lifecycle evidence reopens or contradicts the closure.

The isolated validator must reject duplicate, orphaned, cross-task, or replayed correlations as `closure_indeterminate`.

## Fail-closed rules
The classifier must return `closure_indeterminate` when any of the following occurs:
- unknown lifecycle stage;
- missing required correlation;
- duplicate or conflicting execution/audit correlation;
- task assigned to an unknown or incompatible agent;
- lifecycle ordering contradiction;
- malformed durable record;
- evidence source unavailable;
- a proposed conclusion depends on elapsed time rather than durable state.

## Non-authority guarantees
This contract has no authority effect. Classification must never trigger:
- automatic assignment;
- approval or denial;
- approval consumption;
- retry;
- reroute;
- delegation;
- execution;
- provider/model selection changes;
- task-class expansion;
- agent registration changes;
- authority expansion;
- Mission Control mutation.

## Production mutation boundary
O2 validation is isolated/offline only. It must not write to the production database, change Control API code, add lifecycle stages, restart production services, or alter Mission Control.

## O2 exit criteria
O2 may be marked GREEN when isolated tests demonstrate:
1. historical `ASSIGNED`/`PLANNED` without closure => not closed;
2. explicit, uniquely correlated governed outcome => `closed_proven`;
3. ambiguous/missing/cross-task/replayed correlation => `closure_indeterminate`;
4. worker evidence complete only when all relevant tasks resolve;
5. zero-active workload is never inferred from absence of evidence;
6. all non-authority guarantees remain true.

Only after O2 GREEN may Phase 2.1O proceed to a production **read-only preflight**. Any proposal to add new lifecycle terminal stages or production mutation requires a separate explicit gate and authorization.
