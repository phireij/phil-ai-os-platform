# Phase 2.1N — N2 Worker Readiness Classification Contract

Status: **PROPOSED FOR ISOLATED VALIDATION**
Date: 2026-08-27

## Purpose

Define a conservative, read-only worker-readiness classification for an explicitly governed `general` task. This classification is advisory operator/coordinator information only. It does not assign, approve, retry, reroute, consume an approval, execute, or call a provider.

## Authoritative inputs

1. **Registry eligibility**
   - `agent_id`
   - `enabled`
   - `assignable`
   - `authority_ceiling`
2. **Logical presence**
   - authenticated heartbeat freshness derived from Phase 2.1M evidence
3. **Durable workload evidence**
   - latest durable task lifecycle state attributable to the worker
   - explicit evidence that zero active governed tasks exist, when available
4. **Policy scope**
   - production execution task-class allowlist must remain exactly `general`

Container-running state alone is not sufficient evidence of readiness.

## Output states and precedence

Classification is evaluated in this order:

1. `unassignable`
   - registry record absent, or
   - `enabled != true`, or
   - `assignable != true`, or
   - authority ceiling is incompatible with the current governed worker policy.

2. `stale`
   - registry is eligible, but authenticated logical presence is `stale` or `offline`.

3. `indeterminate`
   - registry is eligible but presence is missing/unknown/conflicting, or
   - presence is fresh but durable workload evidence is missing, unknown, or conflicting, or
   - policy scope cannot be verified as exactly `general`.

4. `busy`
   - registry is eligible,
   - authenticated logical presence is fresh, and
   - durable lifecycle evidence proves at least one active governed task assigned to the worker.

5. `ready`
   - registry is eligible,
   - authenticated logical presence is fresh,
   - production task-class scope is exactly `general`, and
   - durable evidence explicitly proves zero active governed tasks for the worker.

## Active lifecycle semantics

For N2 validation, active task states are limited to non-terminal governed lifecycle stages such as `ASSIGNED`, `RUNNING`, `APPROVAL_PENDING`, or equivalent canonical active states discovered in the durable lifecycle model. Terminal states must not count as active.

The production implementation must use the actual canonical lifecycle vocabulary discovered in preflight; N2 does not authorize inventing or rewriting lifecycle records.

## Safety invariants

- Readiness has **no authority effect**.
- `ready` means only “eligible by observed signals for consideration for an explicit governed assignment.”
- `ready` must never trigger assignment automatically.
- `busy`, `stale`, `unassignable`, or `indeterminate` must never trigger retry/reroute/delegation automatically.
- No new agents are authorized.
- Hermes remains the only assignable worker and remains capped at L3.
- Execution allowlist remains `general` only.
- Human approval semantics remain unchanged.
- Mission Control remains read-only.
- No provider/model/credential policy changes are authorized.

## Fail-closed rule

When evidence is incomplete or contradictory, classify `indeterminate`. Never infer `ready` from absence of evidence.
