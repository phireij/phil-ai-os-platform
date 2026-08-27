# Phase 2.1F — Canonical Task ID Persistence Design & Validation

Status: **STARTED — READ-ONLY DISCOVERY / DESIGN**
Date: 2026-08-27
Program: Phil AI OS Platform

## Objective

Define and validate the safest way to introduce a genuine canonical `task_id` across request → approval → execution → audit without expanding execution authority, weakening approvals, rewriting history, or creating a second control plane.

## Current Proven Baseline

Phase 2.1E established:
- durable approvals live in `approval_requests`
- durable execution history lives in `execution_audit`
- authoritative durable approval→execution linkage already uses `approval_id`
- `task_id` / `canonical_task_id` is not currently persisted in those tables
- Mission Control schema `2.1e.v1` exposes durable `approval_id` linkage without fabricating canonical tasks
- production allowlist remains `general` only
- browser Mission Control remains read-only

## Phase 2.1F Safety Rules

1. Discovery and design first; no schema mutation in the first step.
2. No backfilling or fabrication of historical task IDs.
3. Existing `approval_id` semantics remain intact.
4. Canonical task identity must supplement, not replace, approval/execution IDs.
5. Task identity must not increase authority or bypass approval requirements.
6. No provider/model routing change.
7. No specialist-agent production authority expansion.
8. No browser mutation controls.
9. Any future persistence migration requires backup/restore evidence and a separately gated canary.
10. Legacy rows without canonical task identity remain explicitly legacy/partial.

## Discovery Questions

Phase 2.1F must map:
- every Control API function/route that creates approval requests
- every execution entry point that consumes an approval
- every `execution_audit` insert path
- Mission Control/Hermes approval-request client payloads
- whether one canonical ID can be generated once at task intake and propagated unchanged
- compatibility behavior when `task_id` is absent
- minimum SQLite migration needed, if any
- index/uniqueness requirements
- rollback implications

## Candidate Contract

Preferred future shape, subject to discovery:

- `task_id`: immutable opaque identifier generated once at canonical task intake
- `approval_id`: approval instance identifier, unchanged
- `execution_audit.id`: execution audit row identifier, unchanged
- approval rows may carry nullable `task_id`
- execution audit rows may carry nullable `task_id`
- new writes propagate the same `task_id` end-to-end when available
- old rows remain null and are never synthesized
- `approval_id` remains the authoritative compatibility link for historical data

## Exit Criteria

Phase 2.1F can be GREEN only after:
- write-path/source map is complete
- canonical ID generation boundary is explicit
- compatibility contract is explicit
- migration design is additive and reversible
- no historical fabrication is required
- backup/restore and rollback plan is defined
- no authority, provider, approval, or execution-policy expansion is introduced

No persistence migration is authorized by this document alone.
