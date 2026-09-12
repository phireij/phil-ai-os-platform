# Sprint 5 — Channel Task Extraction Readiness

Date: 2026-09-12  
Status: BOUNDED PREPARATORY READINESS / NON-PRODUCTION

## Purpose

Advance the Sprint 5 roadmap item **Extract orders/tasks** without activating live channel replies or production execution.

## Bounded capability

The five existing fixture-only channel inputs — Facebook, Instagram, Telegram, WhatsApp and Google Business — can now be normalized and converted into deterministic operator-review task candidates.

Current task mapping:

- order inquiry → `order_inquiry_task`
- pickup inquiry → `pickup_inquiry_task`
- product inquiry → `product_inquiry_task`
- complaint → `customer_issue_task`
- public review → `public_review_task`
- general inquiry → `general_inquiry_task`

Governance remains authoritative for approval routing. Sensitive complaints and public reviews enter `awaiting_approval`; currently safe/non-sensitive fixture tasks enter `ready_for_operator_review`. Neither state grants execution authority.

## Queue and dashboard

`TaskCandidateQueue` provides idempotent, read-only task registration. Its aggregate read model omits customer text. Full customer context remains available only through bounded task-detail access for future operator-review surfaces.

The unified Operations Hub dashboard may consume the task queue and expose aggregate task counts, task types, source counts and approval workload while continuing to hide raw customer text, custom notes and reference-image names.

## Safety boundary

All task candidates remain `operator_review_only`. The following remain false:

- automatic execution
- execution authorization
- external channel reply authorization
- WooCommerce mutation
- order creation
- payment execution
- SMS sending
- inventory mutation
- production publication
- general mutation authority

No live channel API endpoints or credentials are introduced.

## Executable evidence

- runtime: `apps/operations-hub/src/operations_hub/task_extraction.py`
- queue: `apps/operations-hub/src/operations_hub/task_queue.py`
- contract: `contracts/operations/task-candidate.schema.json`
- tests: `apps/operations-hub/tests/test_task_extraction.py`
- validator: `apps/operations-hub/tools_validate_operations.py`

Expected marker:

`PHIL_AI_OS_SPRINT_5_TASK_EXTRACTION_GREEN tasks=5 awaiting_approval=2 operator_review=3`

## Control note

This is advance Sprint 5 readiness only. It does not constitute formal Sprint 5 entry or closure and does not change the current formal roadmap sequence. Production activation, live replies, Mission Control writes, Hermes live execution and higher autonomy remain separately gated.
