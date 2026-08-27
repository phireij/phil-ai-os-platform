# Phase 2.1M M2 — Isolated Presence Contract Result

Status: **GREEN / M3 AUTHORIZED**

Date: 2026-08-27

## Run

- Workflow: `Phase 2.1M M2 Isolated Presence Contract`
- Run: `33073154085`
- Job: `98520349036`
- Result: success

## Validated semantics

Freshness thresholds used by the contract:

- heartbeat age <= 120s: `fresh`
- heartbeat age >120s and <=300s: `stale`
- heartbeat age >300s: `offline`
- no heartbeat ever: `unknown`

These are logical-presence classifications only.

## Separation of signals

The isolated validation proved that the operator read model must preserve four independent dimensions:

1. registry state (`enabled` / disabled and assignability);
2. runtime liveness (`running` / stopped);
3. logical presence (`fresh`, `stale`, `offline`, `unknown`) derived only from explicit heartbeat observation;
4. workload derived from durable latest task lifecycle state.

A running container with no heartbeat correctly remains `unknown`.

A stopped runtime with a recent heartbeat retains the heartbeat-derived presence classification while separately reporting runtime stopped. This prevents one signal from silently overwriting another.

## No-authority semantics

For every tested state:

- authority effect: none
- automatic reroute: false
- automatic retry: false
- automatic delegation: false
- automatic execution: false

Presence cannot override registry `enabled`, `assignable`, or authority ceiling.

## Workload contract

Active workload is derived from the latest durable lifecycle state per task assigned to the agent, excluding terminal/audit-closed states. It is an observational count only and cannot change scheduling or authority.

## Decision

M2 is GREEN. Proceed to **M3 production preflight** to identify the smallest additive, rollback-safe heartbeat observation and Mission Control read-model insertion points.

No production change is authorized by this result.

`PHIL_AI_OS_PHASE_2_1M_M2_CONTRACT_GREEN_M3_AUTHORIZED`
