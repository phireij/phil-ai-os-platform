# Phil AI OS Platform — Phase 2.1N Worker Availability & Assignment Readiness Gate

Date: 2026-08-27
Status: OPEN / GATED

## Purpose
Phase 2.1N establishes a trustworthy, read-only **worker availability and assignment-readiness model** for the existing Hermes worker.

Phase 2.1M proved authenticated runtime presence and durable workload visibility. Phase 2.1N may correlate those signals with the existing agent registry so the coordinator and Mission Control can distinguish:

- registered
- assignable by policy
- runtime present
- workload busy/idle/unknown
- ready/not-ready for an **explicit future assignment operation**

The phase does **not** authorize automatic assignment or execution.

## Core Invariant
`availability != authority`

A worker being available or assignment-ready must never grant execution authority, approval authority, or permission to widen task classes.

## Required Governance Baseline
The following must remain true throughout Phase 2.1N:

- production execution allowlist remains exactly `general`
- Hermes remains the only registered and assignable worker
- Hermes authority ceiling remains L3
- Mission Control remains read-only
- human approval safeguards remain unchanged
- no self-approval
- no automatic assignment
- no automatic retry
- no automatic reroute
- no automatic delegation
- no automatic execution
- no provider/model/credential expansion
- no new agent registration
- no task-class expansion
- monitoring, backups, backup self-heal, approval notification dispatch, and runtime heartbeat remain active

## Availability Model
The canonical readiness projection should be derived only from authoritative existing signals:

1. **Registry policy** — `agent_registry`
2. **Authenticated logical presence** — Phase 2.1M heartbeat evidence
3. **Runtime/container observation** — informational only, separate from logical presence
4. **Durable workload state** — latest canonical task lifecycle state assigned to Hermes, if any
5. **Governance boundary** — current execution allowlist and Hermes authority ceiling

A proposed readiness state may be one of:

- `ready`
- `busy`
- `offline_or_stale`
- `disabled_or_unassignable`
- `indeterminate`

The exact state transition rules must be validated before activation.

## Explicitly Out of Scope
Phase 2.1N must not:

- assign a real task to Hermes automatically
- consume an approval
- call `/v1/execute`
- make a provider call
- create a second agent
- expand Hermes beyond L3
- widen the execution allowlist beyond `general`
- add Mission Control mutation controls
- introduce autonomous retries, reroutes, delegation, or failover

## Gate Sequence

### N1 — Read-Only Availability Discovery
Inspect production and verify:
- registry fields and exact Hermes policy state
- Phase 2.1M heartbeat evidence shape and freshness semantics
- durable workload/lifecycle fields usable for busy/idle classification
- existing assignment/planning routes and whether they are already explicit authenticated operations
- current read-model and dashboard integration points
- all governance baseline invariants

No production mutation.

### N2 — Isolated Readiness Contract Validation
Only if N1 identifies ambiguity or missing deterministic classification logic.

Validate readiness classification off-production or against read-only captured metadata.

### N3 — Production Preflight
Prove the exact additive implementation path and rollback boundary.

### N4 — Bounded Availability Projection Activation
Add only the readiness projection. No assignment mutation.

### N5 — Mission Control Read-Only Presentation
Expose readiness clearly, including the statement that readiness grants no authority.

### N6 — Dynamic-State Verification
Verify readiness changes correctly across at least safe observable states without causing a real governed execution.

### N7 — Closure
Revalidate governance invariants and formally close Phase 2.1N only if all gates are GREEN.

## Closure Standard
Phase 2.1N can close GREEN only when the platform can accurately answer whether Hermes is available for an explicit governed assignment while proving that this knowledge itself causes no assignment, approval, execution, provider, authority, or task-class mutation.
