# Phase 2.1A — Mission Control Operator Read Model Contract

**Program:** Phil AI OS Platform  
**Date:** 2026-08-26  
**Status:** CONTRACT DEFINED / READ-ONLY IMPLEMENTATION PREP  
**Authority:** Phase 2.1 operating-model contract + Mission Control gap matrix + Phase 1 GREEN closure

## Objective

Define one canonical **read-only operator model** for Mission Control that consolidates current Phil AI OS state without creating a new execution or authority path.

The read model is an aggregation/presentation contract. It MUST derive from existing governed Control API and operational state and MUST NOT become a bypass around approval, execution, provider, monitoring, backup, or recovery controls.

## Design principles

1. **Read-mostly first.** Phase 2.1A introduces visibility before new mutation controls.
2. **Control API remains authoritative.** Mission Control presents governed state; it does not independently grant authority.
3. **No hidden side effects.** Loading/refreshing the operator view must not create approvals, execute tasks, call providers, alter policies, or mutate production configuration.
4. **Fail visibly.** Missing/stale/unavailable data must be shown as degraded/unknown, never silently treated as healthy.
5. **Correlate, do not infer authority.** Agent/task/approval/execution links may be presented, but UI correlation must not create permission inheritance.
6. **Preserve Phase 1 controls.** Current `general`-only production scope remains unchanged.

## Canonical top-level read model

```json
{
  "schema_version": "2.1a.v1",
  "generated_at": "<UTC timestamp>",
  "overall_state": "healthy|degraded|contained|unknown",
  "platform": {},
  "governance": {},
  "agents": [],
  "tasks": [],
  "approvals": [],
  "executions": [],
  "recovery": {},
  "data_quality": {}
}
```

## `platform`

Required fields:

- `control_api_health`: `ok|degraded|down|unknown`
- `control_api_readiness`: `ok|not_ready|unknown`
- `monitoring_state`: `active|inactive|failed|unknown`
- `snapshot_generated_at`
- `snapshot_age_seconds`

Optional current-state fields where already available:

- service/runtime summaries from `/v1/mission-control/snapshot`;
- provider/model catalog summary without exposing secrets;
- routing profile summary.

## `governance`

Required fields:

- `execution_allowed_task_classes`
- `execution_enforcement_mode`
- `execution_enforcement_scope`
- `kill_switch_state`: `enabled|disabled|unknown`
- `human_approval_required`: boolean or policy summary
- `direct_provider_bypass_allowed`: MUST be `false` for the governed production path
- `authority_expansion_state`: `blocked|gated|enabled`

Phase 2.1A invariant:

```text
execution_allowed_task_classes = ["general"]
authority_expansion_state = blocked
```

unless a later explicit activation gate changes this.

## `agents`

Phase 2.1A begins with declared/read-only identities; it does not grant new privileges.

Each record should support:

- `agent_id`
- `display_name`
- `role`: `human_operator|cto|gateway|specialist`
- `owner`
- `authority_level`: `L0|L1|L2|L3|L4`
- `status`: `active|inactive|degraded|unknown`
- `credential_binding`: reference/label only, NEVER raw credential
- `allowed_task_classes`
- `can_self_approve`: MUST be `false` for Hermes and specialist agents
- `last_seen_at` where a reliable signal exists

Initial declared identities:

- Human Operator / CEO
- CTO Office
- Hermes

Specialist agents remain unactivated until separately contracted and gated.

## `tasks`

A canonical task record should support:

- `task_id`
- `created_at`
- `updated_at`
- `source`
- `owner_id`
- `assigned_agent_id`
- `task_class`
- `summary`
- `state`
- `approval_id` when applicable
- `execution_id` / audit reference when applicable
- `risk_level` when reliably classified
- `failure_reason` / `blocked_reason`

Canonical lifecycle states:

`RECEIVED -> CLASSIFIED -> ASSIGNED -> PLANNED -> POLICY_CHECK -> [APPROVAL_PENDING] -> AUTHORIZED -> EXECUTING -> {SUCCEEDED | FAILED | BLOCKED | CANCELLED} -> AUDITED -> CLOSED`

Exception/terminal states:

- `DENIED`
- `EXPIRED`
- `REJECTED`
- `AMBIGUOUS`
- `CONTAINED`

### Compatibility rule

Phase 2.1A MUST NOT fabricate `task_id` correlations for historical records. If current approval/execution data lacks a canonical task ID, expose the existing source identifiers and set correlation quality accordingly.

## `approvals`

Each record should support the existing approval contract fields where available:

- `approval_id`
- `created_at`
- `updated_at`
- `expires_at`
- `state`
- `source`
- `requester`
- `requested_by`
- `task_text` / safe summary
- `task_class`
- `confidence`
- `profile`
- primary/fallback provider/model labels
- `decision_by`
- `decision_at`
- `decision_note`
- `consumed_at`
- `consumed_by`
- review-link availability/status without exposing reusable secret tokens

