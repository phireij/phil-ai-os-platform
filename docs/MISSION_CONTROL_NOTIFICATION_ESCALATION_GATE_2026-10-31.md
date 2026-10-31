# Mission Control notification escalation gate

**Status:** blocked pending an owner-selected, independently operated
escalation procedure or destination.

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

## Required owner decision

Choose one of the following before escalation can become an acceptance gate:

1. A documented manual operator procedure that consumes only the
   identifier-only dead-letter/audit record; or
2. An independently operated automatic destination, with dedicated
   credentials, recipient scope, retry policy, privacy boundary, and a
   separately approved controlled acceptance.

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
