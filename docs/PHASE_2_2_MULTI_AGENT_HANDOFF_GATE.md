# Phil AI OS Platform — Phase 2.2 Multi-Agent Handoff Gate

**Phase:** 2.2 — Multi-Agent Handoff Foundation
**Status:** OPEN / GOVERNED DISCOVERY
**Opened:** 2026-08-28

## Purpose

Phase 2.2 begins the governed path toward multi-agent coordination and handoff. The phase is intentionally split so that discovery and contract work can proceed before any new worker, authority, task class, automatic delegation, or execution capability is activated.

## Entry conditions inherited from Phase 2.1O

- Mission Control remains read-only.
- Production execution allowlist remains `general` only.
- Hermes remains the only registered/assignable worker and retains authority ceiling L3.
- Human approval boundaries remain authoritative.
- Workload/readiness evidence remains durable and fail-closed.
- No readiness state grants authority or triggers action.
- No direct provider bypass is permitted.

## Non-negotiable safety boundary

Opening Phase 2.2 does **not** itself authorize:

- registration or activation of a second production worker;
- assignment to a new agent;
- higher authority ceilings;
- broader execution task classes;
- automatic handoff, retry, reroute, delegation, or execution;
- Mission Control mutation endpoints;
- provider/model/credential changes;
- approval bypass or weakening of one-time approval consumption.

Any production activation that introduces one of the above must pass a separate bounded activation gate with explicit evidence and rollback.

## Gate sequence

### A1 — Read-Only Multi-Agent Surface Discovery
Inspect current production schemas, routes, registry semantics, assignment history, planning data, lifecycle correlation fields, approval boundaries, and Mission Control read model. Determine what already exists and what is missing for safe handoff. No mutation.

### A2 — Isolated Handoff Contract
Define the canonical handoff contract off-production: source agent, target agent, task identity, authority ceiling, task class, reason, correlation ID, lifecycle transition, approval requirement, timeout/expiry, rollback/containment, and audit evidence. Missing or conflicting evidence must fail closed.

### A3 — Capability / Authority Matrix
Define which agent roles may observe, plan, request handoff, accept work, execute, escalate, and close work. No production authority expansion. The matrix must preserve human approval where required and prevent privilege escalation through delegation.

### A4 — Production Preflight
Prove the minimum additive production change, compatibility with current Hermes-only L3 operation, rollback boundary, database migration needs, read-model impact, and monitoring/backup readiness.

### A5 — Bounded Second-Worker Registration
Only after explicit activation authorization and successful A1–A4. Register the smallest non-executing or tightly constrained second worker first. No automatic assignment; no provider execution unless separately approved by an existing governed execution boundary.

### A6 — Controlled Handoff Verification
Verify one bounded handoff path with durable evidence, explicit source/target identity, authority containment, approval behavior, lifecycle correlation, auditability, replay protection, and rollback. Avoid provider execution if the handoff semantics can be proven without it.

### A7 — Mission Control Read Model Integration
Expose multi-agent state read-only: registered workers, authority ceilings, presence, workload, handoff state, and evidence completeness. Mission Control must remain observational and non-authoritative.

### A8 — Closure
Revalidate governance invariants, fail-closed behavior, backup/monitoring, approval boundaries, and absence of unintended authority. Close Phase 2.2 only when handoff is durable, attributable, auditable, bounded, and safe.

## Required handoff evidence

A trustworthy handoff must be able to prove at minimum:

- canonical task ID;
- source agent identity;
- target agent identity;
- source and target authority ceilings at the time of handoff;
- task class and scope;
- explicit handoff reason;
- durable correlation ID;
- legal lifecycle transition;
- approval requirement and decision state where applicable;
- acceptance/rejection/expiry state;
- no duplicate ownership ambiguity;
- no authority escalation by delegation;
- durable audit trail sufficient to reconstruct the decision and outcome.

## Fail-closed rules

- Missing target identity => no handoff.
- Missing authority evidence => no handoff.
- Unknown task class => no handoff.
- Conflicting ownership => indeterminate / contained, not automatically reassigned.
- Missing or ambiguous approval evidence => no execution.
- Missing durable correlation => handoff not proven.
- Stale/offline target presence alone never causes reroute or reassignment.
- A worker becoming `ready` never grants permission to receive work automatically.

## Current authorization level

The CEO instruction to continue authorizes Phase 2.2 discovery, contract design, read-only validation, and preparatory engineering. It does not by itself broaden production authority or enable a second executing worker. Production authority expansion remains a separately governed activation decision.
