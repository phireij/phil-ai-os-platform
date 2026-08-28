# Phil AI OS Platform — Phase 2.2 A6 Controlled Handoff Preparation Gate

**Phase:** 2.2 A6 — Controlled Handoff Verification  
**Status:** PREPARATION OPEN / PRODUCTION HANDOFF NOT AUTHORIZED  
**Date:** 2026-08-28

## Why A6 needs subgates

A5 registered `specialist-worker-01` as a durable L1 identity, but intentionally left it disabled, non-assignable, without a runtime, without provider credentials, and without execution authority.

The A2 handoff contract requires the target to be explicitly eligible and `ready` at acceptance time. Phase 2.1M defines readiness inputs so that registry eligibility, runtime liveness, authenticated logical presence, and durable workload evidence remain separate signals.

Therefore a real cross-agent handoff cannot safely be attempted immediately after A5. A6 is split into preparatory gates that preserve fail-closed semantics.

## A6 subgate sequence

### A6.1 — Second-worker presence-surface discovery

Read-only production discovery of the current Phase 2.1M heartbeat service/timer, evidence-file layout, runtime/read-model code, identity assumptions, token boundary, and any Hermes-hardcoded behavior.

**No mutation.**

### A6.2 — Isolated specialist presence contract

Define and validate an authenticated logical-presence contract for `specialist-worker-01` that:

- does not grant assignment authority;
- can operate while the registry row remains disabled/non-assignable;
- has no provider credentials;
- cannot call `/v1/execute`;
- cannot create/approve/consume approvals;
- writes only bounded non-secret presence evidence;
- produces `unknown/fresh/stale/offline` independently from registry state;
- cannot trigger automatic retry/reroute/delegation/execution.

### A6.3 — Specialist presence production preflight

Prove the smallest additive runtime/presence change, rollback, monitoring isolation, token scope, filesystem paths, service naming, and no collision with Hermes heartbeat.

**No mutation.**

### A6.4 — Specialist presence activation

**REQUIRES EXPLICIT CEO APPROVAL.**

Activate only the non-executing authenticated presence primitive for `specialist-worker-01`. During A6.4 the registry row remains disabled and non-assignable.

No provider credentials, no provider call, no execution, no handoff, no task assignment.

### A6.5 — Handoff persistence/writer isolated validation

Validate the additive `task_handoffs` persistence and an authenticated Control API handoff writer against an isolated copy/candidate application. Request/authorize/accept/reject/expire/contain/replay semantics must match A2.

### A6.6 — Handoff persistence/writer production preflight

Prove additive schema/application activation and rollback without changing worker eligibility or creating a handoff.

**No mutation.**

### A6.7 — Inert handoff persistence/writer activation

**REQUIRES EXPLICIT CEO APPROVAL.**

Activate the persistence/writer in a fail-closed state where `specialist-worker-01` remains non-assignable. This proves production wiring without permitting transfer.

### A6.8 — Controlled eligibility + one handoff canary

**REQUIRES EXPLICIT CEO APPROVAL.**

Only after A6.1–A6.7 are GREEN:

1. enable and make `specialist-worker-01` assignable only within the bounded canary authorization;
2. prove authenticated presence is fresh;
3. create or select a non-executing bounded canary task whose required authority is L1 or lower;
4. require explicit human handoff authorization;
5. request and accept exactly one Hermes -> specialist handoff;
6. prove exactly one new target `ASSIGNED` event;
7. perform **no provider execution**;
8. verify replay rejection, source/target provenance, approval separation, and no duplicate ownership ambiguity;
9. return the candidate to the explicitly authorized post-canary state if the gate requires containment.

## Critical distinction: presence vs eligibility

Presence evidence alone never makes the specialist assignable.

During A6.4, the intended state is:

```text
registered = true
enabled = false
assignable = false
runtime_presence = fresh | stale | offline | unknown
authority_ceiling = L1
provider_execution = none
```

Because registry eligibility takes precedence, readiness remains `unassignable` even if logical presence is fresh. This is intentional and proves presence without silently enabling work receipt.

## Production approval boundaries

No further CEO approval is required for A6.1, A6.2, A6.3, A6.5, or A6.6 because they are read-only, isolated, or preparatory.

Explicit CEO approval is required before each production authority/runtime mutation boundary:

- **A6.4:** start specialist logical-presence runtime;
- **A6.7:** activate production handoff persistence/writer surface;
- **A6.8:** make specialist eligible and perform a real controlled handoff.

These approvals are intentionally separate so a successful presence activation cannot silently authorize handoff.

## Invariants retained throughout preparation

- Hermes remains L3.
- Specialist authority ceiling remains L1.
- Production execution allowlist remains `general` only.
- Human approval and no-self-approval rules remain unchanged.
- Mission Control remains read-only.
- No automatic assignment, retry, reroute, delegation, or execution.
- No direct provider bypass.
- No provider credential is granted to the specialist presence runtime.
- Missing/conflicting identity, authority, presence, workload, approval, or correlation evidence fails closed.

## Current authorization

Proceed autonomously through A6.1–A6.3 and A6.5–A6.6 preparatory work. Stop before A6.4, A6.7, or A6.8 unless the CEO explicitly authorizes the corresponding production activation.
