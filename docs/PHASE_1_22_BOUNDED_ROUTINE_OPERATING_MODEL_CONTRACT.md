# Phase 1.22 — Bounded Routine Operating Model Contract

Status: **DEFINED — POLICY CONTRACT ONLY / NOT ACTIVATED**  
Date: 2026-08-26

## Purpose

Define the initial production operating contract for the `routine` task class after the successful Phase 1.21 one-request canary, while preserving the restored `general`-only production boundary until a separate activation gate is explicitly approved.

## Verified readiness baseline

Phase 1.22 Current-State Readiness Discovery completed successfully on GitHub Actions run `32909002849`.

Verified state:

- Control API healthy.
- Phase 1.21 closed/restored state verified.
- Production allowlist remains exactly `general`.
- Persistent `routine` enablement remains disabled.
- Execution kill switch is not engaged and remains available.
- Routed execution remains enabled.
- Live-test gate remains disabled.
- Maximum output tokens currently `32`.
- Maximum request size currently `256` characters.
- Scheduled backup and backup self-heal are active.
- Direct provider bypass remains prohibited.
- Autonomous expansion remains disabled.
- Discovery made no provider call and no production change.

Operational note: the discovery did not find an active `phil-ai-os-monitor.timer`; monitoring service/timer naming and coverage must be reconciled before persistent routine activation.

## Initial bounded routine production model

The first production-capable `routine` mode SHALL remain **human-approval-bound per execution request**.

No standing approval, reusable approval, open-ended batch approval, or autonomous routine permission is authorized by this contract.

Each routine execution must satisfy all of the following:

1. A durable approval exists for the exact execution unit.
2. Approval state is approved, unexpired, and unconsumed.
3. Approval task class is `routine`.
4. Control API classifies the request as `routine`.
5. `routine` is explicitly present in the active execution allowlist at execution time.
6. The execution kill switch is not engaged.
7. The request remains within configured request/output ceilings.
8. Budget enforcement permits the call.
9. Execution routes only through the Control API/provider-routing boundary.
10. Approval is consumed once and replay is rejected.
11. Execution and approval linkage are durably auditable.

## Initial ceilings

Until changed by a separately reviewed policy update, the initial bounded routine mode SHALL use conservative limits no wider than the currently validated execution boundary:

- Maximum request size: `256` characters.
- Maximum output tokens: `32`.
- Concurrency: `1` routine execution at a time.
- Approval unit: exactly `1` execution request.
- Approval reuse: prohibited.
- Automatic retry after provider-side execution ambiguity: prohibited unless idempotency is proven.
- Direct provider invocation: prohibited.
- Autonomous task-class expansion: prohibited.

Cost remains subject to the existing Control API budget gate. A dedicated routine per-request cost ceiling must be verified/defined before activation if the current budget implementation does not already enforce a deterministic request-level ceiling.

## Failure behavior

Routine execution must fail closed for:

- missing, expired, mismatched, rejected, or consumed approval;
- classification mismatch;
- `routine` absent from allowlist;
- kill switch engaged;
- request/output ceiling violation;
- budget denial;
- unsupported route/provider state;
- duplicate/replay attempt;
- unresolved execution ambiguity where safe retry cannot be proven.

No failure condition may fall back to direct provider bypass.

## Audit and operator visibility

Before persistent routine activation, the platform must confirm that the existing durable approval/execution records expose enough information to correlate:

- approval ID;
- task class;
- approval state and consumption time;
- execution outcome;
- route/provider/model where applicable;
- budget/cost evidence where available;
- rejection/failure reason.

Mission Control should surface this bounded routine state and its approval/execution evidence before routine volume is expanded beyond the initial production validation scope.

## Monitoring prerequisite

Phase 1.22 readiness discovery reported `monitor_timer=not_found_or_inactive` while backup protections were active. Before activation, perform a monitoring-boundary discovery to determine whether monitoring is provided under a different service/timer name or whether a required monitor needs restoration.

This is a prerequisite investigation, not authorization to change monitoring blindly.

## Activation boundary

This contract does **not** activate `routine` in production.

Production remains:

`PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=general`

A fresh human approval is required before any bounded production activation of `routine`.

## Next action

Run **Phase 1.22 Monitoring & Enforcement Readiness Discovery** to reconcile monitoring coverage and verify deterministic per-request budget/cost, concurrency, approval, audit, and negative-path enforcement surfaces before proposing activation.

`PHIL_AI_OS_PHASE_1_22_BOUNDED_ROUTINE_OPERATING_MODEL_CONTRACT_DEFINED`
