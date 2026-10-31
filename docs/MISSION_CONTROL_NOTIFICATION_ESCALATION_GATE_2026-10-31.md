# Mission Control notification escalation gate

**Status:** owner-selected manual escalation procedure. Automatic escalation
remains intentionally unconfigured.

## Verified current boundary

The dedicated Mission Control Telegram worker sends only identifier-only CEO
decision notifications. It is disabled by default, has no inbound Telegram
handling, and permits one retry after fifteen minutes. A second failure, or an
interrupted in-flight claim, becomes a durable `dead_letter` record with a
fixed safe failure category and an identifier-only audit event.

The current worker contains no automatic escalation route. That is
intentional: retrying the same failed Telegram path cannot establish delivery,
and a fallback that is not independently owned, configured, and tested could
silently widen the notification or authority boundary.

The local Telegram transport test suite passes. The broader encrypted-store
suite was not used as escalation acceptance in this review because the local
environment lacks its `cryptography` dependency; no dependency installation,
secret read, or transport request occurred.

## Approved manual procedure

When a new Mission Control notification reaches `dead_letter`, the designated
operator must:

1. Read the existing identifier-only outbox/audit record and confirm its
   `notification_id`, `decision_id`, `proposal_id`, safe failure category, and
   recorded timestamp. Do not inspect or export message, proposal, decision,
   conversation, or credential content.
2. Contact the owner through an already approved, user-operated human channel.
   This procedure configures no address, recipient, bot, API client, or
   automated delivery destination.
3. Communicate only the durable identifiers and the fact that the notification
   requires owner attention. Do not include rationale, task contents, secrets,
   a copied Telegram body, or an interpretation of the failure cause.
4. Preserve the existing `dead_letter` and audit records. Do not change the
   delivery state, retry the notification, or create a second notification as
   part of manual escalation.
5. Treat any later owner acknowledgement as human process evidence only. It
   does not authorize provider dispatch, task assignment, task execution, or
   any other Mission Control mutation.

This procedure is incident-driven; it does not authorize a synthetic
dead-letter or test message. An independently operated automatic destination
remains a future, separately approved option.

## Prohibited assumptions

- Do not retry a dead letter indefinitely or replay a prior acceptance
  notification.
- Do not reuse the failed Telegram transport as evidence of escalation.
- Do not use Hermes, its credentials, approvals, routes, or workloads.
- Do not include decision rationale, conversation content, protected secrets,
  or recipient identifiers in escalation evidence.
- Do not send a new test message without separate owner approval.

## Non-actions

This gate does not read Telegram credentials, configure a destination, send a
message, alter the CEO session, deploy a worker, or grant authority.
