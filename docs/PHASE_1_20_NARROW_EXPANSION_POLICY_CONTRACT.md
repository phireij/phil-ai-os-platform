# Phase 1.20 — Narrow Expansion Policy Contract

**Status:** PROPOSED / VALIDATION REQUIRED  
**Program:** Phil AI OS Platform  
**Date:** 2026-08-25

## Purpose

Define the first safe expansion beyond the single-request canary while preserving the human-controlled execution boundary proven in Phase 1.19–1.20.

## Expansion Principle

Expansion MUST be narrow, reversible, observable, approval-gated, and deny-by-default. This contract does not authorize unrestricted autonomous execution.

## Allowed Initial Scope

The first expansion candidate is limited to controlled Hermes-originated `general` tasks that:

1. are explicitly submitted through the Phil AI OS Mission Control execution path;
2. have a matching durable approval request;
3. are approved by a human before execution;
4. are unexpired and unconsumed at execution time;
5. match the approved task text and routing classification;
6. satisfy the existing execution allowlist and request-size/output limits;
7. execute through the Control API routing boundary only.

Direct provider bypass is prohibited.

## Mandatory Controls

The following controls MUST remain active:

- human approval for gated execution;
- one-time approval consumption and replay rejection;
- durable approval and execution audit linkage;
- execution kill switch;
- provider/model routing through Control API;
- bounded request and output limits;
- operational health checks;
- automated backup and backup self-heal;
- primary/fallback provider auditability;
- deny-by-default behavior for requests outside the approved scope.

## Explicitly Out of Scope

This contract does NOT authorize:

- unrestricted autonomous agent execution;
- arbitrary shell/host execution;
- arbitrary filesystem mutation;
- arbitrary network/API access outside approved routed providers;
- self-approval by Hermes or another agent;
- approval reuse or replay;
- automatic expansion to additional task classes;
- bypass of Mission Control / Control API;
- disabling monitoring, backup, audit, or kill-switch controls.

## Failure Policy

Any mismatch, expired approval, consumed approval, missing approval, unhealthy control plane, kill-switch activation, non-allowlisted task, audit failure, or policy ambiguity MUST fail closed before provider execution whenever applicable.

## Rollback Policy

Any narrow expansion must have a verified rollback path to the current restricted single-request canary scope. Rollback must not depend on a provider call.

## Validation Gates Required Before Activation

1. Contract/readiness validation — read-only.
2. Negative-path validation for missing, denied, expired, mismatched, and consumed approvals.
3. Replay rejection validation.
4. Kill-switch validation.
5. Durable audit linkage validation.
6. Primary/fallback routing compatibility validation.
7. Rollback readiness validation.
8. One narrowly scoped human-approved activation canary.
9. Post-activation verification before any further expansion.

## Activation Rule

No production scope expansion is authorized by this document alone. Production activation requires a separate explicit Phase 1.20 activation gate after all required validations pass.

## Decision

`NARROW_EXPANSION_POLICY_CONTRACT_DEFINED`

Next action: `VALIDATE_NARROW_EXPANSION_POLICY_CONTRACT`
