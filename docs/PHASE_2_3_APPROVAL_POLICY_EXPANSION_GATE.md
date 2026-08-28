# Phil AI OS Platform — Phase 2.3 Approval & Policy Expansion Framework Gate

**Phase:** 2.3 — Approval & Policy Expansion Framework  
**Status:** OPEN / GOVERNED DISCOVERY  
**Opened:** 2026-08-28  
**Prerequisite:** Phase 2.2 formally CLOSED / GREEN

## Source-of-truth basis

`docs/PHASE_2_ENTRY_PREPARATION.md` defines Phase 2.3 as the workstream that must:

- convert Phase 1 approval primitives into reusable policy gates;
- define risk tiers and explicit autonomous ceilings;
- require canary validation before widening any task class or action scope.

This gate implements that workstream without authorizing a production authority expansion.

## Entry state inherited from Phase 2.2

- Control API remains the authoritative coordinator and execution boundary.
- Production execution allowlist remains `general` only.
- Hermes remains L3, enabled and assignable.
- `specialist-worker-01` remains L1, disabled, non-assignable and non-executing.
- Human approval remains authoritative.
- One-time approval consumption and replay rejection remain mandatory.
- Durable approval/execution/handoff/lifecycle evidence remains required.
- Mission Control remains a read-only observer.
- Automatic assignment/retry/reroute/delegation/execution remain false.
- Monitoring, backup and backup self-heal remain mandatory.
- No provider bypass is permitted.

## Phase objective

Create a reusable, explicit, auditable policy-decision framework that can answer, without granting authority by itself:

1. What risk tier does a proposed action belong to?
2. What authority ceiling is required?
3. Is human approval mandatory?
4. What evidence must exist before execution can become eligible?
5. What scope, expiry, usage count and replay rules apply?
6. What conditions require fail-closed denial or operator escalation?
7. Which task/action classes remain prohibited regardless of agent readiness?

The framework must separate **classification**, **policy decision**, **human authorization**, **execution eligibility**, and **execution** into distinct concepts.

## Non-negotiable rules

Phase 2.3 design must preserve:

- deny by default;
- human approval for any sensitive or newly expanded production scope;
- agent self-approval prohibited;
- policy evaluation cannot itself execute;
- authority ceilings are maxima, never grants;
- readiness is evidence, never permission;
- approval remains task/action/scope specific;
- approval is expiring and one-time consumable where execution is authorized;
- replay is rejected before a second provider call;
- execution must remain routed through the Control API;
- direct provider bypass prohibited;
- kill-switch behavior preserved;
- durable decision and execution audit linkage;
- ambiguous/missing/conflicting policy evidence fails closed;
- no automatic task-class expansion;
- no automatic autonomous-ceiling expansion;
- no Mission Control mutation authority.

## Explicitly not authorized by opening Phase 2.3

This document does **not** authorize:

- adding `routine` or another task class to the production execution allowlist;
- enabling permanent specialist eligibility;
- specialist provider credentials or provider execution;
- autonomous approval;
- automatic approval consumption;
- recurring/automatic handoff or delegation;
- arbitrary shell, filesystem, network or external-system writes;
- broader provider/model access;
- Mission Control write endpoints;
- higher agent authority ceilings;
- weakening current approval/replay/kill-switch controls.

## Initial gate sequence

### P1 — Read-Only Approval & Policy Surface Discovery
Inventory current approval schema/routes, one-time consumption semantics, task classification, execution allowlist, kill switch, audit linkage, policy/config surfaces, Mission Control approval visibility, notification/outbox integration, and any existing risk/authority metadata. No production mutation.

### P2 — Risk-Tier & Policy Decision Contract
Define a canonical risk-tier model, policy-decision schema, required evidence, autonomous ceilings and explicit deny/escalate outcomes. Validate off-production. No production authority expansion.

### P3 — Isolated Policy Evaluator Validation
Build the smallest pure/deterministic policy evaluator in isolation. Validate missing/conflicting evidence, ceiling violations, self-approval rejection, expiry, replay, kill switch, task-class restrictions and human-approval requirements.

### P4 — Production Preflight
Prove the minimum additive persistence/read-model change, compatibility with current `general`-only execution, rollback boundary, backup/monitoring readiness, and zero secret exposure.

### P5+ — Governed Activation Stages
Any production persistence/writer activation, reusable approval-policy activation, autonomous ceiling greater than zero, new task/action class, or real policy-gated execution canary must be separately defined after P1–P4 evidence. A gate that expands production authority requires explicit CEO authorization before activation.

## P1 success criteria

P1 must determine:

- authoritative approval table/schema and decision fields;
- exact approval request/approve/deny/execute routes;
- where and how one-time consumption is enforced;
- how replay is rejected;
- current task classification and allowlist mechanics;
- kill-switch/config controls;
- durable execution audit linkage;
- current authority metadata relevant to approval decisions;
- current Mission Control/read-model approval representation;
- existing policy/config files and whether a reusable policy decision table already exists;
- whether new persistence is actually required for Phase 2.3;
- the smallest safe P2/P3 design boundary.

## Current authorization level

The instruction to proceed authorizes Phase 2.3 discovery, contract design, isolated validation and read-only/preparatory engineering. It does not authorize any new autonomous approval, executing worker, task class, provider call or production authority expansion.

## Immediate next action

Proceed with **P1 — Read-Only Approval & Policy Surface Discovery**.

`PHIL_AI_OS_PHASE_2_3_GATE_OPEN`
