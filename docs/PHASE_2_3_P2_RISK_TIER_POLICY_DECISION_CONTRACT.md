# Phil AI OS Platform — Phase 2.3 P2 Risk-Tier & Policy Decision Contract

**Phase:** 2.3 P2  
**Status:** DESIGN / ISOLATED VALIDATION ONLY  
**Date:** 2026-08-28

## Purpose

Define the canonical reusable policy-decision model required before any production approval-policy persistence, autonomous ceiling, task-class expansion, or policy-gated execution activation.

This contract grants no production authority.

## Separation of concepts

The following are independent and MUST NOT be collapsed into one decision:

1. **Task classification** — descriptive task/action category.
2. **Risk classification** — impact/sensitivity tier.
3. **Policy decision** — deny, escalate, require human, or allow preparation.
4. **Human authorization** — explicit operator decision where required.
5. **Execution eligibility** — all preconditions satisfied for the existing execution boundary.
6. **Execution** — actual governed invocation through Control API.

Agent `authority_ceiling` is a maximum capability boundary. It is never a grant of approval, autonomy, assignment, readiness, or execution.

## Canonical risk tiers

| Tier | Meaning | Default policy |
|---|---|---|
| R0 | Observation / read-only / no external side effect | `allow_prepare` only; never implies provider execution |
| R1 | Bounded low-impact reversible action | `require_human` under current production autonomy ceiling |
| R2 | Governed execution or externally consequential bounded action | `require_human` and one-time approval |
| R3 | Sensitive, high-impact, privileged or scope-expanding action | `escalate` to explicit human/governance gate |
| R4 | Prohibited, unbounded, bypass, self-authorizing or insufficiently containable action | `deny` |

Unknown, conflicting or incomplete risk evidence => `deny` or `escalate`; never implicit downgrade.

## Canonical autonomy ceilings

Autonomy is orthogonal to agent authority.

- **A0 — no autonomous side effect:** observation/preparation may be automated, but any side-effect or execution remains human-gated.
- **A1 — bounded reversible side effect:** future candidate only; not authorized in production.
- **A2 — bounded governed execution:** future candidate only; not authorized in production.
- **A3 — broader bounded workflow autonomy:** future candidate only; not authorized in production.

**Current production autonomy ceiling: A0.**

No policy evaluator may raise the effective autonomy ceiling above the configured/governed ceiling. Readiness, authority ceiling, historical approvals or successful canaries do not raise it automatically.

## Canonical policy-decision object

A future policy evaluator MUST produce an immutable decision object containing at least:

- `policy_decision_id`;
- `policy_version`;
- `evaluated_at`;
- `task_id` or bounded action identity;
- `task_class`;
- `action_type`;
- `subject_agent_id`;
- `subject_authority_ceiling`;
- `risk_tier`;
- `required_authority`;
- `configured_autonomy_ceiling`;
- `requested_autonomy_level`;
- `human_approval_required`;
- `approval_id` when applicable;
- `approval_state` when applicable;
- `approval_expires_at` when applicable;
- `approval_consumption_required`;
- `scope_constraints`;
- `evidence_refs`;
- `decision`;
- `reason_codes`;
- `execution_preconditions_satisfied`;
- `authority_effect` = `none`.

Allowed `decision` values:

- `allow_prepare` — may continue read-only/preparatory processing only;
- `require_human` — human authorization required before eligibility can be reconsidered;
- `eligible_for_execution_boundary` — all policy preconditions satisfied, but no execution is performed by policy evaluation;
- `escalate` — explicit governance/operator decision required;
- `deny` — fail closed.

## Required evidence rules

A policy decision must fail closed when any required evidence is missing, stale, ambiguous, conflicting or unverifiable, including:

- canonical task/action identity;
- task classification;
- risk classification;
- agent identity and authority ceiling where an agent is involved;
- configured autonomy ceiling;
- current execution allowlist for provider execution;
- kill-switch state;
- approval identity/state/scope/expiry/consumption state when approval is required;
- scope constraints and action identity for one-time approval;
- execution/audit correlation requirements.

## Human approval rules

- Non-human agents cannot self-approve.
- Requester identity and decision identity must remain distinguishable.
- Human approval is task/action/scope specific.
- Approval expiry is mandatory for execution authorization.
- Approval consumption is one-time where execution is authorized.
- Consumed, denied or expired approval cannot be reused.
- Handoff authorization and execution approval remain separate.
- Approval does not bypass kill switch, task-class allowlist, authority ceiling, request/output limits, provider governance, audit requirements or other policy constraints.

## Execution eligibility rules

`eligible_for_execution_boundary` may be returned only when all required conditions are simultaneously true. Under the current production boundary this includes at minimum:

- task class is `general`;
- required authority does not exceed subject authority ceiling;
- requested autonomy does not exceed configured autonomy ceiling;
- the action does not rely on autonomous side-effect authority beyond A0;
- human approval exists if required and is approved, unexpired, in-scope and unconsumed;
- requester is not self-authorizing;
- kill switch is not blocking execution;
- all required evidence is complete;
- execution remains routed through Control API.

The decision itself performs no provider call and consumes no approval.

## Risk-to-policy defaults under current A0 production boundary

- R0 => `allow_prepare`.
- R1 => `require_human` for any side effect.
- R2 => `require_human`; may become `eligible_for_execution_boundary` only after all explicit approval/precondition checks.
- R3 => `escalate`.
- R4 => `deny`.

## Explicit deny conditions

At minimum:

- unknown task/action class for requested execution;
- class outside current execution allowlist;
- missing or conflicting risk evidence;
- required authority above subject ceiling;
- requested autonomy above configured ceiling;
- self-approval or ambiguous approver identity;
- missing, denied, expired, consumed, mismatched or replayed approval;
- active kill switch for requested execution;
- direct provider bypass;
- Mission Control mutation used as authorization;
- readiness treated as permission;
- authority ceiling treated as permission;
- missing durable audit/correlation requirement;
- unbounded shell/filesystem/network/external-system write without a separately approved contract.

## Persistence boundary

P2 defines the object and semantics only. It does not authorize a new production table or writer.

If later persistence is needed, the preferred shape is an append-only policy-decision ledger keyed by `policy_decision_id`, with immutable request/evidence snapshot hashes and no capability to grant authority independently.

## P2 acceptance criteria

P2 is GREEN when isolated/static validation proves that the contract:

1. keeps risk, authority and autonomy separate;
2. fixes current production autonomy at A0;
3. preserves human approval for side effects/execution under current scope;
4. rejects self-approval, expiry and replay;
5. preserves kill switch and `general`-only execution scope;
6. gives policy evaluation no execution capability;
7. prevents authority/autonomy escalation;
8. fails closed on missing/conflicting evidence;
9. preserves Mission Control as read-only;
10. introduces no production schema, route, credential, worker or provider change.

## Next gate

After P2 validation: **P3 — Isolated Policy Evaluator Validation**.

`PHIL_AI_OS_PHASE_2_3_P2_CONTRACT_DEFINED`
