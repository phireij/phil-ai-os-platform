# Phil AI OS Platform — Phase 2.1O Canonical Workload Lifecycle & Terminal-State Evidence Gate

Date: 2026-08-28
Status: OPEN / GATED

## Purpose
Phase 2.1O establishes trustworthy durable workload lifecycle evidence so Mission Control can distinguish active work from terminal/closed work without inferring readiness from missing state.

Phase 2.1N intentionally closed with `worker_readiness=indeterminate` and `reason_code=workload_evidence_incomplete`. The next safe increment is therefore to define and validate canonical workload/terminal-state evidence before any retry, reroute, autonomous assignment, or multi-agent behavior.

## Core Invariants

- production execution allowlist remains exactly `general`
- Hermes remains the only enabled/assignable worker
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
- monitoring, backup, backup self-heal, notification dispatch, and heartbeat remain independent and active

## Required Outcome
The platform must be able to determine, from durable authoritative evidence, whether a task assigned to Hermes is:

- active/incomplete;
- terminal-success;
- terminal-failure;
- terminal-blocked/denied/expired/rejected/cancelled;
- ambiguous/unsafe-to-retry;
- audited/closed;
- or unknown because evidence is incomplete.

This phase does not authorize automatic recovery or retry.

## Candidate Canonical Lifecycle

The Phase 2.1 gap matrix proposed:

`RECEIVED -> CLASSIFIED -> ASSIGNED -> PLANNED -> POLICY_CHECK -> [APPROVAL_PENDING] -> AUTHORIZED -> EXECUTING -> {SUCCEEDED | FAILED | BLOCKED | CANCELLED} -> AUDITED -> CLOSED`

Additional exception states:

- `DENIED`
- `EXPIRED`
- `REJECTED`
- `AMBIGUOUS`
- `CONTAINED`

Phase 2.1O must reconcile this proposal against the exact production schema and routes before any activation.

## Gate Sequence

### O1 — Read-Only Lifecycle Discovery
Inspect exact production lifecycle tables, columns, write routes, execution-audit correlations, existing stages, and historical task examples. Determine which states are authoritative today and which are only proposed. No production mutation.

### O2 — Isolated Canonical Lifecycle Contract
Define legal state classes and precedence off-production. Explicitly define `active`, `terminal`, `ambiguous`, `audited/closed`, and `unknown` semantics. Validate that missing/conflicting evidence fails closed.

### O3 — Production Preflight
Prove the smallest additive path, rollback boundary, compatibility with existing approvals/execution audits, and whether schema or read-model-only changes are sufficient.

### O4 — Bounded Durable Lifecycle Evidence Activation
Only if required by O3. Add the minimum durable evidence needed to classify workload. No retry, reroute, assignment automation, approval bypass, or provider call.

### O5 — Read Model / Readiness Integration
Expose authoritative workload evidence to Mission Control and update readiness only when the durable lifecycle evidence is complete.

### O6 — Controlled Verification
Verify active and terminal classification using safe evidence or a tightly bounded governed canary only if necessary and separately authorized by the existing approval boundary.

### O7 — Closure
Revalidate all governance invariants and formally close Phase 2.1O only if workload evidence is authoritative and fail-closed.

## Explicitly Out of Scope

- autonomous retry or recovery
- automatic task reassignment
- multi-agent handoff/delegation
- specialist-agent execution
- new task classes
- provider/model migration
- L4 autonomy
- Mission Control mutation controls
- arbitrary shell/network authority

## Closure Standard
Phase 2.1O closes GREEN only when Mission Control can prove whether Hermes has active vs terminal work from durable authoritative lifecycle evidence, while proving that the lifecycle model itself grants no authority and triggers no automatic action.
