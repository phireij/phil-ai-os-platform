# Phase 2.1E — Durable Correlation Decision

Status: **DECIDED — READ-MODEL FIRST / NO DATABASE MIGRATION YET**
Date: 2026-08-27
Program: Phil AI OS Platform

## Evidence

Read-only durable-state discovery confirmed the authoritative persistence layer currently contains:

- `approval_requests` — 45 rows
- `execution_audit` — 34 rows

`approval_requests` carries immutable `approval_id` and approval lifecycle/consumption metadata.

`execution_audit` carries immutable audit row `id` plus `approval_id`, execution route/model/outcome metadata, and timestamps.

Neither durable table currently carries `task_id` or `canonical_task_id`.

Therefore durable approval-to-execution correlation already exists through `approval_id`, while canonical task identity is not yet persisted.

## Decision

Phase 2.1E will improve Mission Control observability **without changing the database schema or Control API writers**.

The read model may expose a new sanitized durable correlation projection keyed by `approval_id`.

This projection is not a canonical task and must not be represented as a `task_id`.

Canonical `tasks` remain restricted to records containing a genuine authoritative `task_id` or temporary compatibility alias `canonical_task_id`.

## Durable Link Projection

A durable approval/execution link may include only non-secret fields required for operator observability.

Approval-side fields allowed:

- `approval_id`
- `created_at`
- `updated_at`
- `expires_at`
- `state`
- `source`
- `requester`
- `task_class`
- `requested_by`
- `decision_by`
- `decision_at`
- `consumed_at`
- `consumed_by`

Execution-audit fields allowed:

- `id`
- `occurred_at`
- `source`
- `task_class`
- `provider_id`
- `model_id`
- `route_path`
- `compatibility_pass`
- `execution_mode`
- `outcome`
- `approval_id`

The read model must not expose:

- `task_text`
- `decision_note`
- `link_token_hash`
- approval review tokens
- execution `detail`
- provider response payloads
- credentials or secret material

## Correlation Semantics

The projection key type is explicitly:

`correlation_key_type = approval_id`

It represents durable approval-to-execution linkage, not canonical task identity.

A link may contain zero, one, or multiple execution-audit records for the same approval ID. Replay/negative-path audit entries remain separate audit records and must not be collapsed into a fabricated task outcome.

## Why No Migration Yet

Adding `task_id` to durable writers would modify approval creation, approval consumption, and execution-audit persistence semantics. That is unnecessary to gain immediate operator visibility because `approval_id` already provides authoritative durable linkage.

A future canonical task persistence migration may be considered only after:

1. a writer/migration contract is defined,
2. backup-copy migration is validated,
3. rollback is proven,
4. compatibility with approval consumption/replay rejection is proven,
5. a separate production mutation gate is approved.

No historical row may be assigned a fabricated task ID.

## Safety Boundary

This decision does not:

- alter any SQLite schema
- change any persisted row
- create/consume/decide an approval
- invoke provider execution
- widen the `general` allowlist
- alter routing
- add browser mutation controls
- expand agent authority

Marker: `PHIL_AI_OS_PHASE_2_1E_DURABLE_CORRELATION_READ_MODEL_FIRST_DECISION_DEFINED`
