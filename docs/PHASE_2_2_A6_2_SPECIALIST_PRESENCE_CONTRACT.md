# Phil AI OS Platform — Phase 2.2 A6.2 Specialist Presence Contract v1

**Phase:** 2.2 A6.2 — Isolated Specialist Presence Contract  
**Status:** CONTRACT DEFINED — ISOLATED VALIDATION REQUIRED  
**Date:** 2026-08-28  
**Production effect:** NONE

## Purpose

Define authenticated logical-presence semantics for `specialist-worker-01` without granting assignment, handoff, execution, approval, provider, or autonomous authority.

The contract extends the proven Phase 2.1M separation of registry state, runtime liveness, logical presence, and workload to the second durable identity introduced in A5.

## Identity rule

A presence observation for `specialist-worker-01` is valid only when the evidence is attributable to the exact stable identity `specialist-worker-01` through a bounded authentication mechanism.

It is not sufficient to:

- copy or rename Hermes heartbeat evidence;
- infer identity from container name alone;
- infer identity from host process name alone;
- reuse Hermes identity context and relabel the result;
- write a host file that claims specialist identity without an authenticated specialist-originated observation.

A6.1/A6.3 must determine the smallest production mechanism that satisfies this rule without broad credentials.

## Four independent dimensions

The read model MUST keep these dimensions separate:

1. **Registry state**
   - registered / absent
   - enabled / disabled
   - assignable / non-assignable
   - authority ceiling
2. **Runtime liveness**
   - running / stopped / unknown
3. **Logical presence**
   - `fresh`
   - `stale`
   - `offline`
   - `unknown`
4. **Durable workload**
   - derived only from authoritative assignment/lifecycle evidence

No dimension may silently overwrite another.

## Presence freshness semantics

Reuse the Phase 2.1M thresholds unless later production evidence requires a separately governed change:

- age <= 120 seconds => `fresh`
- age > 120 and <= 300 seconds => `stale`
- age > 300 seconds => `offline`
- no valid authenticated observation => `unknown`

These classifications are observational only.

## Registry precedence

Registry eligibility always takes precedence over presence for assignment readiness.

During the first specialist presence activation, the required production state remains:

```text
agent_id = specialist-worker-01
authority_ceiling = L1
enabled = false
assignable = false
logical_presence = fresh | stale | offline | unknown
```

Therefore even `logical_presence=fresh` MUST classify assignment readiness as `unassignable` while `enabled=false` or `assignable=false`.

Presence cannot enable the registry row.

## Runtime boundary

The initial specialist runtime, if later activated, MUST be presence-only/non-executing.

It MUST NOT have:

- OpenAI/OpenRouter/Anthropic/Gemini/provider credentials;
- access to `/v1/execute`;
- approval create/approve/deny/consume capability;
- coordinator assignment/planning/handoff write capability;
- database write access;
- Mission Control mutation capability;
- host Docker socket access;
- broad host filesystem access;
- Hermes identity credentials.

It may have only the minimum credential/surface required to prove an authenticated bounded Control API observation and emit non-secret heartbeat evidence.

## Authentication separation

The production design MUST prove one of the following before A6.4:

1. a distinct least-privilege specialist observation credential/context that is not usable for execution or approval; or
2. another cryptographically/authentically attributable observation mechanism that proves the specialist runtime performed the observation.

A shared credential is acceptable only if the surrounding mechanism independently and durably binds the observation to the specialist runtime identity; a shared bearer credential plus caller-supplied `agent_id` is insufficient.

If identity attribution cannot be proven, logical presence MUST remain `unknown`.

## Evidence-file contract

If the existing Phase 2.1M host evidence-file pattern is reused, the specialist evidence file should be isolated at a path equivalent to:

`/var/lib/phil-ai-os/agent-presence/specialist-worker-01.json`

It may contain only bounded non-secret fields such as:

```text
schema_version
agent_id
observation_type
observed_at
status
runtime_instance_id (opaque/non-secret, optional)
evidence_digest (optional)
```

It MUST NOT contain tokens, credentials, raw headers, prompts, task text, provider responses, or unrestricted host metadata.

Atomic replacement is required so readers never consume partial JSON.

## Workload semantics

While the specialist has no valid `ASSIGNED` lifecycle event, durable active workload is exactly zero only if the lifecycle query positively proves zero assignments/workload; absence of a readable source is `unknown`, not zero.

Presence does not create workload and workload does not create presence.

## Readiness projection

The specialist readiness projection follows the existing fail-closed precedence:

1. absent/disabled/non-assignable registry => `unassignable`;
2. otherwise stale/offline presence => `stale`;
3. otherwise missing/conflicting presence/workload/policy evidence => `indeterminate`;
4. fresh + active workload => `busy`;
5. fresh + explicit zero workload + eligible registry + verified `general` policy scope => `ready`.

A6.4 does not authorize moving past rule 1 because the specialist remains disabled/non-assignable.

## No-authority semantics

For every presence state:

- authority effect: none;
- automatic assignment: false;
- automatic retry: false;
- automatic reroute: false;
- automatic delegation: false;
- automatic execution: false;
- approval effect: none;
- provider effect: none.

## Failure / containment rules

- missing identity attribution => presence `unknown`;
- malformed/stale evidence => fail closed to `unknown/stale/offline` as applicable;
- runtime stopped with recent heartbeat => report runtime stopped separately; do not rewrite heartbeat-derived freshness;
- running runtime with no authenticated heartbeat => logical presence `unknown`;
- conflicting specialist/Hermes identity evidence => `unknown` plus containment signal;
- any evidence of execution/provider/approval/coordinator-write capability in the presence runtime blocks A6.4 activation.

No failure state may trigger reroute or auto-repair that mutates assignment.

## A6.2 isolated acceptance criteria

A6.2 is GREEN only if isolated tests prove:

1. fresh authenticated specialist evidence is classified `fresh`;
2. stale/offline/unknown thresholds match Phase 2.1M;
3. disabled/non-assignable registry remains `unassignable` even with fresh presence;
4. running runtime without heartbeat remains logical presence `unknown`;
5. stopped runtime with recent heartbeat preserves heartbeat freshness separately;
6. specialist evidence cannot be substituted with Hermes identity evidence;
7. zero workload is accepted only from explicit durable zero evidence;
8. missing workload evidence fails closed;
9. no presence state grants authority or automatic action;
10. no provider/execution/approval/coordinator-write capability is part of the contract.

## Production boundary

This contract does not authorize a specialist runtime, token, service, timer, evidence file, registry change, handoff table, assignment, or execution in production.
