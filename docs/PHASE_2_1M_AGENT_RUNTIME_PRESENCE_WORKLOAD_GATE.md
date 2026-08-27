# Phase 2.1M — Agent Runtime Presence & Workload Read Model Gate

Status: **AUTHORIZED FOR READ-ONLY DISCOVERY ONLY**

Date: 2026-08-27

## Basis

Phase 2.1L is CLOSED GREEN. The canonical task, lifecycle, assignment, approval, governed execution, audit correlation, and server-side approval notification paths are established without widening production authority.

The Phase 2.1 Mission Control gap matrix still identifies **agent/session operational status** as AMBER: no complete production contract is evidenced for agent presence, heartbeat/freshness, workload, or degraded-state semantics.

## Objective

Define and validate the smallest safe **read-only agent runtime presence and workload model** for Mission Control before any multi-agent runtime expansion.

Target read model:

`registered agent identity -> runtime presence evidence -> freshness/degraded classification -> current bounded workload -> operator-visible read model`

This gate does not authorize new agents, task classes, execution authority, delegation, autonomous retry, or Mission Control mutation controls.

## Required invariants

1. Production execution allowlist remains exactly `general`.
2. Hermes remains the only registered assignable production worker at the existing L3 ceiling.
3. Human approval policy and no-self-approval invariant remain unchanged.
4. Mission Control remains read-only.
5. Presence/heartbeat state is observational only and cannot grant authority.
6. A stale/offline/degraded classification cannot automatically reroute, retry, delegate, or execute work.
7. Workload counts must derive from durable task/lifecycle/approval state where possible, not inferred hidden authority.
8. Runtime/container health evidence must be clearly distinguished from agent logical presence.
9. No raw credentials, tokens, provider secrets, or unrestricted host details may be exposed in the operator read model.
10. Monitoring, backup, backup self-heal, and approval-notification dispatcher remain independent and active.
11. No provider/model policy, execution allowlist, credential boundary, agent registry authority, or autonomous execution expansion is permitted.

## Gate sequence

### M1 — Read-only runtime-presence discovery
Inspect production agent registry, coordinator/task tables, lifecycle state, Hermes container/runtime metadata, existing health/heartbeat signals, and Mission Control read-model source. Determine what reliable freshness/workload primitives already exist.

**Permitted:** read-only schema/state/source inspection, health/readiness checks, container status/health metadata, systemd status, recent lifecycle counts.

**Prohibited:** database writes, approval creation/decision/consumption, Telegram sends, `/v1/execute`, provider calls, service restarts, container changes, registry changes, allowlist changes, agent authority changes, Mission Control mutations.

### M2 — Isolated presence/read-model contract validation
Only if M1 confirms gaps, define deterministic presence/freshness/workload semantics and validate them in isolation.

### M3 — Production preflight
Validate additive migration/read-model safety, rollback, monitoring independence, data minimization, and no-authority semantics.

### M4 — Minimal controlled activation
Add only the smallest read-only runtime status primitive required by the validated contract. No new agent or execution authority.

### M5 — Live read-model canary
Prove Mission Control correctly reports Hermes identity, presence/freshness, workload and degraded semantics without creating or executing work.

### M6 — Stale/degraded negative-path verification
Prove stale/degraded status is fail-safe and observational: no reroute, retry, delegation, approval mutation, or provider call.

### M7 — Closure
Close Phase 2.1M GREEN only if all invariants hold and the operator read model is evidence-based and non-authoritative.

## Immediate authorized action

Proceed with **M1 read-only discovery only**.

`PHIL_AI_OS_PHASE_2_1M_GATE_DEFINED`
