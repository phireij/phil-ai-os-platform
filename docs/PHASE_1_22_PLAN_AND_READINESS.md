# Phase 1.22 — Governed Routine Production Readiness

Status: **STARTED — PLANNING / READINESS ONLY**  
Date: 2026-08-26

## Objective

Determine whether the successfully canary-validated `routine` task class is ready for a narrowly governed production operating mode, without converting Phase 1.21's one-request validation into unrestricted or persistent autonomous execution.

## Inherited baseline from Phase 1.21

- Phase 1.21 checkpoint closed successfully.
- Production execution allowlist restored to `general` only.
- `routine` canary completed and inactive.
- Human approval remains mandatory.
- Durable approval consumption and replay protection are validated.
- Control API routing remains mandatory.
- Budget enforcement remains active.
- Execution kill switch remains available.
- Direct-provider bypass remains prohibited.
- Unrestricted autonomous execution remains disabled.
- Monitoring, scheduled backup, and backup self-heal remain active.

## Phase 1.22 workstream

1. Current-state readiness discovery after Phase 1.21 restoration.
2. Define the exact production operating model for `routine` tasks.
3. Decide whether approval is required per request, per bounded batch, or another explicitly constrained unit.
4. Define routine-task ceilings for token output, cost, request size, frequency, and concurrency.
5. Define provider/model routing constraints and fallback behavior.
6. Define replay, duplicate-request, timeout, and partial-failure behavior.
7. Define audit requirements and Mission Control visibility.
8. Define Telegram approval / escalation behavior for routine production requests.
9. Define rollback and kill-switch procedures.
10. Run negative-path validation before any persistent routine enablement.
11. Require a fresh human approval before any production policy expansion.
12. If approved, activate only a narrow bounded routine mode and verify it before checkpoint closure.

## Initial safety rule

Phase 1.22 planning and discovery do **not** authorize `routine` as a persistent production task class.

Until a fresh activation approval is granted, production execution must remain:

`PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=general`

The following remain prohibited:

- direct provider bypass;
- unrestricted autonomous execution;
- silent expansion of allowed task classes;
- approval reuse or replay;
- unbounded token/cost/concurrency settings.

## Recommended operating direction

Prefer **approval-bound routine execution** over permanent autonomous routine access. The initial production model should preserve a human-approved execution unit with explicit ceilings and durable audit, then expand further only after operational evidence supports it.

## Readiness gate

Before any activation work:

- verify Phase 1.21 closure marker and restored `general`-only state;
- verify Control API health;
- verify monitor, backup timer, and backup self-heal;
- verify kill switch state and operability;
- verify no direct provider bypass;
- verify no unrestricted autonomous execution;
- inspect current routine classification and route behavior;
- verify approval and audit schema can support the proposed bounded operating model.

## First action

Create and run **Phase 1.22 Current-State Readiness Discovery**.

`PHIL_AI_OS_PHASE_1_22_PLANNING_STARTED`
