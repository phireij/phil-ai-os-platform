# Phil AI OS Platform — Phase 2.2 A6 Preparation Checkpoint

**Date:** 2026-08-28  
**Status:** PREPARATION GREEN / A6.4 APPROVAL REQUIRED

## Gate status

| Gate | Status | Production mutation |
|---|---|---|
| A6.1 Specialist presence discovery | GREEN | none |
| A6.2 Specialist presence contract | GREEN | none |
| A6.3 Specialist presence preflight | GREEN | none |
| A6.4 Specialist presence activation | BLOCKED — CEO approval required | not executed |
| A6.5 Handoff persistence/writer isolated validation | GREEN | none |
| A6.6 Handoff persistence/writer production preflight | GREEN | none |
| A6.7 Inert handoff writer activation | BLOCKED — later CEO approval | not executed |
| A6.8 Eligibility + one handoff canary | BLOCKED — later CEO approval | not executed |

## Current production state

- `hermes`: L3, enabled, assignable.
- `specialist-worker-01`: L1, disabled, non-assignable.
- specialist assignment references: zero.
- specialist presence runtime: not activated.
- specialist provider credentials: none.
- production `task_handoffs` table: absent.
- production handoff writer routes: absent.
- production execution allowlist: `general` only.
- Mission Control remains read-only.

## A6.4 prepared activation

The prepared A6.4 design introduces only a signed presence primitive:

- dedicated Ed25519 specialist presence identity;
- local Control API health/readiness round-trip;
- dedicated systemd service/timer;
- dedicated specialist evidence file;
- no Control API bearer token;
- no provider credentials;
- no execution capability;
- no registry eligibility change;
- rollback containment prepared.

A6.4 cannot assign work because the specialist remains disabled/non-assignable.

## A6.5 / A6.6 handoff preparation

A6.5 isolated validation proved request/accept/reject, human-authorization separation, atomic accepted assignment, replay protection, expiry/rejection, conflict containment, readiness/authority enforcement, and execution-approval immutability.

A6.6 production preflight discovered the live coordinator integration anchors:

- Control API source: `/app/app.py`
- existing routes: `/v1/tasks/assign`, `/v1/tasks/plan`
- current Control API image: `phil-ai-os/control-api:0.20.3-phase21i`
- existing production handoff code: none
- candidate `task_handoffs` schema: additive and compatible on a copied live DB
- A6.7 requires no new service, registry change, handoff row, or assignment row at activation

## Next required decision

The next sequential production gate is **A6.4 Specialist Presence Activation**. It requires explicit CEO approval before the prepared workflow may be activated.
