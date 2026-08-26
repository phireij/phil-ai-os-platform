# Phase 2.1D — Canonical Task / Agent Lifecycle & Mission Control Observability

Status: **STARTED — READ-ONLY / CONTRACT FIRST**
Date: 2026-08-27
Program: Phil AI OS Platform

## Purpose

Close the remaining Mission Control observability gaps revealed by the Phase 2.1C production operator dashboard without expanding execution authority or creating a new control path.

Phase 2.1D remains read-only and contract-first.

## Carried-Forward Gaps

The Phase 2.1C browser dashboard exposed three known data-quality gaps:

1. `execution_enforcement_mode` is unavailable in current read sources.
2. `execution_enforcement_scope` is unavailable in current read sources.
3. Canonical `task_id` correlation is not yet available; historical approval/execution correlations remain legacy or partial.

These are the primary Phase 2.1D targets.

## Canonical Lifecycle

The existing Phase 2.1 operating model remains authoritative:

`RECEIVED -> CLASSIFIED -> ASSIGNED -> PLANNED -> POLICY_CHECK -> [APPROVAL_PENDING] -> AUTHORIZED -> EXECUTING -> {SUCCEEDED | FAILED | BLOCKED | CANCELLED} -> AUDITED -> CLOSED`

Exception states remain:

`DENIED`, `EXPIRED`, `REJECTED`, `AMBIGUOUS`, `CONTAINED`.

A handoff must never increase authority.

## Phase 2.1D Objectives

### 1. Canonical task identity

Define a durable, non-secret task identifier that can correlate:

- originating request
- task classification
- assigned agent
- approval request and decision
- governed execution attempt
- execution outcome
- audit record
- closure state

The identifier must support legacy/partial records without rewriting history.

### 2. Agent lifecycle observability

Mission Control should be able to show, read-only:

- agent identity
- declared role
- maximum authority level
- current task ownership
- handoff source/target when applicable
- lifecycle state
- last meaningful state transition
- degraded/blocked status

Declared authority remains bounded by the Phase 2.1 operating model.

### 3. Execution governance visibility

Expose authoritative read-only values for:

- execution enforcement mode
- execution enforcement scope
- production allowed task classes
- kill-switch state
- direct-provider-bypass state

No setting changes are introduced in this increment.

### 4. Approval-to-execution linkage

Preserve the durable Phase 1 approval-consumption contract while adding canonical correlation:

- approval ID remains immutable
- consumption remains one-time
- replay remains rejected
- execution audit remains linked
- canonical task ID supplements rather than replaces approval/execution IDs

### 5. Operator dashboard data quality

Reduce current `unknown` / `legacy` states only where authoritative backend evidence exists.

The dashboard must continue to distinguish:

- known authoritative values
- inferred/derived values
- unavailable values
- legacy/partial correlation

No silent guessing or synthetic completion is permitted.

## Hard Safety Constraints

Phase 2.1D must not:

- widen the `general` production allowlist
- enable specialist-agent production authority
- change provider/model routing
- expose provider, Control API, Telegram, SSH, or approval-review credentials
- add browser mutation controls
- bypass Telegram/Control API approvals
- permit self-approval
- retry provider execution automatically
- create autonomous multi-agent delegation authority
- weaken backup/monitor/self-heal controls

## Planned Implementation Sequence

1. Read-only discovery of authoritative enforcement-mode/scope sources.
2. Canonical task-ID contract and legacy compatibility rules.
3. Agent/task lifecycle read-model schema extension.
4. Read-only prototype update.
5. Compatibility validation against live Control API / approval / execution sources.
6. Operator dashboard update only after read-model validation.
7. Production read-only canary and closure gate.

Each step must preserve production state and current authority boundaries unless a later separately approved phase explicitly changes them.

## GREEN Exit Criteria

Phase 2.1D may close GREEN only when:

- a canonical task identity contract is defined
- new records can be correlated across task/approval/execution/audit read models
- legacy records remain correctly labeled legacy/partial
- authoritative execution enforcement mode is visible or explicitly proven unavailable
- authoritative execution enforcement scope is visible or explicitly proven unavailable
- agent/task lifecycle states are represented consistently
- Mission Control shows data provenance/quality for uncertain fields
- browser remains read-only
- existing approval and Mission Control routes remain intact
- production allowlist remains `general` only
- monitoring, backups, and self-heal remain active
- no uncontrolled provider or execution path is introduced

## Current Decision

**Phase 2.1D is authorized to begin as a read-only, contract-first observability increment.**

No authority expansion is authorized.
