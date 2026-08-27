# Phase 2.1H Controlled Production Canary Contract

Status: READY FOR CONTROLLED CANARY
Date: 2026-08-27

## Scope
Activate the validated append-only lifecycle ledger and bounded lifecycle writer in production without creating test approvals or test executions.

## Candidate
- Base image: `phil-ai-os/control-api:0.20.1-phase21f`
- Candidate image: `phil-ai-os/control-api:0.20.2-phase21h`
- New table: `task_lifecycle_events`
- UPDATE and DELETE blocked by database triggers
- Writer events: `RECEIVED`, `CLASSIFIED`, `APPROVAL_PENDING`, `AUDITED`
- Agent assignment remains unavailable

## Required invariants
- Production task-class allowlist remains `general` only.
- Existing approval and execution rows remain unchanged.
- Existing task IDs remain unchanged.
- Mission Control remains read-only.
- Operator authentication remains required.
- Browser POST, PUT, PATCH, and DELETE remain blocked.
- Monitor, backup, self-heal, and operator services remain active.
- No test approval or execution is created during activation.

## Rollback
Before any mutation, save the full Compose file and a verified SQLite backup. If any post-activation check fails, restore both backups and recreate only Control API.

## Activation sequence
1. Recheck the current Phase 2.1H baseline.
2. Save rollback snapshots.
3. Build the candidate child image from the current production image.
4. Apply the validated lifecycle-ledger schema change.
5. Change only the Control API image reference.
6. Recreate only Control API.
7. Verify health and readiness.
8. Verify image, app hash, table, indexes, append-only triggers, zero lifecycle rows, and unchanged existing row counts.
9. Verify the `general`-only boundary and recovery services.
10. Verify public route statuses return to the exact pre-activation values within a bounded convergence window.
11. Verify browser mutation methods remain blocked.

A GREEN canary establishes lifecycle persistence for future genuine canonical tasks. It does not add agent assignment or new lifecycle stages beyond the validated writer slice.
