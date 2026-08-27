# Phil AI OS Platform — Phase 2.1I Agent Registry Contract v1

**Status:** CONTRACT DEFINED — ISOLATED VALIDATION REQUIRED  
**Date:** 2026-08-27

## Purpose

Provide an authoritative, durable identity source for assignable agents without granting execution authority.

## Minimal registry schema

```text
agent_registry
- agent_id TEXT PRIMARY KEY
- display_name TEXT NOT NULL
- role TEXT NOT NULL
- authority_ceiling TEXT NOT NULL
- status TEXT NOT NULL
- assignable INTEGER NOT NULL
- created_at TEXT NOT NULL
- updated_at TEXT NOT NULL
```

Initial allowed `status` values:

- `active`
- `inactive`
- `disabled`

Initial authority ceilings:

- `L0`
- `L1`
- `L2`
- `L3`
- `L4`

## Identity rules

- `agent_id` is immutable after creation.
- Display name or role must never substitute for `agent_id`.
- Assignment must reference an exact registered `agent_id`.
- Requester/source fields are not agent identity.
- Unknown, disabled, inactive, or non-assignable agents must fail closed.

## Authority rules

Registry authority is a **ceiling**, not a grant.

An assignment cannot:

- increase the agent's authority ceiling;
- override approval requirements;
- expand task-class allowlists;
- permit direct provider access;
- trigger execution;
- change routing policy.

## Initial registry candidates

The registry may eventually contain durable identities for:

- `human-operator-ceo`
- `cto-office`
- `hermes`

These names are candidate stable IDs for validation only until production activation is separately approved.

## Assignment validation rule

A future assignment writer must verify all of the following in one transaction before appending `ASSIGNED`:

1. canonical `task_id` exists;
2. `agent_id` exists in `agent_registry`;
3. agent status is `active`;
4. agent is assignable;
5. requested assignment does not imply authority above the registry ceiling;
6. assignment does not modify approval state or execution policy.

## Reassignment

Reassignment is represented by a later append-only `ASSIGNED` lifecycle event with the new `assigned_agent_id` and an explicit reason code. Prior assignment events remain immutable.

## Mission Control

Mission Control may read registry and assignment data but remains read-only.

## Next gate

Validate this schema and assignment/reassignment semantics on an isolated copy only. Production schema remains unchanged until the isolated validator is GREEN.