Read-model state must distinguish at least:

`pending|approved|denied|expired|consumed|unknown`

Consumed approval state must remain visibly linked to execution evidence.

## `executions`

Each record should support:

- execution/audit identifier
- `timestamp`
- `source`
- `task_class`
- safe task summary
- provider/model labels
- `outcome`
- `approval_id`
- `agent_id`/requester where available
- `rejection_reason` / failure class
- retry/replay indicator where available

Required presentation rule:

A rejected replay must not be presented as a successful execution. The read model should make clear that replay was blocked before a new provider call when that evidence exists.

## `recovery`

Required fields:

- `backup_timer_state`: `active|inactive|failed|unknown`
- `backup_self_heal_state`: `active|inactive|failed|unknown`
- `latest_backup_status`: `ok|stale|failed|unknown`
- `latest_backup_at` where available
- `restore_validation_status`: `validated|not_validated|unknown`
- `monitoring_independent_of_ui`: MUST remain `true`

Mission Control is not allowed to replace systemd monitoring/backup enforcement during Phase 2.1A.

## `data_quality`

Required fields:

- `freshness`: `fresh|stale|unknown`
- `partial`: boolean
- `missing_sources`: []
- `correlation_quality`: `complete|partial|legacy|unknown`
- `warnings`: []

### Degraded-state rule

If a required source cannot be read, `overall_state` must not remain `healthy` unless the missing source is explicitly non-critical and documented as such.

## Read-source mapping

Initial Phase 2.1A inputs should be limited to existing validated sources:

| Operator model section | Existing source |
|---|---|
| platform safety/runtime snapshot | `/v1/mission-control/snapshot` |
| approvals | `/v1/approvals/recent` |
| executions | `/v1/execution/recent` |
| Control API health | `/healthz` |
| Control API readiness | `/readyz` |
| production allowlist/enforcement | Control API runtime/env state already validated in Phase 1 gates |
| monitoring | `phil-ai-os-monitor.service` state |
| backup | `phil-ai-os-backup.timer` state |
| backup self-heal | `phil-ai-os-backup-self-heal.timer` state |
| durable approval consumption/audit link | Control-plane database/read API evidence |

No new provider endpoint or direct provider credential is required for Phase 2.1A.

## Read-only compatibility requirements

A Phase 2.1A compatibility validation must prove:

1. `/v1/mission-control/snapshot`, `/v1/approvals/recent`, and `/v1/execution/recent` remain authenticated and readable from the Hermes/control context.
2. Refreshing/read-model generation produces **no approval mutation**.
3. It produces **no execution call**.
4. It produces **no provider call**.
5. It produces **no production configuration change**.
6. Current production allowlist remains `general` only.
7. Monitoring, backup timer, and backup self-heal remain active.
8. Approval consumption/audit linkage evidence remains intact.
9. Unknown/missing fields are surfaced as unknown/partial rather than guessed.
10. No raw token, API key, Telegram token, approval review token, or secret path content is returned by the model.

## Security / secret-redaction contract

The read model MUST NEVER expose:

- Control API bearer token;
- OpenAI/OpenRouter/Gemini/Anthropic keys;
- Telegram bot token;
- reusable approval review token;
- SSH private keys;
- raw secret file contents;
- environment-variable values containing credentials.

Provider/model names and non-secret configuration labels may be shown.

## Operator UI contract for Phase 2.1A

The first operator-facing implementation should be read-only and organized into six views/panels:

1. **System Health** — Control API, monitor, backup/self-heal, degraded state.
2. **Governance** — allowed task classes, enforcement scope/mode, kill-switch state.
3. **Agents** — identity, role, authority level, status; no privilege editing yet.
4. **Tasks & Approvals** — lifecycle state and pending/decided approval visibility.
5. **Executions & Audit** — outcomes, approval linkage, rejection/failure evidence.
6. **Recovery & Data Quality** — backup readiness, freshness, missing/partial data warnings.

No Approve/Deny/Execute/Retry/Policy-Edit buttons are introduced by this contract. Existing approval mechanisms remain authoritative until a later mutation-control gate.

## Phase 2.1A exit gate

Phase 2.1A may be declared GREEN when:

1. this read-model contract is committed;
2. read-only compatibility validation passes against current production state;
3. a prototype/aggregate read response can be produced without secret leakage;
4. existing Telegram approval flow remains operational;
5. `general` remains the only production execution task class;
6. monitoring/backup/self-heal remain active;
7. no provider/execution/approval mutation occurs during validation;
8. operator UI/read endpoint implementation plan has explicit rollback/containment boundaries.

## Current CTO decision

**Proceed with Phase 2.1A read-only compatibility validation and aggregate-shape discovery.**

Do not add multi-agent execution, new approval mutation controls, specialist-agent production authority, or expanded task classes in this checkpoint.

`PHIL_AI_OS_PHASE_2_1A_OPERATOR_READ_MODEL_CONTRACT_DEFINED`
