# Phil AI OS Platform — Phase 2.2 A6.8 Controlled Eligibility + One Handoff Canary Gate

**Phase:** 2.2 A6.8 — Controlled Eligibility + One Handoff Canary  
**Status:** PREPARATION / NOT AUTHORIZED FOR PRODUCTION  
**Date:** 2026-08-28

## Purpose

Prove exactly one real Hermes -> `specialist-worker-01` handoff in production without granting provider execution or leaving the specialist broadly eligible after the bounded canary.

A6.8 is the first Phase 2.2 gate allowed to temporarily set the specialist registry row to enabled/assignable. The authorization is canary-scoped only.

## Preconditions

A6.8 may run only while all remain true:

- A6.1–A6.7 GREEN;
- Control API health/readiness GREEN;
- current Control API image is the A6.7 writer image;
- `task_handoffs` exists and contains no unexpected pending handoffs;
- Hermes remains L3, enabled, assignable;
- specialist remains L1, disabled, non-assignable before the canary;
- specialist assignment references remain zero before the canary;
- specialist signed presence is fresh and signature-verifiable;
- Hermes authenticated presence is fresh;
- execution allowlist remains exactly `general`;
- Mission Control mutation methods remain `405`;
- monitor/backups/self-heal remain active.

Any mismatch blocks the canary.

## Canary task

A6.8 MUST create a dedicated non-executing canary task rather than reuse a real business task.

Required properties:

- task class: `general`;
- required authority: exactly `L1`;
- source owner before handoff: `hermes`;
- target: `specialist-worker-01`;
- no provider execution;
- no execution approval consumption;
- canary source/requester clearly identifies Phase 2.2 A6.8;
- canary is terminalized after handoff proof so it leaves no active specialist workload.

## Authoritative required-authority evidence

A6.7 intentionally fails closed because the current task schema does not durably expose `required_authority`.

A6.8 MUST NOT infer required authority from:

- caller input;
- target authority ceiling;
- source authority ceiling;
- task class alone;
- task text alone.

For the bounded canary only, the approved production workflow may create a root-controlled canary task-policy evidence file in the existing host runtime-state surface, which the Control API sees read-only.

The task-policy evidence MUST be bound to:

- exact canary `task_id`;
- `task_class=general`;
- `required_authority=L1`;
- `source_agent_id=hermes`;
- `target_agent_id=specialist-worker-01`;
- `authorized_by=CEO`;
- A6.8 authorization identifier;
- short expiry;
- a unique canary correlation identifier.

The A6.8 Control API extension may return required authority only when this exact bounded policy evidence is valid. All other tasks continue to fail closed.

## Human handoff authorization separation

Handoff request and handoff authorization remain distinct.

Required sequence:

1. create/assign the canary task to Hermes;
2. create bounded task-policy evidence with handoff authorization still false/unbound;
3. request the handoff, producing one `requested` `task_handoffs` row with `handoff_approval_state=pending` and zero target assignment;
4. bind the previously granted CEO A6.8 authorization to the exact returned `handoff_id` in the root-controlled policy evidence;
5. only then may acceptance recognize the handoff as human-authorized.

No general-purpose handoff-approval endpoint is introduced by A6.8.

## Authenticated readiness evidence

A6.8 MUST use bounded canary readiness evidence rather than treating registry eligibility as readiness.

The approved workflow MUST verify before acceptance:

### Hermes source

- authenticated Hermes presence evidence fresh;
- registry enabled/assignable;
- Hermes is the current durable owner of the canary;
- source presence/readiness may be `busy` because Hermes necessarily owns the canary task.

### Specialist target

- Ed25519 specialist presence signature verifies against the A6.4 public key;
- signed observation is fresh;
- registry is temporarily enabled/assignable only after explicit A6.8 authorization;
- authority ceiling remains L1;
- specialist has zero prior assignment references before the canary;
- target readiness projects `ready` only for this bounded canary.

A short-lived root-controlled readiness evidence file may be written to the existing runtime-state surface after these checks. The Control API must treat it as canary-only and revalidate current registry/ownership/workload evidence at acceptance.

## Source readiness correction

A6.7 intentionally left all eligible readiness as `indeterminate`, so acceptance was inert.

For A6.8 canary semantics:

- source must have fresh authenticated presence and may be `busy` or `ready`;
- target must be exactly `ready`;
- source being `busy` is not a handoff failure because owning the canary is the reason for the transfer.

This remains canary-scoped and does not create an automatic scheduler.

## Temporary eligibility

The specialist registry transition is bounded:

```text
before:  enabled=false, assignable=false
canary:  enabled=true,  assignable=true
final:   enabled=false, assignable=false
```

The authority ceiling remains L1 throughout.

Temporary eligibility does not grant provider credentials or `/v1/execute` capability.

## Exactly-one handoff proof

Before acceptance, record baseline counts.

After acceptance, prove:

- exactly one `task_handoffs` row for the canary;
- state is `accepted`;
- source is Hermes;
- target is specialist;
- exact policy/correlation provenance matches;
- exactly one new target `ASSIGNED` lifecycle event exists for the canary;
- current owner after handoff is the specialist;
- no duplicate target assignment exists;
- handoff approval and execution approval remain separate;
- no provider/execution/usage delta was caused by the canary.

Then replay the same accept request and prove no second assignment is created.

## Post-canary containment

After handoff and replay proof:

1. append a terminal lifecycle stage for the dedicated canary without provider execution;
2. restore specialist registry state to L1, disabled, non-assignable;
3. remove/expire the temporary task-policy and readiness evidence files;
4. verify specialist durable active workload is zero because the canary is terminal;
5. retain the accepted handoff row and lifecycle history as audit evidence.

The canary therefore proves the transfer mechanism without leaving broad eligibility enabled.

## Failure containment / rollback

A6.8 requires a fresh pre-change database backup and exact application/compose rollback snapshot.

If any invariant fails after mutation begins, rollback MUST restore:

- pre-canary database state;
- pre-A6.8 Control API image/application/compose;
- specialist registry state disabled/non-assignable;
- no temporary canary policy/readiness files;
- no partial canary task/handoff/assignment state.

No failure may trigger provider execution, automatic retry, reroute, delegation, or assignment.

## Production effects explicitly excluded

A6.8 does **not** authorize:

- provider credentials for specialist;
- `/v1/execute` for specialist;
- direct provider access;
- task-class widening beyond `general`;
- permanent automatic assignment;
- automatic retry/reroute/delegation/execution;
- Mission Control mutation capability;
- a second handoff canary;
- generic handoff approval APIs;
- arbitrary task-authority registration.

## Approval boundary

Production A6.8 remains BLOCKED until explicit CEO approval.

Required authorization phrase:

`APPROVE_PHASE_2_2_A6_8`
