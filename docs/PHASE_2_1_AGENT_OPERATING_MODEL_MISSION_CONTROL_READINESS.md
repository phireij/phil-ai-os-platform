# Phase 2.1 — Agent Operating Model & Mission Control Readiness Discovery

**Program:** Phil AI OS Platform  
**Status:** STARTED — DISCOVERY / READ-ONLY  
**Date:** 2026-08-26  
**CTO posture:** Governance-first, narrow authority, observable, reversible

## Entry basis

Phase 1 — Core AI OS Foundation is formally CLOSED and GREEN. Phase 1.27 passed the final foundation readiness gate with Control API health/readiness OK, monitoring and backup controls active, production execution restricted to the `general` task class, durable approval consumption, and successful execution audit linkage.

Phase 2.1 therefore begins without relaxing Phase 1 controls.

## Objective

Define the operating contract for Hermes, the CTO function, future specialist agents, Mission Control, approvals, task handoffs, authority levels, operator intervention, observability, and accountability before any meaningful expansion of production authority.

## Discovery workstreams

1. **Agent roles and identities** — define each agent's purpose, owner, responsibilities, and explicit non-authorities.
2. **Authority model** — classify read-only, propose, approval-required, bounded execution, and prohibited actions.
3. **Task lifecycle** — define intake → classification → routing → planning → approval → execution → audit → closure.
4. **Mission Control readiness** — determine the minimum interfaces and state Mission Control must expose before it can become the operational home for agents and the CTO office.
5. **Human control points** — define approval, escalation, interruption, denial, expiry, and emergency-stop behavior.
6. **Observability/accountability** — define agent identity, task ownership, approval linkage, execution records, outcomes, and operator-visible status.
7. **Safe expansion criteria** — establish evidence required before any new task class or agent authority can be enabled.

## Initial operating model hypothesis

### CEO / Human Operator
- Final authority over policy and material production expansion.
- Receives approval requests and can approve, deny, interrupt, or restrict activity.

### CTO Office
- Designs architecture, governance, validation gates, and rollout plans.
- May inspect and propose changes.
- Must not silently expand production authority.

### Hermes
- Primary operational agent/gateway candidate.
- Executes only through approved Phil AI OS boundaries.
- Must carry task/agent identity and preserve approval/audit linkage.

### Specialist Agents
- Future bounded workers for defined domains.
- No implicit inherited authority from Hermes or CTO.
- Each requires an explicit capability and policy contract before activation.

### Mission Control
- Candidate operational control surface, not an authority source by itself.
- Must display task state, agent identity, approvals, execution status, audit linkage, failures, and intervention controls before being treated as production-ready.

## Authority ladder

| Level | Meaning | Phase 2.1 default |
|---|---|---|
| L0 | Observe/read | Allowed for discovery where credentials permit |
| L1 | Analyze/propose | Allowed |
| L2 | Prepare action requiring approval | Allowed where existing approval controls apply |
| L3 | Bounded execution under explicit policy | Existing narrow production boundary only |
| L4 | Expanded autonomous production authority | Prohibited until separately gated |

## Mission Control minimum readiness criteria

Mission Control should not become the primary operating home until it can reliably provide:

- authenticated operator access;
- visible agent identity and task ownership;
- task lifecycle/status visibility;
- approval request and decision visibility;
- durable approval-to-execution linkage;
- execution outcome and failure visibility;
- audit/history access;
- operator interruption/deny controls;
- clear degraded/unhealthy state indication;
- no bypass around Control API governance;
- rollback/recovery awareness for production-affecting operations.

## Non-negotiable Phase 1 controls carried forward

- No unrestricted production autonomy.
- No silent execution-allowlist expansion.
- Human approval remains required where policy demands it.
- Approval consumption and execution outcomes remain auditable.
- Monitoring, backups, and backup self-heal remain protected controls.
- New authority is introduced only through narrow, testable, reversible increments.
- Existing production scope remains `general` only unless a later gate explicitly changes it.

## Phase 2.1 exit gate

Phase 2.1 may be declared GREEN only when:

1. agent roles and ownership are documented;
2. the authority ladder and approval matrix are documented;
3. the canonical task lifecycle is documented;
4. Mission Control gaps are inventoried against the minimum readiness criteria;
5. observability/audit requirements are mapped to existing Control API capabilities;
6. no uncontrolled execution path is introduced;
7. a bounded implementation plan for the next Phase 2 increment is approved.

## Current decision

**PHASE 2.1 STATUS: STARTED — DISCOVERY ONLY.**

No production allowlist expansion, provider call, execution mutation, approval mutation, or runtime configuration change is authorized by this document.
