# Phil AI OS Platform — Phase 2.1J Coordinator-Controlled Task Intake & First Genuine Lifecycle Canary

Status: **OPEN — DISCOVERY / CONTRACT FIRST**

## Objective
Validate the first genuine coordinator-controlled canonical task intake flow in production without allowing provider execution.

The canary is intended to prove that a real canonical task can enter the durable lifecycle ledger and coordinator model while all execution authority remains blocked.

## Initial bounded lifecycle scope
The first production task-intake canary may emit only lifecycle events that are already authoritative at intake/coordination time:

1. `RECEIVED`
2. `CLASSIFIED`
3. `APPROVAL_PENDING`
4. `ASSIGNED` only through the authenticated Control API coordinator operation and only to an enabled/assignable registered agent.
5. `PLANNED` only through the authenticated Control API coordinator operation with a server-generated plan reference.

The canary must not emit `EXECUTING`, `SUCCEEDED`, `FAILED`, or `CLOSED` and must not invoke the provider execution boundary.

## Authority constraints
- Production execution allowlist remains `general` only.
- Human approval remains authoritative.
- Assignment does not grant execution authority.
- Planning does not grant execution authority.
- Mission Control remains read-only.
- Direct provider bypass remains prohibited.
- No approval may be auto-approved or consumed by this canary.
- No provider call or `/v1/execute` request is permitted during this canary.

## Canary success criteria
A GREEN canary must prove all of the following for one newly created genuine canonical task:

- server-generated canonical `task_id` exists;
- approval request remains pending;
- durable lifecycle contains exactly the allowed intake/coordination evidence emitted by the canary;
- assignment references the registered `hermes` worker only;
- plan reference is server-generated and durable;
- Mission Control read model correlates the task, lifecycle evidence, registry, and plan metadata;
- no execution audit row is created for the canary task;
- no approval consumption occurs;
- no provider call occurs;
- operator authentication and Mission Control `405` mutation boundary remain intact;
- recovery services remain active.

## First gate
Perform read-only discovery of the current production intake/request, assignment, planning, approval, lifecycle, and execution interfaces and pin the exact canary request sequence before any genuine task is created.
