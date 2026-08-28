# Phil AI OS Platform — Phase 2.2 A7 Mission Control Multi-Agent Read Model Gate

**Phase:** 2.2 A7 — Mission Control Read Model Integration  
**Status:** OPEN / GOVERNED ENGINEERING  
**Date:** 2026-08-28

## Purpose

A7 implements the Phase 2.2 gate requirement to expose multi-agent state in Mission Control **read-only** while preserving the Control API as authoritative coordinator and preserving all existing approval/execution boundaries.

A7 does not authorize permanent specialist eligibility, automatic delegation, provider execution, task-class widening, Mission Control mutation, or a generic authority grant.

## Entry state

A6 is GREEN / COMPLETE.

Production entry invariants:

- `hermes`: L3, enabled, assignable;
- `specialist-worker-01`: L1, disabled, non-assignable;
- specialist signed presence runtime active;
- one durable accepted A6.8 handoff audit row;
- exactly one historical specialist target `ASSIGNED` event for the completed A6.8 canary;
- active specialist workload zero;
- A6.8 canary latest stage `COMPLETED`;
- execution approval for the canary was not consumed;
- temporary A6.8 canary policy/readiness files absent;
- execution allowlist `general` only;
- Mission Control mutation methods `405`;
- automatic assignment/retry/reroute/delegation/execution false.

## Required A7 projection

Mission Control must expose, without gaining write authority:

1. registered workers and exact `agent_id`;
2. display name / role when available;
3. authority ceiling;
4. registry eligibility (`enabled`, `assignable`);
5. presence state and evidence completeness;
6. workload / latest owned lifecycle state;
7. readiness classification that does not grant permission;
8. durable handoff state, source, target, correlation and decision state;
9. handoff evidence completeness;
10. active-vs-historical ownership distinction;
11. fail-closed/indeterminate projection when evidence is incomplete or conflicting.

## Safety rules

- Mission Control remains observational and non-authoritative.
- No Mission Control POST/PUT/PATCH/DELETE capability is introduced.
- Readiness never grants assignment or execution authority.
- Registry authority ceiling is reported as a ceiling, not as a grant.
- Historical specialist assignment from A6.8 must not make the disabled specialist look currently eligible or busy.
- Accepted handoff audit history must remain visible even though the canary is terminal.
- Missing/invalid specialist signed-presence evidence must project as incomplete/unknown, not ready.
- Disabled or non-assignable registry state takes precedence over presence freshness for assignability/readiness.
- Handoff request/accept/reject routes remain owned by the Control API, not Mission Control.
- No provider credential, execution credential, control token, private key, or secret value may enter the read model.

## Gate sequence

### A7.1 — Production Read-Only Discovery
Inspect current Mission Control implementation, read-model schema, source paths, service wiring, runtime mounts, current API output, A6.8 durable rows, presence evidence surfaces, and mutation boundary. No production mutation.

### A7.2 — Multi-Agent Read Model Contract + Isolated Validation
Define schema and projection semantics off-production. Validate registry precedence, presence attribution, workload ownership, historical handoff visibility, evidence completeness, terminal canary handling, and fail-closed conflict cases.

### A7.3 — Production Preflight
Prove exact source/image/file changes, rollback snapshot, compatibility with the current Mission Control endpoint, unchanged Control API authority, unchanged execution allowlist, and absence of secret material in projection.

### A7.4 — Read-Only Production Integration
Deploy only the minimum Mission Control read-model change required to expose the A7 projection. Revalidate all governance invariants and independently verify the external authenticated operator view. Roll back automatically on any invariant failure.

## A7.4 success criteria

- both registered agents appear in the read model;
- Hermes remains L3 enabled/assignable;
- specialist remains L1 disabled/non-assignable;
- specialist presence is attributable to its dedicated signed evidence;
- specialist active workload is zero;
- completed A6.8 handoff remains visible as historical accepted evidence;
- no duplicate/ambiguous ownership is projected;
- Mission Control mutation methods remain `405`;
- Control API health/readiness remain GREEN;
- execution allowlist remains `general`;
- no approval, lifecycle, handoff, registry, execution, provider, or credential mutation occurs as part of A7;
- automatic assignment/retry/reroute/delegation/execution remain false.

## Authorization boundary

The current CEO instruction to proceed authorizes A7 discovery, contract work, isolated validation, production preflight, and the **read-only observer integration** described above. It does not authorize any worker/runtime/writer/authority/execution expansion beyond the read-only Mission Control projection.
