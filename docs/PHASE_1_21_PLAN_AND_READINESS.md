# Phase 1.21 — Governed Expansion Planning & Readiness

Status: **STARTED — PLANNING / READINESS ONLY**
Date: 2026-08-25

## Objective

Define the next safe expansion beyond the Phase 1.20 narrow production boundary without weakening human approval, Control API routing, replay protection, auditability, monitoring, backup protection, or the execution kill switch.

## Phase 1.20 inherited baseline

- Narrow expansion active.
- Production execution scope: `general` only.
- Human approval mandatory.
- Control API execution boundary mandatory.
- Direct provider bypass prohibited.
- Unrestricted autonomous execution disabled.
- Kill switch available.
- Live-test gate disabled.
- Durable approval consumption / replay protection validated.
- Monitoring, scheduled backup, and backup self-heal active.

## Phase 1.21 proposed workstream

1. Current-state readiness discovery.
2. Candidate task-class expansion inventory.
3. Risk classification and deny-by-default policy contract.
4. Approval requirements per candidate task class.
5. Cost/token/output ceilings and provider-routing constraints.
6. Negative-path and rollback contract.
7. Canary scope definition.
8. Human-approved activation gate.
9. Post-activation verification and checkpoint.

## Initial safety rule

Phase 1.21 planning does **not** authorize any new production task class or autonomous execution. Any expansion requires explicit contract validation, canary testing, rollback readiness, and a fresh human approval.

## Recommended first candidate

Evaluate `routine` as the first possible additional task class, but do not activate it until readiness evidence shows that its classification boundary, approval policy, cost ceiling, audit behavior, and rollback path are deterministic and safe.

## Readiness gate

Before activation work begins, verify:

- Phase 1.20 marker remains active and unchanged.
- Control API is healthy.
- Monitoring and backup protections are active.
- Current allowed task classes remain exactly `general`.
- Kill switch remains available.
- No direct-provider bypass exists.
- No unrestricted autonomous execution is enabled.
- Candidate expansion remains deny-by-default until approved.

## Next action

Create and run **Phase 1.21 Current-State Readiness Discovery**.

`PHIL_AI_OS_PHASE_1_21_PLANNING_STARTED`
