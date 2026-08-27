# Phase 2.1L L1 — Notification Path Discovery Result

Status: **GREEN / GAP CONFIRMED — L2 REQUIRED**

Date: 2026-08-27

## Production observations

Read-only discovery run `33069489301` completed successfully with marker:

`PHIL_AI_OS_PHASE_2_1L_L1_NOTIFICATION_DISCOVERY_OK`

The production Control API was healthy and ready. `phil-ai-os-monitor.service`, `phil-ai-os-backup.timer`, and `phil-ai-os-backup-self-heal.timer` were active. The production execution allowlist remained exactly `general`.

## Durable-state finding

Current tables:

`advisory_decisions, agent_registry, approval_requests, execution_audit, meta, model_catalog, observer_checkpoints, provider_state, route_policies, shadow_observations, sqlite_sequence, task_lifecycle_events, task_plans, usage_ledger`

No notification, outbox, delivery, or Telegram-specific durable table exists. The only notification-related durable table discovered was `approval_requests` itself.

## Control API finding

The deployed Control API contains approval creation and approval-link issuance primitives, but L1 found no server-side notification/outbox/dispatcher implementation.

Relevant existing primitives:

- `approval_create(...)`
- canonical `approval_id` / `task_id` linkage
- lifecycle `APPROVAL_PENDING`
- `approval_link_issue(approval_id)`
- authenticated approval reads

## Hermes notification finding

The current Hermes Mission Control client contains `notify_pending_approval(result)` and invokes:

`/usr/local/bin/philaios-telegram-approval-notifier <approval_id>`

The notifier:

1. reads the approval by `approval_id`;
2. requests the secure approval review link through the Control API;
3. sends the Telegram message;
4. reports transport status.

This confirms notification delivery is presently **client-coupled**, not a general durable server-side reliability path.

## Gap decision

A real Phase 2.1L gap exists.

L2 is required to define and validate the smallest additive durable notification-outbox contract before any production migration or activation.

No approval mutation, notification send, execution call, provider call, schema write, restart, or authority expansion occurred during L1.

`PHIL_AI_OS_PHASE_2_1L_L1_GREEN_L2_REQUIRED`
