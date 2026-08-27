# Phase 2.1L — Server-Side Approval Notification Outbox & Delivery Reliability Gate Closure

Status: **CLOSED GREEN**

Date: 2026-08-27

## Objective result

Phase 2.1L established and validated a durable, source-independent approval-notification reliability path without creating a second authority path.

Production flow is now:

`approval created -> atomic outbox enqueue -> scheduled server dispatcher -> established approval notifier -> governed Control API review link -> Telegram delivery -> durable delivered/retry/dead-letter state`

Notification remains non-authoritative. It cannot approve, deny, consume, route, execute, widen authority, or create a duplicate approval.

## Gate results

- L1 — Read-only notification-path discovery: **GREEN**
- L2 — Isolated outbox contract design/validation: **GREEN**
- L3 — Production migration/preflight: **GREEN**
- L4 — Controlled activation: **GREEN**
  - L4A — additive outbox schema activation: **GREEN**
  - L4B — source-independent atomic enqueue trigger: **GREEN**
  - L4C — one-shot dispatcher installation, initially unscheduled: **GREEN**
- L5 — Notification delivery canary: **GREEN**
- L6 — Retry/idempotency/failure verification: **GREEN**
- L6B — server-dispatcher production cutover: **GREEN**
- L7 — Final read-only closure verification: **GREEN**

## Production architecture now active

### Durable outbox

Table:

`approval_notification_outbox`

The durable record contains notification correlation/delivery metadata only. Generic outbox state does **not** contain review-link tokens, Telegram bot tokens, bearer credentials, arbitrary payloads/commands, provider selections, or model selections.

### Atomic enqueue

Trigger:

`trg_approval_notification_outbox_enqueue`

For every newly inserted pending approval, the trigger atomically creates a single `approval_pending` / `telegram` notification intent carrying the exact `approval_id` and `task_id`.

Duplicate suppression is enforced by deterministic event identity and schema uniqueness.

### Dispatcher

Executable:

`/usr/local/sbin/philaios-approval-notification-dispatcher`

Systemd units:

- `phil-ai-os-approval-notification-dispatcher.service`
- `phil-ai-os-approval-notification-dispatcher.timer`

Production cadence: approximately every 60 seconds.

The dispatcher leases one eligible row, calls the established notifier with only the `approval_id`, records confirmed delivery, or reuses the same row for bounded retry/dead-letter handling.

### Hermes client cutover

The persistent Hermes Mission Control client now defaults to server-outbox notification mode:

`PHIL_AI_OS_AUTO_NOTIFY_APPROVALS=0`

The legacy direct notifier code remains available only as an explicit rollback/override path; it is no longer the production default.

## L5 successful delivery canary

- Approval ID: `apr_c6a4ed5510bb474699f3ab68c8fd18ef`
- Task ID: `tsk_9fb9021a89e24dba94c11ed3361f6e4e`
- Task class: `general`
- Telegram message ID: `401`
- Outbox rows for canary: exactly `1`
- Dispatcher attempts: exactly `1`
- Final notification state: `delivered`
- Approval decision: none
- Approval consumption: none
- Execution audit links: `0`
- Provider/execution calls: none

The canary is notification-only and must not be approved or executed. If still pending, it should be allowed to expire naturally.

## L6 retry/failure canary

- Approval ID: `apr_958a420bf7c342cdaf29669eb13e74ac`
- Task ID: `tsk_3eae6a789d0d439f81cf15ad356521db`
- Task class: `general`
- Real Telegram delivery: none

A deliberately nonexistent transport target forced controlled delivery failure.

- Attempt 1: same row -> `retry_wait`
- Attempt 2: same row -> `dead_letter`
- Duplicate approval: false
- Duplicate outbox row: false
- Approval decision: none
- Approval consumption: none
- Execution audit links: `0`
- Provider/execution calls: none

The first L6 workflow attempt failed at GitHub-hosted SSH setup before any canary action. The unchanged job was rerun and completed GREEN without creating a duplicate test record.

This canary is also notification-only and must not be approved or executed. If still pending, it should be allowed to expire naturally.

## Final closure verification

L7 confirmed:

- SQLite `quick_check=ok`;
- outbox table present;
- atomic enqueue trigger present;
- forbidden secret/authority fields absent from outbox schema;
- eligible outbox queue depth: `0`;
- L5 durable state: `delivered`, one attempt;
- L6 durable state: `dead_letter`, two attempts;
- canary execution audit rows: `0`;
- Hermes remains the only registered assignable worker at authority ceiling `L3`;
- Control API health/readiness: GREEN;
- monitor active;
- scheduled backup active;
- backup self-heal active;
- notification dispatcher timer active;
- legacy direct notification default disabled;
- server-outbox mode active;
- execution allowlist remains `general` only;
- Mission Control remains read-only;
- no approval mutation, notification send, execution call, or provider call occurred during final verification.

## Required invariant disposition

1. Production execution allowlist remained `general` only — **PASS**.
2. Hermes remained the only registered assignable worker at L3 — **PASS**.
3. Human approval policy remained unchanged — **PASS**.
4. Agent self-approval remained impossible — **PASS**.
5. Notification logic gained no approve/deny/consume/route/execute authority — **PASS**.
6. Retry never created a duplicate approval — **PASS**.
7. Exact `approval_id` / `task_id` correlation is durable — **PASS**.
8. Review-link token handling remains inside the established Control API/notifier boundary; raw tokens are not stored in the generic outbox — **PASS**.
9. Mission Control mutation authority was not expanded — **PASS**.
10. Monitoring, scheduled backup, and backup self-heal remain independent and active — **PASS**.
11. No provider/model policy, credential boundary, task-class allowlist, agent authority, or autonomous execution expansion occurred — **PASS**.

## Rollback assets

Database rollback snapshots:

- `/app/state/control-plane.db.pre-phase21l-l4a-20260827T121718Z`
- `/app/state/control-plane.db.pre-phase21l-l4b-20260827T121834Z`

Hermes client rollback:

`/opt/phil-ai-os-platform/phil-ai-os-platform-phase1/infrastructure/hermes/philaios-mission-control-client.py.pre-phase21l`

The dispatcher timer can be disabled independently without affecting approval/execution authority.

## Scope retained after closure

Phase 2.1L does **not** authorize broader task classes, new agents, Mission Control mutation controls, autonomous approval, autonomous execution, wider provider/model policy, or credential-boundary expansion.

Production execution authority remains `general`-only and human-governed.

`PHIL_AI_OS_PHASE_2_1L_CLOSED_GREEN`
