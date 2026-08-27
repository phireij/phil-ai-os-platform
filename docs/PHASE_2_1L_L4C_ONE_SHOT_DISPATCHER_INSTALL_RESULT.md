# Phase 2.1L L4C — One-Shot Dispatcher Installation Result

Status: **GREEN**

Date: 2026-08-27

## Result

The bounded server-side approval-notification dispatcher is installed at:

`/usr/local/sbin/philaios-approval-notification-dispatcher`

It is intentionally **not scheduled** and therefore cannot run autonomously yet.

The dispatcher:

- atomically leases one eligible outbox row;
- preserves exact `approval_id` / `task_id` correlation;
- invokes the established Hermes Telegram notifier with only the `approval_id`;
- marks the same durable row `delivered` only on confirmed Telegram success;
- on failure, reuses the same row as `retry_wait` and eventually `dead_letter` after a bounded attempt count;
- never creates an approval request;
- never approves, denies, consumes, routes, or executes a task;
- never invokes a model/provider;
- does not persist Telegram or review-link tokens in the outbox.

Installation evidence:

- prior dispatcher backup: none (new install);
- outbox rows before canary: `0`;
- dispatcher installed: true;
- dispatcher scheduled: false;
- no notification sent during installation;
- no approval mutation;
- no execution or provider call.

## L5 canary method

For exactly one L5 request, the genuine Hermes Mission Control client will be invoked with `PHIL_AI_OS_AUTO_NOTIFY_APPROVALS=0`. This suppresses only that invocation's legacy direct sender while leaving the existing client behavior unchanged globally. The new outbox trigger will enqueue the notification, then the one-shot server dispatcher will be invoked exactly once.

`PHIL_AI_OS_PHASE_2_1L_L4C_GREEN`
