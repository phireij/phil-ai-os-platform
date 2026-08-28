# Phil AI OS Platform — Phase 2.3 P1 Approval & Policy Surface Discovery Result

**Phase:** 2.3 P1  
**Status:** GREEN  
**Date:** 2026-08-28  
**Workflow run:** `33148733258`  
**Job:** `98775545009`  
**Evidence artifact:** `phase-2-3-p1-approval-policy-discovery-evidence` (`9676817881`)

## Result

P1 completed read-only discovery successfully with no production mutation.

## Authoritative approval / execution surfaces

Production already contains durable primitives needed by Phase 2.3:

- `approval_requests` — 52 rows at discovery; states: 19 approved, 2 denied, 31 expired; 9 consumed and 43 unconsumed.
- `approval_notification_outbox` — durable approval delivery queue; 3 rows.
- `execution_audit` — 36 rows with `approval_id` and `task_id` correlation fields.
- `usage_ledger` — 18 rows.
- `route_policies` — 4 route-policy rows keyed by task class.
- `task_lifecycle_events` — durable canonical lifecycle evidence.
- `task_handoffs` — one accepted Phase 2.2 handoff row.
- `agent_registry` — Hermes L3 enabled/assignable and `specialist-worker-01` L1 disabled/non-assignable.

The approval schema already contains decision identity/time/note fields, expiry, browser-link metadata, one-time consumption fields (`consumed_at`, `consumed_by`), task class, routing snapshot and canonical `task_id`.

## Existing code-level controls

The current Control API contains explicit functions for:

- deterministic classification and route evaluation;
- approval creation, lookup, decision, browser-token decision and consumption;
- execution audit and usage recording;
- routed execution;
- execution kill-switch enforcement;
- execution task-class allowlist enforcement;
- coordinator assignment, planning and handoff semantics.

Production environment controls include:

- `PHIL_AI_OS_APPROVAL_TTL_SECONDS`;
- `PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES` = `general`;
- `PHIL_AI_OS_EXECUTION_KILL_SWITCH`;
- execution request/output limits;
- routed execution and live-test controls.

Unauthenticated approval request/approve/deny and execution probes returned HTTP 401.

## Existing notification and operator surfaces

- `phil-ai-os-approval-notification-dispatcher.timer` is enabled.
- Mission Control exposes approval/audit/handoff evidence read-only.
- Mission Control GET read model returned 200; POST/PUT/PATCH/DELETE remained 405.

## Gap identified

There is **no canonical reusable risk-tier / autonomous-ceiling policy decision object or durable policy-decision table** in the discovered production schema.

`route_policies` governs provider/model routing by task class; it is not an authorization/risk policy framework. The temporary Phase 2.2 A6.8 canary policy mechanism is task-specific and must not be generalized silently.

Therefore Phase 2.3 needs a new policy contract before any persistence or evaluator is considered.

## Smallest safe next boundary

Proceed to P2 with an off-production contract that keeps five concepts separate:

1. classification;
2. risk/policy decision;
3. human authorization;
4. execution eligibility;
5. execution.

Risk tier and autonomy ceiling must also remain separate from the registry `authority_ceiling`. A higher agent authority ceiling is never an autonomy grant.

## Production invariants preserved

- execution allowlist remains `general` only;
- Mission Control remains read-only;
- specialist remains L1 disabled/non-assignable;
- monitoring, backup and self-heal remain active;
- no provider call, approval decision, approval consumption, execution call, service restart, schema change or authority expansion occurred.

`PHIL_AI_OS_PHASE_2_3_P1_GREEN`
