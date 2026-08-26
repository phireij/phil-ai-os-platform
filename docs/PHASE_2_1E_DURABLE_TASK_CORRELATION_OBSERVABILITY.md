# Phase 2.1E — Durable Task Correlation & Mission Control Observability

Status: **STARTED — READ-ONLY DISCOVERY / CONTRACT FIRST**
Date: 2026-08-27
Program: Phil AI OS Platform

## Purpose

Phase 2.1E closes the remaining durable-correlation gap identified at Phase 2.1D closure: Mission Control can consume a canonical `task_id` when one is present, but the current durable approval/execution persistence layer has not yet been proven to carry one end-to-end.

This increment begins with read-only discovery against the authoritative Control API SQLite state and live implementation. No execution-authority expansion is authorized.

## Primary Questions

1. Which durable tables currently carry approval, execution, and audit state?
2. Which columns can already correlate approval requests to execution audit records?
3. Is any canonical task identifier already present under another field name?
4. Where is the narrowest future write boundary for adding `task_id` without changing approval or execution semantics?
5. Can Mission Control improve historical/read-only correlation before any persistence mutation is required?

## Discovery Boundary

Phase 2.1E discovery may inspect:

- SQLite table names
- table column names and types
- indexes and foreign-key declarations
- row counts
- presence/absence of candidate correlation columns
- Control API function signatures/source regions relevant to approval creation, approval consumption, routed execution, and execution audit persistence

Discovery must not print task text, provider responses, credential values, approval review tokens, or other sensitive row contents.

## Safety Constraints

Phase 2.1E must not:

- widen `PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=general`
- change approval state
- consume or create an approval
- invoke a provider
- invoke governed execution
- change provider/model routing
- add browser mutation controls
- weaken BasicAuth, monitoring, backups, or self-heal
- create specialist-agent production authority
- create autonomous delegation authority

## Decision Rule

If durable correlation can be improved entirely in the read model using existing authoritative identifiers, prefer that approach.

If a new durable `task_id` column/write path is required, Phase 2.1E must first define a migration/write contract and validate backup/rollback compatibility before any production schema or writer mutation.

Historical rows must never receive fabricated task IDs.

## Planned Sequence

1. Durable schema and implementation discovery — read-only.
2. Correlation-gap result and field mapping.
3. Decide read-model-only improvement vs. bounded persistence change.
4. Define compatibility/migration contract if persistence is required.
5. Validate on backup/copy before production mutation.
6. Update Mission Control read model only after authoritative linkage is proven.
7. Production read-only canary and closure gate.

## GREEN Exit Criteria

Phase 2.1E may close GREEN only when:

- durable approval/execution/audit correlation sources are documented
- canonical task-correlation strategy is explicit
- no historical task ID is fabricated
- Mission Control can represent the strongest authoritative correlation available
- any required persistence migration is separately validated with rollback
- existing approval consumption semantics remain unchanged
- browser remains read-only
- production allowlist remains `general` only
- monitoring, backups, and self-heal remain active
- no uncontrolled provider or execution path is introduced

**Phase 2.1E is authorized to begin read-only. No authority expansion is authorized.**
