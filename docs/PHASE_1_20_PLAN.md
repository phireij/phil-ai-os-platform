# Phil AI OS — Phase 1.20 Plan

Date: 2026-08-25
Status: STARTING
Branch: `ops/phase-1.20`

## Objective

Move from the validated Phase 1.19 human-approval canary into a safer, policy-driven controlled-execution baseline without granting broad autonomous authority.

## Scope

1. Define explicit execution policy by task class and risk level.
2. Keep human approval mandatory for sensitive/non-routine execution.
3. Strengthen binding between approval, task, requester, route, provider, and model.
4. Revalidate replay, duplicate-consume, expiry, denial, mismatch, kill-switch, provider-failure, and fallback protections.
5. Preserve durable audit records for every execution attempt.
6. Add concise operator-facing verification output suitable for mobile review.
7. Keep production expansion conservative and allow only validated execution paths.

## Safety Baseline

- no unrestricted autonomous execution;
- kill switch remains available and testable;
- approval remains single-use;
- execution attempts remain auditable;
- fallback routing remains controlled;
- monitoring and backup/self-heal protections remain active;
- production changes occur only through the controlled GitHub Actions → SSH pathway.

## Completion Gate

Phase 1.20 is complete only when one concise regression workflow proves the approved policy path and all critical rejection/failure paths, while confirming Control API health, monitoring, backup/self-heal status, and durable auditability.
