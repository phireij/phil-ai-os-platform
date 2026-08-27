# Phase 2.1L — Server-Side Approval Notification Outbox & Delivery Reliability Gate

Status: **AUTHORIZED FOR READ-ONLY DISCOVERY / NO PRODUCTION MUTATION YET**

Date: 2026-08-27

## Basis

Phase 2.1K is CLOSED GREEN and proved the complete governed canonical task chain through human approval, one-time approval consumption, governed execution, durable audit correlation, and replay rejection.

Phase 2.1J explicitly deferred a general server-side notification outbox/dispatcher for approval sources other than the Hermes Mission Control client. The current Hermes client auto-notifies Telegram after creating a pending approval, but notification delivery is client-coupled and not yet a durable server-side reliability contract.

## Objective

Establish the smallest safe architecture for durable approval-notification delivery without creating a new authority path.

Target flow:

`approval created -> durable notification intent -> dispatcher -> Telegram review link delivery -> delivery result/audit`

Notification delivery must remain non-authoritative: it may notify or retry notification transport, but it may never approve, deny, consume, route, execute, widen authority, or create a duplicate approval.

## Required invariants

1. Production execution allowlist remains `general` only.
2. Hermes remains the only registered assignable worker at the existing L3 ceiling.
3. Human approval remains mandatory under the active policy.
4. Agent self-approval remains impossible.
5. Notification logic cannot approve, deny, consume, route, or execute a task.
6. Notification retry must never create a duplicate approval request.
7. Any future outbox record must preserve exact `approval_id` and `task_id` correlation.
8. Review-link token handling must remain inside the established Control API boundary; raw tokens must not be durably exposed in generic logs/state.
9. Mission Control remains read-only; mutation authority is not expanded by this gate.
10. Monitoring, scheduled backup, and backup self-heal remain independent and active.
11. No provider/model policy, credential boundary, task-class allowlist, agent authority, or autonomous execution expansion is permitted.

## Gate sequence

### L1 — Read-only notification-path discovery

Inspect current production Control API source/schema/state, Hermes notification client, notifier scripts/services, and existing durable tables to determine whether any reusable notification-outbox primitives already exist.

**Permitted:** read-only source/schema/state inspection, service-status checks, file existence/metadata inspection, and health/readiness checks.

**Prohibited:** approval creation/decision/consumption, notification sending, `/v1/execute`, provider calls, database writes, service restarts, image changes, allowlist changes, agent-authority changes, or Mission Control mutations.

### L2 — Isolated outbox contract design/validation

Only if L1 confirms the gap, define the smallest additive durable schema and dispatcher contract in isolation. No production activation is implied.

### L3 — Production migration/preflight

Validate additive migration safety, rollback, health, monitoring, backup/self-heal, duplicate suppression, token boundary, and no-authority semantics.

### L4 — Controlled activation

Activate only the minimal server-side notification-intent/outbox mechanism, preserving the existing Hermes client path until proven safe.

### L5 — Notification delivery canary

Create exactly one bounded pending `general` approval through the genuine coordinator path and prove exactly one notification delivery path without approval decision, consumption, execution, or provider call.

### L6 — Retry/idempotency/failure verification

Prove transport failure/retry cannot duplicate the approval or create authority side effects; verify durable delivery evidence and fail-closed behavior.

### L7 — Closure

Close Phase 2.1L GREEN only if all invariants and evidence are satisfied.

## Immediate authorized action

Proceed with **L1 read-only notification-path discovery only**.

No notification send, approval mutation, approval consumption, governed execution, provider call, production schema change, service restart, or authority expansion is authorized by this document.

`PHIL_AI_OS_PHASE_2_1L_GATE_DEFINED`
