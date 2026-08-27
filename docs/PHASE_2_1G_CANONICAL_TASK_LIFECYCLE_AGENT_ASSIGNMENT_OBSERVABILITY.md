# Phil AI OS Platform — Phase 2.1G Canonical Task Lifecycle & Agent Assignment Observability

**Phase:** 2.1G  
**Status:** STARTED — READ-ONLY DISCOVERY / CONTRACT  
**Date:** 2026-08-27

## Objective

Build on Phase 2.1F canonical `task_id` persistence so Mission Control can represent a genuine task lifecycle and authoritative task/agent ownership without inventing state, widening execution authority, or creating a second control plane.

## Canonical lifecycle target

`RECEIVED -> CLASSIFIED -> ASSIGNED -> PLANNED -> POLICY_CHECK -> [APPROVAL_PENDING] -> AUTHORIZED -> EXECUTING -> {SUCCEEDED | FAILED | BLOCKED | CANCELLED} -> AUDITED -> CLOSED`

Exception states remain:

`DENIED`, `EXPIRED`, `REJECTED`, `AMBIGUOUS`, `CONTAINED`.

A handoff or assignment change must never increase authority.

## Phase 2.1G first principle

Lifecycle and assignment state must be sourced from durable authoritative records or explicitly marked unavailable. Mission Control must not synthesize a definitive lifecycle stage from incomplete evidence.

## Discovery questions

1. Which current `approval_requests` fields can prove receipt, classification, requester/source, approval state, authorization, consumption, denial, expiry, and responsible human/agent identity?
2. Which current `execution_audit` fields can prove execution start/outcome/audit state and canonical `task_id` linkage?
3. Which current fields can establish authoritative `assigned_agent` / task owner semantics without relying on UI declaration alone?
4. Which lifecycle stages are already provable from existing persistence?
5. Which lifecycle stages remain only derivable, partial, legacy, or unavailable?
6. Can Phase 2.1G improve Mission Control read-only observability without another production DB migration?

## Safety invariants

- Mission Control remains read-only.
- Production execution allowlist remains `general` only.
- Direct provider bypass remains prohibited.
- Human approval and Control API governance remain authoritative.
- No execution call is made for discovery or validation.
- No approval decision/consumption is changed for discovery or validation.
- No provider configuration or credentials are changed.
- No specialist-agent or autonomous delegation authority is enabled.
- Historical task IDs are not fabricated or backfilled.
- Agent assignment cannot imply more authority than the assignee already holds.
- Backups, monitoring, and self-heal remain active.

## Phase 2.1G planned gates

1. **Durable lifecycle source inventory** — read-only schema/key/state inventory from the live Control API database and current API/read-model surfaces.
2. **Lifecycle provenance contract** — classify each lifecycle field as authoritative, derived, legacy/partial, or unavailable.
3. **Read-model candidate** — expose canonical task records only where a real persisted `task_id` exists; attach provable lifecycle/assignment evidence.
4. **Isolated/live read-only validation** — verify no row-count changes, no mutations, no provider/execution activity, and no authority expansion.
5. **Mission Control presentation** — show lifecycle/assignment provenance without action controls.
6. **Final closure verification** — GREEN only after production read-only observability is stable and the existing safety posture remains unchanged.

## Exit criteria

Phase 2.1G may close GREEN only when:

- canonical task lifecycle visibility is based on proven sources;
- agent/task assignment semantics are explicit and provenance-labelled;
- ambiguous lifecycle states remain visibly ambiguous rather than guessed;
- canonical `task_id` mismatches remain zero;
- `general` remains the only production task class;
- Mission Control remains read-only with mutation verbs blocked;
- operator authentication remains fail-closed;
- approval/execution/provider authority is unchanged;
- recovery services remain active.
