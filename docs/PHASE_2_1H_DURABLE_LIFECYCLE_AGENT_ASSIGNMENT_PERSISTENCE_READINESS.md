# Phil AI OS Platform — Phase 2.1H Durable Lifecycle & Agent Assignment Persistence Readiness

**Status:** STARTED — CONTRACT / READ-ONLY DISCOVERY FIRST  
**Date:** 2026-08-27

## Objective

Determine whether Phil AI OS should introduce a dedicated durable lifecycle and agent-assignment persistence model for new canonical tasks, without widening execution authority or converting observational metadata into assignment authority.

## Starting baseline

Phase 2.1G closed GREEN with:

- Control API image `phil-ai-os/control-api:0.20.1-phase21f`
- Mission Control read-model schema `2.1g.v1`
- dashboard badge `READ ONLY · Phase 2.1G`
- canonical `task_id` persistence available for new records
- evidence-based lifecycle visibility for the durable subset
- agent assignment explicitly unavailable from authoritative sources
- unsupported durable stages: `ASSIGNED`, `PLANNED`, `POLICY_CHECK`, `EXECUTING`, `CLOSED`
- production allowlist `general` only
- direct provider bypass prohibited
- human approval authoritative
- Mission Control browser mutation blocked

## Non-negotiable constraints

1. Read-only discovery before any schema or application mutation.
2. No conversion of `requester`, `requested_by`, `source`, or `consumed_by` into `assigned_agent_id` unless an explicit assignment contract proves that meaning.
3. Assignment cannot increase an agent's authority level or allowed task classes.
4. Lifecycle events must be append-only or otherwise durably auditable if introduced.
5. Existing historical rows remain valid; no fabricated backfill.
6. Existing `approval_id` and `task_id` identities remain immutable.
7. Human approval semantics, one-time approval consumption, provider routing, and execution allowlists remain unchanged unless separately gated.
8. Mission Control remains read-only during this increment unless a later explicit gate authorizes otherwise.
9. Any production persistence migration requires isolated-copy validation, backup, rollback, and canary.

## Discovery questions

- Is a separate `task_lifecycle_events` table preferable to adding lifecycle columns to approval/execution tables?
- What is the minimal durable assignment record needed to prove `ASSIGNED` without implying execution authorization?
- Which component is allowed to create an assignment record?
- How should assignment handoff be represented without authority escalation?
- Which lifecycle events can be emitted synchronously from existing Control API functions?
- Which events require a distinct task coordinator or future agent runtime component?
- How should `POLICY_CHECK`, `EXECUTING`, and `CLOSED` be defined so they are not inferred from unrelated timestamps?
- What rollback and compatibility guarantees are required for legacy records?

## Initial design bias

Prefer an append-only lifecycle event model for new canonical tasks over overloading approval state, provided discovery confirms it can remain bounded and backward compatible.

A possible future event shape may include only non-secret metadata such as:

- event ID
- task ID
- lifecycle stage
- occurred-at timestamp
- actor/agent ID when authoritative
- source component
- prior stage when known
- reason/status code safe for audit

This is a design hypothesis only, not an approved schema.

## Phase 2.1H GREEN exit criteria

Phase 2.1H may close GREEN when:

- lifecycle/assignment persistence requirements are defined;
- authoritative writer ownership is defined;
- assignment semantics cannot increase authority;
- append-only/audit semantics are defined;
- legacy compatibility is defined;
- isolated migration/application validation is GREEN if implementation is proposed;
- Mission Control can distinguish authoritative lifecycle/assignment events from unavailable data;
- production `general`-only policy remains unchanged;
- no provider bypass or uncontrolled execution path is introduced;
- backups, monitoring, self-heal, and rollback remain healthy.

No production mutation is authorized merely by this document.
