# Phil AI OS Platform — Phase 2.2 A5 Bounded Second-Worker Activation Gate

**Phase:** 2.2 A5 — Bounded Second-Worker Registration  
**Status:** BLOCKED — REQUIRES A4 GREEN + EXPLICIT CEO ACTIVATION AUTHORIZATION  
**Prepared:** 2026-08-28  
**Production activation:** NOT AUTHORIZED

## Purpose

Prepare the smallest reversible second-worker registration step without activating execution, assignment, automatic delegation, or provider access.

This document is preparatory engineering only. Creating this gate does not authorize the production mutation.

## Candidate bounded identity

Subject to A4 GREEN evidence, the proposed first second-worker registry record is:

```text
agent_id: specialist-worker-01
display_name: Specialist Worker 01
role: specialist_worker
authority_ceiling: L1
enabled: false
assignable: false
source_component: phase-2.2-a5-controlled-registration
```

Rationale:

- L1 is below Hermes L3 and minimizes privilege.
- `enabled=false` prevents worker eligibility.
- `assignable=false` prevents assignment.
- Registry identity alone grants no execution authority.
- No provider credential or runtime service is introduced.
- No new execution class is introduced.

## Exact A5 authority boundary

If separately approved, A5 may do only the minimum registration operation and verification necessary to prove a second durable identity can coexist safely with Hermes.

A5 MUST NOT:

- enable or make the candidate assignable;
- append an `ASSIGNED` event to the candidate;
- create or accept a handoff;
- create a task for the candidate;
- create/consume/modify an approval;
- execute a provider call;
- add credentials;
- start a new worker runtime/container;
- widen the `general` execution allowlist;
- change Hermes L3 authority;
- add automatic assignment, retry, reroute, delegation, or execution;
- add Mission Control mutation endpoints.

## Required pre-activation evidence

Before A5 activation:

1. A1 GREEN.
2. A2 GREEN.
3. A3 GREEN.
4. A4 GREEN.
5. Control API health/readiness GREEN.
6. Mission Control remains read-only.
7. Hermes remains the only current enabled/assignable L3 worker.
8. Execution allowlist remains exactly `general`.
9. Monitor, backup timer, and backup self-heal are active.
10. Fresh pre-change database backup is verified.
11. Exact production mutation path is documented and bounded.
12. Rollback operation is prepared.
13. Explicit CEO activation authorization is recorded.

## Controlled activation verification

A successful A5 registration must prove:

- registry row count increases by exactly one;
- Hermes registry row remains byte-for-byte/logically unchanged;
- candidate is exactly L1, disabled, and non-assignable;
- no lifecycle row is added;
- no task plan row is added;
- no approval row is changed;
- no execution-audit row is added by activation;
- no handoff row is created;
- Mission Control remains read-only;
- production allowlist remains `general` only;
- no provider or execution call occurs;
- monitoring/backups remain active.

## Rollback boundary

If any invariant fails:

1. stop before any further Phase 2.2 action;
2. restore the pre-change database backup or remove only the candidate registry row if and only if evidence proves no downstream reference exists;
3. verify Hermes remains the sole registered/assignable production worker;
4. verify database `quick_check=ok`;
5. verify Control API/Mission Control/monitoring/backups GREEN;
6. record rollback evidence.

## After A5

A5 success still does not authorize handoff. The candidate remains disabled and non-assignable. Any transition to enabled/assignable state and any A6 controlled handoff must be separately bounded by the Phase 2.2 gate and explicit activation authority appropriate to that production change.

## Approval boundary

**Do not execute A5 until the CEO explicitly authorizes this production registration after A4 is GREEN.**
