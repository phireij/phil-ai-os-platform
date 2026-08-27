# Phil AI OS Platform — Phase 2.1I Planning Contract

**Status:** CONTRACT DEFINED — PRODUCTION WRITER NOT AUTHORIZED  
**Date:** 2026-08-27

## Purpose

Define authoritative `PLANNED` lifecycle semantics without granting execution authority.

## Ownership

Control API is the authoritative coordinator. Hermes is an assignable worker. Mission Control remains read-only.

## `PLANNED` semantics

A `PLANNED` event is coordination evidence only. It means an explicit bounded plan reference has been recorded for an existing canonical task.

A valid planning record/event requires:

- existing canonical `task_id`;
- explicit `plan_ref` generated/accepted by the coordinator;
- source component = `control-api`;
- timestamp;
- previous lifecycle context when known.

`plan_ref` is an opaque identifier, not task text or prompt content.

## Proposed persistence

A future isolated candidate may add a coordinator-owned planning table:

```text
task_plans
- plan_ref TEXT PRIMARY KEY
- task_id TEXT NOT NULL
- created_at TEXT NOT NULL
- created_by TEXT NOT NULL
- plan_kind TEXT NOT NULL
- status TEXT NOT NULL
- supersedes_plan_ref TEXT NULL
```

Only safe metadata is stored. Plan body/prompt/provider response content is out of scope for Phase 2.1I.

A successful planning operation appends one `PLANNED` event to `task_lifecycle_events` with correlation/reference metadata pointing to `plan_ref`.

## Fail-closed rules

Planning MUST fail if:

1. `task_id` does not exist as a canonical task;
2. task is terminal (`SUCCEEDED`, `FAILED`, `DENIED`, `EXPIRED`, `CANCELLED`, `CLOSED`) according to authoritative lifecycle evidence;
3. `plan_ref` collides with an existing plan;
4. coordinator identity/source is not authoritative;
5. requested plan would alter task class, approval state, provider route, execution allowlist, or authority level.

## Supersession

Plans are append-only. Replanning creates a new `plan_ref` and may reference `supersedes_plan_ref`; existing plan rows are not rewritten.

## Authority invariants

`PLANNED` does NOT:

- approve a task;
- consume an approval;
- assign an agent;
- select a provider;
- trigger execution;
- change `general`-only production policy;
- increase any agent authority ceiling.

## Mission Control

Mission Control may display plan metadata read-only after production persistence exists. It must not expose plan bodies, prompts, provider responses, credentials, or mutation controls.

## Next gate

Validate the proposed planning persistence and fail-closed semantics on an isolated copy of the live SQLite database. GREEN isolated validation permits production-preflight design only; it does not authorize live activation.
