# Phase 2.1K — Human Approval-to-Execution Correlation Gate

Status: **AUTHORIZED FOR DISCOVERY / NO EXECUTION YET**

## Basis

Phase 2.1J is GREEN and formally closed. Its closure explicitly deferred human approval, one-time approval consumption, and governed execution validation for the new canonical task flow.

Phase 2.1K takes that deferred item as the next narrow gate. It does not authorize wider execution scope, additional task classes, new agents, Mission Control mutation controls, autonomous approval, or autonomous execution.

## Objective

Prove that a genuine canonical task created through the coordinator-controlled intake path can preserve exact identity and governance linkage through:

`task intake -> approval request -> human approval -> one-time approval consumption -> governed execution -> durable execution audit`

The validation must demonstrate that the canonical `task_id`, approval identity, requester/agent identity, task class, and governed execution unit remain correlated without creating a second authority path around the Control API.

## Required invariants

1. Production execution allowlist remains `general` only.
2. Hermes remains the only registered assignable worker and retains its existing authority ceiling.
3. Agent self-approval remains impossible.
4. Human approval is required for the controlled canary before any governed execution attempt.
5. Approval consumption is one-time and durable.
6. Replay is rejected before a provider call.
7. Successful execution, if later authorized, must produce durable audit evidence linked to the exact approval and canonical task.
8. Mission Control remains read-only; mutation methods remain blocked.
9. Unauthenticated Control API mutation requests remain rejected.
10. Monitoring, scheduled backup, and backup self-heal remain active.
11. No allowlist, provider/model, credential-boundary, agent-authority, or Mission Control exposure change is permitted by this gate.

## Gate sequence

### K1 — Read-only correlation discovery

Inspect current production schema, handler/source shape, and existing durable records to determine whether the new Phase 2.1J canonical task identity can already be carried through approval consumption and execution audit without migration.

**Permitted:** read-only source/schema/state inspection and health checks.

**Prohibited:** approval decisions, approval consumption, `/v1/execute`, provider calls, database writes, service restarts, image changes, allowlist changes, and agent-authority changes.

### K2 — Isolated contract validation

If K1 shows a correlation gap, build and validate the smallest additive candidate in isolation. No production activation is implied.

### K3 — Production preflight

Confirm rollback, health, monitoring, backup/self-heal, `general`-only allowlist, human approval path, one-time consumption semantics, replay rejection, and exact task/approval identity binding.

### K4 — Human approval canary preparation

Create exactly one bounded `general` canonical task through the genuine coordinator-controlled intake path. Automatic Telegram notification may operate exactly as established in Phase 2.1J. The task must remain unexecuted until explicit human approval is recorded.

### K5 — Controlled approved execution canary

Only after K1–K4 are GREEN and the human operator explicitly approves the canary, consume that exact approval once and attempt the exact governed execution unit through the Control API.

### K6 — Post-execution and replay verification

Verify durable task/approval/execution audit linkage; verify replay rejection occurs before any second provider call; verify no unrelated state or authority changed.

### K7 — Closure

Close Phase 2.1K GREEN only if all required invariants and evidence are present. Otherwise stop fail-closed and record the blocker or rollback result.

## Immediate authorized action

Proceed with **K1 read-only correlation discovery only**.

No human approval, approval consumption, governed execution, provider call, or production mutation is authorized by this document.

`PHIL_AI_OS_PHASE_2_1K_GATE_DEFINED`
