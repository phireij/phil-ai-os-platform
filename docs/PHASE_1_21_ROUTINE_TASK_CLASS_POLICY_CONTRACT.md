# Phase 1.21 — Routine Task-Class Policy Contract

Status: **PROPOSED / VALIDATION REQUIRED**
Date: 2026-08-25

## Purpose

Define the safety contract for evaluating `routine` as the first additional production task class beyond the Phase 1.20 `general`-only boundary.

## Core rule

`routine` remains deny-by-default until all Phase 1.21 validation gates pass and a fresh human-approved activation is consumed. This document alone does not authorize production expansion.

## Candidate scope

A `routine` task may become eligible only when it is deterministic, bounded, reversible or non-destructive, routed through the Control API, durably audited, and covered by explicit approval policy.

## Mandatory inherited controls

- Phase 1.20 `general` execution boundary remains active during validation.
- Human approval remains mandatory for any activation or sensitive execution.
- Control API routing is mandatory.
- Direct provider bypass is prohibited.
- Unrestricted autonomous execution remains disabled.
- One-time approval consumption and replay rejection remain mandatory.
- Durable approval/execution audit linkage remains mandatory.
- Execution kill switch remains available.
- Monitoring, scheduled backup, and backup self-heal remain active.
- Provider/model routing and bounded output limits remain enforced.

## Routine candidate restrictions

Before activation, `routine` must have:

1. deterministic classification evidence;
2. explicit request-size and output ceilings;
3. bounded provider/model routing;
4. deny-by-default handling for ambiguous classifications;
5. negative-path coverage;
6. rollback readiness;
7. durable audit linkage;
8. fresh human authorization for production activation;
9. a single controlled canary before wider use.

## Explicitly prohibited

The `routine` candidate does not authorize arbitrary shell execution, filesystem mutation, unrestricted network access, self-approval, approval replay, direct provider access, security-control modification, backup/monitoring changes, or autonomous widening of task classes.

## Failure behavior

Any missing/denied/expired/consumed approval, classification ambiguity, non-allowlisted task, kill-switch state, unhealthy control plane, audit failure, or policy mismatch must fail closed before provider execution whenever applicable.

## Activation sequence

1. Validate this contract.
2. Validate classification and limits.
3. Validate negative paths and rollback.
4. Prepare a one-request canary.
5. Obtain fresh human approval.
6. Consume approval exactly once.
7. Activate only the narrowly defined `routine` scope.
8. Run post-activation verification.
9. Checkpoint before any wider expansion.

## Decision

`PHIL_AI_OS_PHASE_1_21_ROUTINE_POLICY_CONTRACT_DEFINED`

Next action: `VALIDATE_PHASE_1_21_ROUTINE_POLICY_CONTRACT`
