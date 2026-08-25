# Phase 1.18 — Execution Policy Boundary & Agent Path Enforcement

**Status:** STARTING

## Objective

Prove that every supported agent execution path is forced through the Phil AI OS control plane and cannot silently bypass approval, routing, budget, kill-switch, audit, or usage-accounting policy.

## Why this phase now

Phase 1.17 completed backup/recovery operations. The major remaining Phase 1 risk is policy bypass: normal Hermes or future agent traffic must never reach providers through an uncontrolled path. Phase 1.18 closes that boundary before Mission Control becomes the operating center in Phase 2.

## Scope

1. Inventory all Hermes/provider execution paths and credentials in use.
2. Identify any direct provider-call path that does not traverse the Control API.
3. Establish a machine-readable execution-policy boundary report.
4. Enforce default-deny behavior for unsupported/unregistered execution paths.
5. Preserve the maximum-safe runtime posture while testing.
6. Validate that approval-gated execution still succeeds through the sanctioned path.
7. Validate that bypass/replay/task-mismatch/kill-switch cases remain blocked with zero unintended provider usage.
8. Surface boundary health through the existing operational monitor / Mission Control snapshot where practical.
9. Produce end-to-end audit evidence tying sanctioned execution to approval, route, provider/model, outcome, and usage.

## Non-goals

- No wider autonomous execution authority.
- No removal of human approval requirements.
- No automatic Mission Control delegation yet.
- No provider credentials will be exposed in GitHub logs or committed to the repository.

## Closure gates

Phase 1.18 is complete only when:

- all known agent/provider execution paths are inventoried;
- sanctioned paths are explicitly identified;
- no uncontrolled provider path is accepted as production-valid;
- bypass probes are rejected safely;
- sanctioned approval-gated execution remains functional;
- provider usage accounting remains exactly-once;
- production safety monitor, backups, and Control API remain healthy;
- evidence is documented and merged to `main`.

## Phase 2 readiness contribution

Closing Phase 1.18 is a prerequisite for moving the CTO Office and agents into Mission Control, because Mission Control must become the authoritative coordination surface rather than one of several possible execution paths.
