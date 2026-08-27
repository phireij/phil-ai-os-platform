# Phase 2.1J — First Genuine Canonical Task Canary Contract

Status: **AUTHORIZED FOR ONE NON-EXECUTING CANARY TASK**

## Purpose
Validate the live coordinator intake path on exactly one genuine canonical `general` task while explicitly prohibiting approval decision, approval consumption, provider execution, and `/v1/execute` use.

## Allowed production mutations
Exactly one new approval/task record may be created through the authenticated `/v1/approvals/request` route. For that one canonical task only, the canary may create:

- intake lifecycle evidence: `RECEIVED`, `CLASSIFIED`, `APPROVAL_PENDING`;
- one explicit `ASSIGNED` event to registered worker `hermes` through `/v1/tasks/assign`;
- one bounded plan through `/v1/tasks/plan`, producing one `PLANNED` event and a server-generated plan reference.

No other production mutation is authorized by this contract.

## Explicitly prohibited
The canary MUST NOT:

- approve or deny the approval;
- consume the approval;
- call `/v1/execute`;
- call any provider;
- create an execution-audit row;
- change provider/model routing;
- change the production allowlist;
- change any agent authority ceiling;
- add a second agent registry entry;
- expose a Mission Control mutation control;
- fabricate historical lifecycle data.

## Pre-canary invariants
The workflow must refuse to continue unless:

- live image is `phil-ai-os/control-api:0.20.3-phase21i`;
- database `quick_check=ok`;
- `agent_registry` contains exactly one enabled/assignable `hermes` entry with ceiling `L3`;
- `task_plans` count is zero;
- `task_lifecycle_events` count is zero;
- production allowlist is exactly `general`;
- Mission Control schema is `2.1i.v1`;
- Mission Control POST/PUT/PATCH/DELETE remain `405`;
- public unauthenticated operator route returns `401`;
- unauthenticated intake/assign/plan routes return `401`.

## Canary sequence
1. Capture approval, lifecycle, plan, and execution-audit counts.
2. Create exactly one authenticated `general` approval request with a unique canary marker in its task text.
3. Capture returned immutable `approval_id` and server-generated immutable `task_id` without logging task text or auth material.
4. Verify exactly one new approval row and lifecycle stages `RECEIVED`, `CLASSIFIED`, `APPROVAL_PENDING` for that `task_id`.
5. Verify approval remains `pending` and has no decision/consumption fields set.
6. Authenticated assignment of that `task_id` to `hermes`.
7. Verify one `ASSIGNED` lifecycle event and no authority/policy change.
8. Authenticated creation of one bounded plan for the same `task_id`.
9. Verify one active plan with a server-generated plan reference and one `PLANNED` lifecycle event.
10. Verify execution-audit count is exactly unchanged and no provider/execution evidence exists for the canary task.
11. Verify Mission Control reads the new task/coordinator metadata while remaining read-only.

## Expected durable delta
Compared with the immediately preceding baseline:

- `approval_requests`: +1
- `task_lifecycle_events`: +5 (`RECEIVED`, `CLASSIFIED`, `APPROVAL_PENDING`, `ASSIGNED`, `PLANNED`)
- `task_plans`: +1
- `execution_audit`: +0
- `agent_registry`: +0

Any different delta is a failed canary.

## Completion state
A successful canary intentionally leaves the approval pending and the task non-executed. This is evidence that coordination can proceed up to planning without crossing the human-approval/execution boundary.
