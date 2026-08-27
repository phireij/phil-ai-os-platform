# Phil AI OS Platform — Phase 2.1G Lifecycle Provenance Contract

**Status:** ACTIVE DESIGN CONTRACT  
**Date:** 2026-08-27

## Discovery evidence

Authoritative read-only discovery run:

- Run: `33033927748`
- Job: `98392393095`
- Conclusion: SUCCESS
- Marker: `PHIL_AI_OS_PHASE_2_1G_DURABLE_LIFECYCLE_SOURCE_DISCOVERY_OK`

Observed durable tables:

### `approval_requests`

Relevant fields include:

`approval_id`, `created_at`, `updated_at`, `expires_at`, `state`, `source`, `requester`, `task_class`, `requested_by`, `decision_by`, `decision_at`, `consumed_at`, `consumed_by`, `task_id`.

### `execution_audit`

Relevant fields include:

`id`, `occurred_at`, `source`, `task_class`, `execution_mode`, `outcome`, `approval_id`, `task_id`.

At discovery time:

- approval rows: `45`
- execution-audit rows: `34`
- approval rows with non-null canonical `task_id`: `0`
- execution-audit rows with non-null canonical `task_id`: `0`
- canonical task-ID mismatch count: `0`

This is expected: Phase 2.1F did not backfill historical rows and no post-activation canonical approval had yet been created.

## Provenance classes

Mission Control lifecycle fields MUST use one of these provenance classes:

- `authoritative` — directly persisted by the Control API or durable control-plane DB.
- `derived` — deterministically inferred from authoritative fields without inventing an event that is not persisted.
- `legacy_partial` — evidence exists for historical rows but canonical task identity is absent.
- `unavailable` — current authoritative sources cannot prove the state.

A derived field must never be presented as if it were an independently persisted event.

## Lifecycle mapping

| Lifecycle concept | Current source | Provenance | Rule |
| --- | --- | --- | --- |
| `RECEIVED` | `approval_requests.created_at` | authoritative | Proven when an approval request exists. |
| `CLASSIFIED` | `approval_requests.task_class` | authoritative | Proven when task class is persisted. |
| `ASSIGNED` | none | unavailable | `requester`, `requested_by`, `consumed_by`, or audit `source` MUST NOT be relabelled as assignee. |
| `PLANNED` | none | unavailable | No durable plan event exists. |
| `POLICY_CHECK` | current request/approval flow behavior only | unavailable as durable event | Existing governance may perform checks, but no standalone durable policy-check event is persisted. |
| `APPROVAL_PENDING` | `approval_requests.state` | authoritative/derived label | Only when persisted state is pending. |
| `AUTHORIZED` | approval `state=approved` plus decision metadata | authoritative/derived label | Approval is authoritative; lifecycle label is derived from that persisted state. |
| `DENIED` | `approval_requests.state=denied` | authoritative | Direct durable state. |
| `EXPIRED` | `approval_requests.state=expired` | authoritative | Direct durable state. |
| approval consumed | `consumed_at`, `consumed_by` | authoritative | Represents consumption, not assignment and not execution start. |
| `EXECUTING` | none | unavailable | Current audit persistence occurs after/at an audit write; no durable execution-start event exists. |
| execution outcome | `execution_audit.outcome` | authoritative | Outcome text/value may support derived terminal-state presentation only through an explicit mapping contract. |
| `AUDITED` | existence of linked `execution_audit` row / `occurred_at` | authoritative/derived label | Audit record existence is authoritative; lifecycle label is derived. |
| `CLOSED` | none | unavailable | No durable close event exists. |

## Agent identity and assignment semantics

The following fields are identity/context evidence but **not authoritative assignment fields**:

- `source`
- `requester`
- `requested_by`
- `decision_by`
- `consumed_by`
- execution-audit `source`

Mission Control may display these using their real semantic labels, but MUST NOT rename any of them to `assigned_agent`, `owner`, or equivalent.

A future authoritative assignment model requires an explicit durable assignment field/event and must obey the rule that assignment cannot increase authority.

## Historical/legacy rule

Historical rows with `task_id=NULL` remain `legacy_partial` and MUST NOT be backfilled or assigned synthetic canonical task IDs.

Only records carrying a genuinely persisted `task_id` may populate the canonical task list.

## Phase 2.1G implementation decision

Phase 2.1G will proceed in two layers:

1. **Read-model improvement first:** expose lifecycle evidence/provenance that is already authoritative, while showing unavailable stages explicitly and keeping canonical task count at zero until a real post-2.1F task exists.
2. **Lifecycle-ledger / assignment persistence only if separately justified:** a new DB migration is not implied by this contract. Any future persistence change must receive its own isolated migration validation, application-candidate validation, rollback contract, production preflight, and controlled activation.

## Safety posture

This contract changes no execution authority.

- Mission Control remains read-only.
- production allowlist remains `general` only.
- direct provider bypass remains prohibited.
- human approval and Control API governance remain authoritative.
- no approval/execution/provider mutation is introduced.
- no historical task identity is fabricated.
