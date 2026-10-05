# Autonomous Operations MVP — Phase 0 Architecture

**Status:** PROPOSED / A0-INERT  
**CEO direction approved:** 2026-10-05  
**Verified baseline:** `main@35853cea3c8ebedf8f61a3ab5b3c81e5dcfa148e`

## Objective

Make Phil AI OS the persistent, governed orchestration and project-control platform for Phil AI OS itself, Ruby's Cake Delights HQ, KCFC Portal, and future pluggable projects.

The target loop is:

```
project state
  -> durable task queue
  -> policy-aware task selection
  -> agent assignment
  -> bounded execution
  -> independent verification
  -> authoritative state update
  -> next authorized task
```

If an action exceeds delegated authority, that action MUST stop and enter an approval-required state. Independent authorized work MAY continue.

## Phase 0 boundary

Phase 0 creates contracts and inert/read-only projections only. It does not raise the production autonomy ceiling.

- autonomy ceiling: A0
- Mission Control: read-only
- execution allowlist: unchanged
- Hermes authority: unchanged
- specialist-worker authority/eligibility: unchanged
- production cutover/DNS/live payment: not authorized
- real order/payment creation for QA: not authorized
- Twilio: deferred/disabled
- Ruby and KCFC production boundaries: unchanged

## Existing primitives to reuse

Do not rebuild these capabilities:

1. canonical task/lifecycle identity and durable correlation;
2. Hermes runtime presence/readiness and workload evidence;
3. governed approval-to-execution correlation and replay protection;
4. Phase 2.2 durable multi-agent handoff foundation;
5. Phase 2.3 policy/risk framework and inert append-only policy ledger;
6. Mission Control read-only observer boundary;
7. monitoring, backup and self-heal controls;
8. Operations Hub task extraction and Automation Hub simulation foundations.

## Missing AO-MVP capabilities

### 1. Project Registry
A canonical registry identifies every managed project and its evidence sources, repositories, environments, authority profile, current objective and integration adapter.

Initial projects:
- `phil-ai-os`
- `rubys-cake-delights-hq`
- `kcfc-portal`

### 2. Authoritative Project State
Each project exposes a normalized state containing:
- current objective/milestone;
- completed work;
- work in progress;
- queued work;
- blockers;
- agent activity;
- latest verified repository state;
- latest verified deployment/environment state;
- CEO decisions/approvals required;
- next autonomous actions;
- evidence freshness and provenance.

Repository/deployment facts must be evidence-backed. Unknown or stale facts remain explicit; they are never inferred into GREEN.

### 3. Durable Work Queue
The existing read-only in-memory channel candidate queue is not the autonomous queue. AO-MVP requires durable, idempotent work records with:
- project and objective identity;
- dependencies;
- priority;
- task class and risk tier;
- required authority;
- eligible agent/capability set;
- verification contract;
- approval state;
- lifecycle state;
- execution and verification evidence references.

### 4. Policy-Aware Selector
A selector may choose work only when:
- dependencies are satisfied;
- evidence is fresh enough for the task;
- the task class is allowed;
- required authority is within the active delegation;
- an eligible healthy agent exists;
- no approval gate is unresolved.

No eligible task means no execution.

### 5. Persistent Orchestrator
A durable service/timer repeatedly performs:
`reconcile -> select -> assign -> execute -> verify -> record -> reconcile`.

The orchestrator MUST be crash-safe, idempotent and replay-safe. It must not equate an execution attempt with completion.

### 6. Verification Gate
A task reaches `completed` only after its declared verifier succeeds and evidence is durably recorded. Failed or inconclusive verification must remain visible and fail closed.

### 7. Approval Escalation
Tasks beyond delegated authority enter `awaiting_ceo_approval`. Approval is scoped to the exact task/plan/evidence binding and is one-time where required. Denial or expiry cannot silently become approval.

### 8. Master Multi-Project Read Model
Mission Control consumes a privacy-safe, read-only aggregate projection across all registered projects. This is the canonical source for the executive question: "Give me the overall project status."

### 9. Executive Client Boundary
Chat is the primary command/decision interface. A future OpenAI Dot/AI Chief of Staff is an optional executive client above Phil AI OS, not a runtime dependency. Both consume governed Phil AI OS interfaces.

## Initial adapter posture

### Phil AI OS
Source of truth: this repository plus verified runtime/control-plane evidence.  
Role: orchestration/control platform and first self-managed project.

### Ruby's Cake Delights HQ
Source of truth: existing Ruby contracts/readiness/evidence in this repository plus separately verified WooCommerce/preproduction evidence. Preserve all existing work. First real business integration.

### KCFC Portal
Source of truth: `phireij/KCFC-Portal` and verified staging evidence. Production `main` and staging/redevelopment remain isolated. Phil AI OS initially observes/report status only; it gains no KCFC production mutation authority.

## Proposed AO-MVP sequence

- AO-0: architecture, project registry contract and reconciled baseline — A0/inert.
- AO-1: durable project-state store and evidence reconciliation.
- AO-2: durable work queue and dependency model.
- AO-3: inert policy-aware selector and assignment planner.
- AO-4: synthetic end-to-end orchestrator loop with verification and escalation.
- AO-5: Master Multi-Project Mission Control read model.
- AO-6: Ruby adapter as first real integration; KCFC read-only adapter second.
- AO-7: exact A1 authority matrix, threat model, rollback plan and CEO approval gate.
- AO-8: bounded A1 activation for explicitly allowlisted reversible development tasks only.

## A1 is not authorized by this document

A future A1 proposal should allow only explicitly registered, reversible, low-risk task classes and should retain approval gates for production, financial, credential, destructive, customer-impacting, public-publish and authority-expansion actions.

Branch merging must not become unattended while repository branch protection/ruleset enforcement remains unresolved.

## Phase 0 exit criteria

Phase 0 is complete when:
1. project registry and project-state contracts are committed;
2. the three initial projects have evidence-backed baseline records;
3. AO-MVP sequence supersedes the old sprint sequence as the executive priority without deleting historical sprint records;
4. Mission Control remains read-only;
5. no production authority changes;
6. CI validates the new static contracts;
7. the next implementation gate is AO-1.
