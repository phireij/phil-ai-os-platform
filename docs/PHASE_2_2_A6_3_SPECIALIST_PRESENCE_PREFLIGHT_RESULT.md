# Phil AI OS Platform — Phase 2.2 A6.3 Specialist Presence Production Preflight Result

**Phase:** 2.2 A6.3 — Specialist Presence Production Preflight  
**Status:** GREEN / COMPLETE  
**Date:** 2026-08-28  
**Workflow run:** `33141612181`  
**Evidence artifact:** `phase-2-2-a6-3-specialist-presence-preflight-evidence`

## Decision

A6.3 is GREEN. A specialist logical-presence primitive can be introduced without a database schema change or registry mutation, but it must be identity-specific and isolated from the existing Hermes heartbeat. A6.4 remains a separately approved production runtime activation.

## Existing Hermes presence implementation

Read-only structural inspection proved:

- heartbeat executable: `/usr/local/sbin/philaios-agent-heartbeat`;
- literal Hermes references: `5`;
- explicit Hermes container reference: `hermes-agent-whow`;
- Mission Control client usage: present;
- provider references: none;
- `/v1/execute` / execution-client references: none;
- Hermes Mission Control token file mode: `0400`;
- Hermes token file owner: `hermes:hermes`;
- Mission Control runtime read model is present and currently contains Hermes-specific logic (`9` literal Hermes references, `0` specialist references).

The existing Hermes heartbeat and read-model logic therefore cannot be treated as generic second-worker identity evidence by relabeling.

## Authentication-boundary finding

Control API source inspection confirmed the governed `/v1/execute` route has authentication-related logic. A6.3 did **not** prove that the current Hermes Control API credential is a distinct presence-only credential or that it can safely identify a second worker.

Therefore the specialist presence design MUST NOT simply reuse Hermes identity context and supply a different caller-controlled `agent_id`.

Before A6.4 activation, the specialist observation mechanism must provide identity-specific attribution through a separate least-privilege credential/context or another independently attributable mechanism that cannot be confused with Hermes.

## Available production namespace

No collisions were found for the proposed specialist presence units:

- `phil-ai-os-specialist-worker-01-presence.service`
- `phil-ai-os-specialist-worker-01-presence.timer`
- `phil-ai-os-specialist-worker-01.service`

The specialist evidence path is also available:

`/var/lib/phil-ai-os/agent-presence/specialist-worker-01.json`

The existing presence directory is present and usable as the parent evidence surface.

## Registry and assignment state

Production registry remains exactly:

1. `hermes` — L3, enabled, assignable;
2. `specialist-worker-01` — L1, disabled, non-assignable.

Specialist lifecycle assignment references remain `0`.

## Minimum A6.4 boundary

A6.4 requires no database schema change and no registry change. If separately authorized, it may introduce only:

- one identity-specific, presence-only specialist observation implementation;
- one isolated specialist presence service/timer;
- one isolated specialist presence evidence file;
- the minimum identity-attribution secret/context required for authenticated presence, provided it cannot grant execution/provider/approval/coordinator-write authority.

A6.4 MUST preserve:

- specialist `enabled=false`;
- specialist `assignable=false`;
- specialist authority ceiling `L1`;
- no provider credentials;
- no execution capability;
- existing Hermes heartbeat unchanged;
- production execution allowlist `general` only;
- Mission Control mutation methods `405`.

## Safety verification

- Control API health/readiness: GREEN
- monitor/backups/self-heal: active
- execution allowlist: `general`
- Mission Control mutations: `405`
- production change: none
- service restart: none
- registry mutation: none
- lifecycle mutation: none
- approval mutation: none
- execution call: none
- provider call: none
- authority expansion: none

Marker: `PHIL_AI_OS_PHASE_2_2_A6_3_SPECIALIST_PRESENCE_PREFLIGHT_OK`

## Gate decision

**A6.3: GREEN / COMPLETE. A6.4 is technically prepared but remains BLOCKED pending explicit CEO approval.**

A6.5/A6.6 handoff persistence/writer preparation may continue independently and read-only/isolated while A6.4 remains blocked.
