# Phil AI OS Platform — Phase 2.1I Coordinator Application Interface Contract

**Status:** CONTRACT DEFINED — ISOLATED APPLICATION CANDIDATE NEXT  
**Date:** 2026-08-27

## Authority source

The Control API is the sole authoritative coordinator for Phase 2.1I. Mission Control remains read-only. Hermes is a worker and must not self-assign or self-plan through a bypass path.

## Candidate operations

The isolated candidate may add authenticated internal Control API operations equivalent to:

```text
POST /v1/tasks/assign
POST /v1/tasks/plan
```

These names are candidate interface names, not production authorization.

### Assignment request

Safe request metadata:

```text
task_id
agent_id
requested_by
reason_code (optional, bounded)
```

The server must resolve agent identity and assignability from the authoritative registry. Caller-supplied authority level, role, provider, model, task class or approval state must be ignored/rejected.

A successful assignment appends `ASSIGNED` lifecycle evidence. Reassignment appends a new event; prior evidence is not rewritten.

### Planning request

Safe request metadata:

```text
task_id
plan_kind
requested_by
supersedes_plan_ref (optional)
```

The server generates `plan_ref`. Caller-supplied `plan_ref` must not become authoritative.

A successful planning operation stores safe plan metadata and appends `PLANNED` lifecycle evidence correlated by server-generated `plan_ref`.

No prompt/task body/provider response is stored in the Phase 2.1I plan record.

## Mandatory fail-closed conditions

Both operations fail if canonical `task_id` is absent or the task is terminal.

Assignment additionally fails for unknown, disabled or non-assignable agents.

Planning additionally fails for invalid supersession references.

Unauthenticated requests fail closed.

## Explicit non-capabilities

Neither operation may:

- approve or deny an approval;
- consume approval authorization;
- call `/v1/execute` or a provider;
- change task class;
- alter routing/provider/model policy;
- modify the `general`-only allowlist;
- change an agent's authority ceiling;
- expose a Mission Control mutation control;
- accept caller-supplied authority claims as truth.

## Transaction semantics

Registry/plan persistence and corresponding lifecycle event append should occur in one SQLite transaction per operation. Partial success is prohibited.

## Read response

Responses should contain only safe coordination metadata such as `task_id`, `agent_id`, `plan_ref`, lifecycle stage and timestamp. They must not return task text, decision notes, provider output, secrets or bearer credentials.

## Next gate

Patch a copy of the current Control API application and a copy of the live database. Validate authentication, fail-closed assignment/planning, server-generated plan IDs, append-only history, atomicity and absence of provider/execution/approval side effects. Production remains unchanged until a separate preflight and activation contract are GREEN.
