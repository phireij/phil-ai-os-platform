# Phil AI OS Platform — Phase 2.2 A7.1 Mission Control Read Model Discovery Result

**Phase:** 2.2 A7.1 — Production Read-Only Discovery  
**Status:** GREEN / DISCOVERY COMPLETE — EXISTING READ-MODEL DEFECT IDENTIFIED  
**Date:** 2026-08-28  
**Primary discovery run:** `33147578282`  
**Primary evidence artifact:** `phase-2-2-a7-1-mission-control-discovery-evidence` (`9676369448`)  
**Primary artifact digest:** `sha256:cafa192ac17998a5d34b16b0cd6b019d2d1579446f0cea84b65295341e43dd5c`  
**Diagnostic run:** `33147658765`  
**Diagnostic job:** `98772169902`  
**Diagnostic artifact:** `phase-2-2-a7-1b-read-model-diagnostic` (`9676402598`)  
**Diagnostic digest:** `sha256:04746d524b949c92981388f753869b6ff9e04599a5b16c2c372b480c186d7773`

## Decision

A7.1 discovery is complete. The production Control API, durable registry, handoff ledger, lifecycle evidence, and both presence mechanisms are healthy enough to support A7. The currently exposed Mission Control aggregate read model is not healthy: `/api/read-model` returns HTTP `503` because of a deterministic defect in the existing `read-model.py` wrapper.

This is a read-only presentation/projection defect. It is not a Control API, database, registry, handoff, execution, or provider outage.

## Exact 503 root cause

`/opt/phil-ai-os/mission-control/read-model.py` defines an outer Python constant:

```text
OPEN_STAGES={'RECEIVED','CLASSIFIED','APPROVAL_PENDING','ASSIGNED','PLANNED'}
```

Its `workload_snapshot()` function then constructs a separate embedded Python program and executes that program inside the Control API container. The embedded program references `OPEN_STAGES`, but does not define that name inside its own interpreter scope.

Direct execution therefore fails with:

```text
NameError: name 'OPEN_STAGES' is not defined
```

The Mission Control server catches the failed subprocess and correctly fails closed with HTTP `503` and a partial/unknown fallback response.

A7 will remove this defect by replacing the affected read-model projection with the A7 multi-agent projection rather than weakening the fail-closed server behavior.

## Mission Control runtime topology

Read-only discovery proved:

- host listener: `127.0.0.1:4881`;
- active process: `/usr/bin/python3 /opt/phil-ai-os/mission-control/server.py`;
- current server is a host process parented by PID 1, not `phil-ai-os-mission-control.service`;
- no host listener was found on port `4880`;
- `server.py` executes the configured read-model Python file on every GET to `/api/read-model`;
- POST/PUT/PATCH/DELETE against `/api/read-model` return HTTP `405`;
- therefore replacing only the read-model file can be sufficient for A7 and does not inherently require a Mission Control server restart.

## Current read-model implementation

`/opt/phil-ai-os/mission-control/agent-runtime-read-model.py`:

- SHA-256: `769b4e292f3d23e30ba494ffdbe689a36241ee41dc651ccaca64c3fd0b5c5971`;
- is Hermes-specific;
- reads only `/var/lib/phil-ai-os/agent-presence/hermes.json`;
- queries only the Hermes registry row;
- observes the Hermes container;
- reports schema `2.1m.v1`;
- contains no specialist-worker projection.

Direct execution of this Hermes runtime probe succeeds. The failure occurs in the aggregate `read-model.py` layer.

## Durable multi-agent production evidence

Production database quick check is `ok`.

Registry:

1. `hermes` — role `operational_worker`, authority ceiling L3, enabled, assignable;
2. `specialist-worker-01` — role `specialist_worker`, authority ceiling L1, disabled, non-assignable.

The completed A6.8 durable handoff remains present:

```text
handoff_id = hof_ba25bd0fdfea401c9894d6520099b4cf
task_id = tsk_a68_082b86212fc944b0a45f6c43395cb6f1
correlation_id = hofcorr_7dba30f92f2c46188c435aaea55bde67
source_agent_id = hermes
target_agent_id = specialist-worker-01
required_authority = L1
state = accepted
handoff_approval_state = approved
```

Its lifecycle evidence contains:

1. Hermes `ASSIGNED`;
2. specialist `ASSIGNED` through the accepted handoff;
3. terminal `COMPLETED`.

This establishes a legitimate sequential ownership transfer, not duplicate simultaneous ownership.

## Presence surfaces

Hermes presence:

- source file `/var/lib/phil-ai-os/agent-presence/hermes.json`;
- observation type `authenticated_control_api_roundtrip`;
- Control API status `ok`;
- fresh during discovery.

Specialist presence:

- source file `/var/lib/phil-ai-os/agent-presence/specialist-worker-01.json`;
- dedicated Ed25519-signed envelope;
- public-key SHA-256 `95091d2cfd33d06f551a9071735fef10bb24f9f2d4ad29294bc949364a5a4e24`;
- payload identifies `specialist-worker-01`, L1, disabled, non-assignable;
- fresh during discovery.

A7 must verify the specialist signature rather than trusting caller-controlled identity text.

## Production governance state

Discovery revalidated:

- Control API image `phil-ai-os/control-api:0.21.1-phase22a68`;
- execution allowlist `general`;
- Control API health/readiness GREEN;
- Mission Control mutation methods `405`;
- no production mutation from A7.1/A7.1b;
- no registry mutation;
- no lifecycle mutation;
- no handoff mutation;
- no approval mutation;
- no execution call;
- no provider call;
- no authority expansion.

## A7 engineering implication

The minimum safe A7 change is a read-only replacement of the Mission Control read-model projection that:

- fixes the existing 503 defect;
- reads all registered agents instead of Hermes only;
- verifies identity-specific presence evidence;
- reconstructs lifecycle ownership across accepted handoffs;
- exposes durable handoff audit history;
- preserves legacy Hermes fields needed by the existing dashboard presentation;
- keeps Mission Control mutation methods blocked;
- does not change the Control API, registry, worker eligibility, handoff writer, execution boundary, provider credentials, or automatic-action policy.

## Marker

Diagnostic marker:

`PHIL_AI_OS_PHASE_2_2_A7_1B_DIAGNOSTIC_OK`

## Gate decision

**A7.1: GREEN / COMPLETE.** The existing Mission Control aggregate read model is fail-closed at HTTP `503` due to the identified `OPEN_STAGES` scope defect. A7.2/A7.3 may safely proceed toward a read-only multi-agent replacement.
