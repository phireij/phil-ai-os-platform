# Phil AI OS Platform — Phase 2.1I Task Coordinator, Assignment & Planning Model

**Status:** OPEN — DISCOVERY / CONTRACT FIRST  
**Date:** 2026-08-27

## Objective

Define the authoritative component and persistence contract for task coordination so `ASSIGNED` and `PLANNED` can become durable lifecycle events without increasing execution authority.

## Non-negotiable authority boundary

Assignment and planning are coordination metadata only. They MUST NOT:

- increase an agent authority level;
- expand the production task-class allowlist;
- authorize or initiate provider execution;
- bypass human approval or approval consumption;
- change routing/provider policy;
- create a second Mission Control authority path.

Mission Control remains read-only.

## Discovery questions

1. Which existing component can authoritatively own task coordination: Control API, Hermes gateway, or a separate bounded coordinator?
2. Which durable identity proves the target task (`task_id`) and which identity proves the assigned agent?
3. Where can planning be persisted without embedding sensitive task text or model output into the operator read model?
4. How does the coordinator fail closed if an agent identity is missing, unknown, unavailable, or outside policy?
5. How are reassignment and replanning represented append-only without rewriting lifecycle history?
6. How do `ASSIGNED` and `PLANNED` remain distinct from `AUTHORIZED` and `EXECUTING`?

## Initial design preference

Prefer a bounded coordinator contract over making Mission Control a writer.

The coordinator should append explicit lifecycle events to the existing `task_lifecycle_events` ledger:

- `ASSIGNED` only after explicit coordinator selection of a known agent identity;
- `PLANNED` only after a durable plan reference/summary exists;
- reassignment or replanning becomes a later append-only event;
- an assignment alone never implies approval or execution authorization.

## Phase 2.1I entry baseline

Phase 2.1H closed GREEN with:

- Control API `0.20.2-phase21h`;
- append-only lifecycle ledger active;
- bounded lifecycle writer for `RECEIVED`, `CLASSIFIED`, `APPROVAL_PENDING`, and `AUDITED`;
- Mission Control `2.1h.v1` read-only ledger visibility;
- agent assignment explicit-event-only;
- production allowlist still `general` only.

## First gate

Run read-only ownership/interface discovery. No coordinator writer, schema change, assignment event, planning event, provider call, execution call, or approval mutation is authorized by this document.
