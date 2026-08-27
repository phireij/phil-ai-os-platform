# Phase 2.1J — Automatic Telegram Notification Trigger Contract

Status: **DESIGN GATE**

## Goal
Ensure every newly created actionable approval is handed to the existing Telegram notifier automatically, without adding approval, execution, routing, or provider authority.

## Ownership
- Control API remains the authoritative approval/task source.
- Hermes remains the runtime that owns the existing Telegram notifier command and Telegram environment.
- Mission Control remains read-only.

## Required behavior
1. Approval creation commits first and returns a durable `approval_id` / canonical `task_id`.
2. A bounded notification trigger then invokes the existing Hermes notifier with only that `approval_id`.
3. The notifier resolves approval details from Control API and sends the existing review link/message.
4. Notification outcome is observational only. It cannot approve, deny, consume, assign, plan, route, or execute the task.
5. If notification delivery fails, the approval stays pending until expiry or human action. No execution may occur as a consequence of notification failure.
6. Expired/non-pending approvals remain fail-closed and must not produce actionable Telegram approval messages.

## Preferred implementation
Use a dedicated host-side one-shot notification dispatcher invoked immediately after successful approval creation, rather than a continuously polling Telegram daemon.

The dispatcher should:
- accept one `approval_id`;
- invoke `/usr/local/bin/philaios-telegram-approval-notifier <approval_id>` inside the existing Hermes container;
- never expose the Telegram bot token or Control API bearer token outside their existing runtime boundaries;
- write only bounded success/failure metadata to logs;
- be idempotent or deduplicated so the same approval is not intentionally delivered multiple times;
- have no access to `/v1/execute`, provider credentials, approval decision endpoints, or approval consumption logic.

## Activation gate
Before production activation:
- validate the dispatcher against a copied/stubbed approval ID path where possible;
- verify missing Hermes/notifier returns failure without mutating approval state;
- verify expired/non-pending approval returns fail-closed;
- verify no new provider/execution/approval-decision paths are introduced;
- verify current `general`-only execution allowlist remains unchanged;
- prepare rollback for any new systemd unit/hook.

## Production canary
Create exactly one fresh `general` approval. The automatic trigger must deliver Telegram without manual notifier invocation. Verify:
- Telegram message arrives;
- approval remains pending and unconsumed;
- execution audit count does not increase;
- no provider/execution call occurs;
- Mission Control mutation boundary remains `405`;
- production execution allowlist remains `general` only.

Phase 2.1J can close only after this automatic-delivery canary is GREEN.
