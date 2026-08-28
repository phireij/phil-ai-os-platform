# Phil AI OS Platform — Phase 2.2 A6.8 Controlled Handoff Canary Production Preflight Result

**Phase:** 2.2 A6.8 — Controlled Eligibility + One Handoff Canary  
**Status:** GREEN / PREPARED — PRODUCTION CANARY NOT AUTHORIZED  
**Date:** 2026-08-28  
**Workflow run:** `33144200440`  
**Workflow job:** `98761552635`  
**Evidence artifact:** `phase-2-2-a6-8-production-preflight-evidence` (`9675117772`)  
**Artifact digest:** `sha256:c0bf76e81dd30cacb2e483472b9eb7ba3071fcf97394f942020b7418b7ed2668`

## Decision

A6.8 production preflight is GREEN. The production system has the exact anchors required to execute one separately authorized, non-executing Hermes -> `specialist-worker-01` handoff canary with temporary specialist eligibility and post-canary return to disabled/non-assignable state.

No production mutation was performed by this preflight.

## Current production baseline

Verified before any A6.8 authority change:

- Control API health/readiness: GREEN;
- Control API image: `phil-ai-os/control-api:0.21.0-phase22a67`;
- Control API application SHA-256: `faa727987e087e2540fec7be0c9d709f7cc57dd51ddc767a3d8b39e0a6474b55`;
- execution allowlist: exactly `general`;
- Mission Control mutation methods: `405`;
- monitor, backup timer, backup self-heal, Hermes heartbeat and specialist presence timer: active;
- `task_handoffs` table: present;
- `task_handoffs` rows: `0`;
- specialist assignment references: `0`.

Registry remains exactly:

```text
hermes                L3  enabled=true   assignable=true
specialist-worker-01  L1  enabled=false  assignable=false
```

## Presence and identity evidence

### Specialist

Read-only verification proved:

- Ed25519 signature verified successfully;
- identity is exactly `specialist-worker-01`;
- authority ceiling remains L1;
- signed registry projection remains disabled/non-assignable;
- observed presence age during preflight: `33.485` seconds.

### Hermes

Existing Hermes presence evidence was present and fresh:

- observation type: `authenticated_control_api_roundtrip`;
- presence age during preflight: `12.984` seconds;
- bounded evidence keys were readable without exposing credentials.

## Canary policy/readiness surface

The existing Control API runtime-state bind provides a suitable root-controlled, read-only-to-Control-API evidence surface.

Available paths are collision-free:

- `phase2_2_a6_8_canary_policy.json`;
- `phase2_2_a6_8_canary_readiness.json`.

This allows A6.8 to bind required authority, exact task/source/target, short expiry, CEO authorization and exact `handoff_id` without introducing a generic task-authority or handoff-approval API.

## Existing authenticated coordinator anchors

Production source contains all required existing primitives:

- `approval_create(...)`;
- authenticated `/v1/approvals/request`;
- `coordinator_assign(...)`;
- authenticated `/v1/tasks/assign`;
- `lifecycle_event_insert(...)`;
- authenticated handoff request/accept/reject routes;
- A6.7 required-authority fail-closed behavior.

The existing Control API bearer secret is present with mode `0400`; its value was not printed or copied into evidence.

## A6.8 bounded semantics

The prepared production canary is constrained to:

- one dedicated `general` task;
- authoritative required authority exactly `L1`;
- source owner exactly `hermes`;
- target exactly `specialist-worker-01`;
- temporary specialist registry transition only for the canary;
- separate handoff request and human handoff authorization;
- source authenticated presence may project `busy` because Hermes owns the canary;
- target must project exactly `ready`;
- exactly one accepted handoff and one target `ASSIGNED` lifecycle event;
- accept replay must create no duplicate assignment;
- no provider execution;
- no execution-approval consumption;
- canary terminalization after proof;
- specialist returned to L1, disabled, non-assignable;
- temporary policy/readiness evidence removed or expired;
- accepted handoff/lifecycle history retained for audit.

## Safety state

- provider execution authorized: no;
- `/v1/execute` authorized: no;
- task-class widening authorized: no;
- generic handoff approval API authorized: no;
- permanent specialist eligibility authorized: no;
- automatic assignment/retry/reroute/delegation/execution: false;
- Mission Control write authority: none.

Marker: `PHIL_AI_OS_PHASE_2_2_A6_8_PRODUCTION_PREFLIGHT_OK`

## Gate decision

**A6.8 preparation: GREEN. Production canary remains BLOCKED pending explicit CEO approval.**

Required authorization phrase: `APPROVE_PHASE_2_2_A6_8`.
