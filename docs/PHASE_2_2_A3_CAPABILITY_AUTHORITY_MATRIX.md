# Phil AI OS Platform — Phase 2.2 A3 Capability / Authority Matrix v1

**Phase:** 2.2 A3 — Capability / Authority Matrix  
**Status:** DESIGN MATRIX — NO PRODUCTION AUTHORITY EXPANSION  
**Date:** 2026-08-28

## Purpose

Define who may observe, plan, request handoff, authorize handoff, accept work, execute, escalate, and close work while preserving the existing Phase 2.1O governance boundary.

This matrix describes allowed semantics. It does not register a new production agent, add a route, widen the execution allowlist, or grant runtime credentials.

## Capability vocabulary

- **observe** — read durable non-secret operational evidence within scope.
- **plan** — create/propose bounded planning metadata; does not authorize execution.
- **request handoff** — ask the coordinator to evaluate a transfer; does not transfer ownership.
- **authorize handoff** — provide the human/governance authorization required for a cross-agent transfer.
- **accept work** — explicitly accept an already-authorized handoff after all contract checks; acceptance changes coordination ownership only.
- **execute** — invoke the existing governed execution boundary; separate approval/policy requirements still apply.
- **escalate** — request higher authority/human intervention; never self-grant higher authority.
- **close** — explicitly mark governed work closed only when a future closure policy and sufficient terminal evidence authorize it.

## Role matrix

| Role / component | Observe | Plan | Request handoff | Authorize handoff | Accept work | Execute | Escalate | Close |
|---|---|---|---|---|---|---|---|---|
| Human operator / CEO | YES | YES | YES | YES | N/A | Via governed operator paths only | YES | YES, when closure evidence/policy permits |
| CTO Office advisory role | YES | PROPOSE ONLY | PROPOSE ONLY | NO | NO | NO | REQUEST ONLY | NO |
| Control API coordinator | YES | PERSIST ONLY WHEN AUTHORIZED | EVALUATE/PERSIST ONLY | NO SELF-AUTHORIZATION | COMMIT ACCEPTANCE ONLY WHEN AUTHORIZED | NO PROVIDER EXECUTION BY COORDINATION ROUTE | CONTAIN / SURFACE | PERSIST ONLY WHEN SEPARATELY AUTHORIZED |
| Hermes operational worker, current L3 | ASSIGNED SCOPE | BOUNDED | REQUEST ONLY | NO | YES only under explicit validated handoff | YES only through existing governed `general` execution boundary | REQUEST ONLY | NO automatic/self closure |
| Future specialist worker, initial bounded profile | OWN ASSIGNED SCOPE | BOUNDED | REQUEST ONLY | NO | YES only under explicit validated handoff | **NO at initial Phase 2.2 registration** | REQUEST ONLY | NO |
| Mission Control | YES / READ ONLY | NO | NO | NO | NO | NO | NO mutation | NO |

## Current-production interpretation

At the start of Phase 2.2:

- Hermes is the only registered/assignable worker and is capped at L3.
- No future specialist worker is registered.
- Therefore no real cross-agent production handoff is currently possible or authorized.
- Mission Control remains read-only.
- Production execution remains `general` only.

## Non-escalation rules

1. Registry `authority_ceiling` is a ceiling, never a grant.
2. A normal handoff cannot raise the task's effective authority.
3. A source worker cannot obtain higher authority indirectly by handing work to a higher-ceiling target.
4. `required_authority` for a normal handoff must fit both source and target ceilings.
5. Work that truly requires authority above the source ceiling is an **escalation request**, not a handoff.
6. Escalation requires a separate human/governance decision and is not automatically transformed into assignment or execution.
7. No role may approve its own execution request where human approval policy requires separation.

## Separation of powers

### Request is not authorization

A worker or advisory role may request a handoff, but the request creates no ownership change and grants no permission.

### Authorization is not acceptance

Human/operator authorization allows the coordinator to evaluate acceptance. It does not itself append a target assignment if identity, readiness, authority, task class, expiry, or correlation checks fail.

### Acceptance is not execution

An accepted handoff appends operational ownership evidence only. It does not consume execution approval, call a provider, or permit a task class outside the current allowlist.

### Readiness is not assignment

`ready` is advisory evidence for explicit consideration only. `busy`, `stale`, `unassignable`, or `indeterminate` never trigger automatic reroute; `ready` never triggers automatic assignment.

## Initial future-specialist profile for A5 planning

If A1–A4 are GREEN and the CEO later gives explicit activation authorization, the safest first second-worker profile is:

- new stable `agent_id` defined by the activation gate;
- role: `specialist_worker`;
- authority ceiling: **L1 maximum initially**;
- enabled: true only after bounded registration validation;
- assignable: preferably false at registration, then separately enabled only for a controlled handoff canary if authorized;
- provider execution capability: none;
- direct provider credentials: none;
- automatic assignment/retry/reroute: none;
- task class: no independent production execution class grant;
- Mission Control: read-only visibility only.

This is a planning profile, not authorization to create the worker.

## Approval policy for initial cross-agent handoff

Until a later policy gate proves safe automation:

- every production cross-agent handoff requires explicit human/operator authorization;
- the requesting worker cannot authorize its own handoff;
- the target cannot treat its own readiness/acceptance as authorization;
- handoff authorization does not satisfy execution approval;
- execution approval does not silently authorize handoff;
- ambiguous authorization evidence fails closed.

## Forbidden capability combinations

No non-human agent may have any of these combinations under Phase 2.2 foundation policy:

- request + self-authorize handoff;
- accept + auto-execute;
- readiness + auto-assign;
- failure/staleness + auto-reroute;
- assignment + approval bypass;
- higher target ceiling + delegated privilege escalation;
- Mission Control read access + mutation authority;
- direct provider credentials + bypass of Control API execution governance.

## A3 acceptance criteria

A3 is GREEN when static validation proves that the matrix:

1. gives Mission Control no mutation capability;
2. gives CTO Office no production execution or approval authority;
3. gives current Hermes no automatic handoff/retry/reroute/closure;
4. gives the initial future-specialist profile no provider execution;
5. requires human authorization for initial production cross-agent handoff;
6. keeps execution approval separate from handoff authorization;
7. prevents normal handoff from exceeding either source or target ceiling;
8. preserves `general` as the only current production execution class;
9. introduces no new production identity or credential.

## Production boundary

This matrix authorizes policy design and isolated/static validation only. Any actual second-worker registration or cross-agent production handoff remains blocked until A5 and explicit activation authorization.
