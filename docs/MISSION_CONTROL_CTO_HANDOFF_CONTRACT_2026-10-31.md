# Mission Control CTO task-handoff contract

**Status:** offline-safe implementation checkpoint

## Purpose

This contract begins the missing CEO-to-CTO/agent loop identified by the
Mission Control program charter. It creates an encrypted, owner-bound,
idempotent handoff record only after a durable CEO decision has approved the
underlying task proposal and that decision has not expired.

## Current behavior

The CEO session may create and list a handoff for an approved proposal. The
record contains only correlation identifiers and the state
`awaiting_connector`. Its audit event is identifier-only. The handoff record
does not contain an executor endpoint, credential, token, task dispatch,
result, execution permission, mutation permission, or network side effect.

The API is protected by the existing authenticated CEO session, origin/CSRF
checks, owner binding, encrypted snapshot persistence, bounded request body,
and idempotency checks. A duplicate handoff for the same proposal is rejected;
an idempotent replay returns the original record.

The encrypted store also defines internal-only packet and result methods for a
future connector. They have no HTTP route or default identity. A future adapter
must independently verify a CTO token, inject that verified subject, and match
it exactly against a protected expected subject before it can read one bounded
task packet or record one result. Result text and evidence references stay
encrypted and are omitted from the identifier-only audit timeline. A result is
not execution evidence and cannot authorize a mutation.

## Not yet implemented or authorized

The following remain separate gates and must not be inferred from this
checkpoint:

1. A verified CTO/agent connector identity and its least-privilege scope.
2. A real connector retrieval path, acknowledgement, and result callback using
   the independently verified identity boundary.
3. Result presentation to the CEO through a separately reviewed session/UI
   path.
4. Any task dispatch, automatic execution, retry, external mutation, or
   provider call.
5. Deployment of a session image containing this change and its associated
   integrated acceptance/release evidence.

The read-only MC-021 connector work remains a prerequisite for a future CTO
transport. This contract intentionally makes no claim that the connector is
running or that a CTO has received a task.
