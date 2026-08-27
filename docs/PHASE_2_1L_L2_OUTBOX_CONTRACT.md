# Phase 2.1L L2 — Isolated Approval Notification Outbox Contract

Status: **ISOLATED CONTRACT / NO PRODUCTION ACTIVATION**

Date: 2026-08-27

## Purpose

Define the smallest additive durable notification reliability contract that can support approval sources beyond the Hermes Mission Control client without granting notification infrastructure any approval or execution authority.

## Durable outbox record

Proposed additive table: `approval_notification_outbox`

Required fields:

- `id` — integer primary key
- `event_id` — stable unique event identity
- `approval_id` — exact approval identity
- `task_id` — exact canonical task identity
- `event_type` — initially `approval_pending`
- `channel` — initially `telegram`
- `state` — `pending | leased | retry_wait | delivered | dead_letter`
- `attempt_count` — non-negative integer
- `next_attempt_at` — nullable retry eligibility time
- `lease_until` — nullable dispatcher lease expiry
- `created_at`
- `updated_at`
- `delivered_at` — nullable
- `last_error_code` — nullable bounded transport/error classification only

Unique constraint:

`UNIQUE(approval_id, event_type, channel)`

This is the primary duplicate-suppression boundary.

## Explicitly prohibited durable fields

The outbox must not persist:

- raw approval review-link tokens;
- Telegram bot tokens;
- Control API bearer tokens;
- provider credentials;
- arbitrary executable payloads;
- shell commands;
- approval decision instructions;
- provider/model override instructions.

The dispatcher receives only the durable correlation identity needed to resolve the current approval through governed Control API methods.

## Enqueue contract

For future activation, outbox intent must be inserted atomically with successful approval creation or in an equivalently durable transaction boundary.

The enqueue operation:

- creates zero or one outbox row for the exact approval/channel/event;
- never creates a second approval;
- never changes approval state;
- never issues a review link;
- never sends Telegram;
- never consumes approval;
- never executes the task.

If the duplicate key already exists, enqueue is idempotent and returns the existing intent rather than creating another row.

## Dispatcher contract

A dispatcher may:

1. claim one due `pending` or `retry_wait` row with a bounded lease;
2. resolve the approval using `approval_id`;
3. verify the approval is still relevant for notification;
4. request the secure review link through the existing Control API boundary at send time;
5. invoke the established Telegram transport;
6. record `delivered` or a bounded retry/dead-letter outcome.

A dispatcher may **not**:

- approve or deny;
- consume approval;
- call `/v1/execute`;
- alter routing or task class;
- change agent authority;
- create another approval;
- expose raw review tokens in durable outbox state.

## Retry contract

Retry applies only to notification delivery.

- Retry never repeats approval creation.
- Retry never changes approval decision state.
- Retry never invokes provider execution.
- Retry increments `attempt_count` on the same outbox row.
- Backoff is bounded.
- After a configured maximum attempt count, the row moves to `dead_letter` and requires operator visibility/intervention.
- A successful delivery becomes `delivered` and is not eligible for automatic resend.

## Approval relevance rule

Before sending, the dispatcher must re-read current approval state.

Minimum rule for initial implementation:

- send only for the intended approval event and when the approval is still review-relevant;
- do not send a fresh approval request after an approval has already been consumed, denied, or otherwise terminal;
- state mismatch must become an auditable non-delivery outcome, not an authority mutation.

The exact production relevance predicate must be frozen during L3 preflight.

## Migration / coexistence rule

The existing Hermes client notifier remains authoritative for current production behavior until the server-side path is independently validated.

Production activation must avoid dual delivery. A staged migration should separate:

1. durable enqueue activation;
2. dispatcher activation;
3. Hermes client auto-notify retirement or suppression after the server path is proven.

No cutover is authorized by this L2 contract.

## Isolated validation requirements

L2 validation must prove:

- unique-key duplicate suppression;
- one approval can create at most one Telegram `approval_pending` intent;
- retry reuses the same row;
- delivered rows are not automatically resent;
- no secret/token fields exist in schema;
- approval/task correlation is preserved;
- no approval or execution tables are required to change in the isolated test;
- no provider/network call is used.

`PHIL_AI_OS_PHASE_2_1L_L2_OUTBOX_CONTRACT_DEFINED`
