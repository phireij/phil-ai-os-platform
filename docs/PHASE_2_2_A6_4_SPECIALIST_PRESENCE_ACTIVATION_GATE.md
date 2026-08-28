# Phil AI OS Platform — Phase 2.2 A6.4 Specialist Presence Activation Gate

**Phase:** 2.2 A6.4 — Specialist Presence Activation  
**Status:** BLOCKED — EXPLICIT CEO APPROVAL REQUIRED  
**Prepared:** 2026-08-28  
**Production activation:** NOT AUTHORIZED

## Activation objective

Introduce only an identity-specific, non-executing logical-presence primitive for `specialist-worker-01` while leaving its registry state unchanged:

```text
authority_ceiling = L1
enabled = false
assignable = false
provider_credentials = none
execution_capability = none
```

A6.4 does not activate a usable worker and does not authorize handoff.

## Identity mechanism

A6.4 will use a dedicated **Ed25519 signing identity** for specialist presence rather than reusing Hermes's Control API token.

The presence service will:

1. run as a hardened systemd oneshot service on a timer;
2. make local read-only Control API `/healthz` and `/readyz` round-trips;
3. construct bounded non-secret presence evidence naming exactly `specialist-worker-01`;
4. sign the canonical evidence payload with a dedicated Ed25519 private key;
5. atomically publish the evidence file under the existing presence evidence directory;
6. expose only the public verification key to future readers.

This satisfies A6.2's independently attributable observation option without granting a Control API bearer token to the specialist presence runtime.

## Proposed production files

- `/usr/local/sbin/philaios-specialist-worker-01-presence`
- `/etc/phil-ai-os/specialist-worker-01/presence-private.pem` — mode 0400
- `/etc/phil-ai-os/specialist-worker-01/presence-public.pem` — public verifier
- `/etc/systemd/system/phil-ai-os-specialist-worker-01-presence.service`
- `/etc/systemd/system/phil-ai-os-specialist-worker-01-presence.timer`
- `/var/lib/phil-ai-os/agent-presence/specialist-worker-01.json`

## Evidence fields

The published JSON is bounded to fields equivalent to:

```text
schema_version = 2.2-a6.4.v1
agent_id = specialist-worker-01
observation_type = authenticated_signed_control_api_roundtrip
observed_at
status
control_api_health
control_api_readiness
nonce
signature_algorithm = ed25519
signature_b64
```

The signature is calculated over canonical JSON excluding `signature_b64`.

No token, secret, task text, prompt, provider response, host inventory, approval link, or credential is stored in the evidence.

## Runtime hardening

The service must have no provider or Control API bearer credentials and no Docker access. The systemd unit will use restrictive settings including:

- `NoNewPrivileges=true`
- `ProtectSystem=strict`
- `ProtectHome=true`
- `PrivateTmp=true`
- `PrivateDevices=true`
- `ProtectKernelTunables=true`
- `ProtectKernelModules=true`
- `ProtectControlGroups=true`
- empty capability bounding/ambient sets
- explicit writable path limited to the presence evidence directory
- explicit inaccessible paths covering Hermes/Control API token mounts and Docker socket paths

The service may make only the local health/readiness round-trip required for evidence.

## Activation invariants

Before mutation:

- A6.1–A6.3 must be GREEN;
- Control API health/readiness GREEN;
- Hermes heartbeat active and unchanged;
- specialist remains L1 disabled/non-assignable;
- specialist has zero assignment references;
- production allowlist exactly `general`;
- monitor/backups/self-heal active;
- proposed unit/file paths absent;
- Ed25519 support verified.

After mutation:

- specialist registry row is byte-for-byte/logically unchanged;
- lifecycle/plan/approval/execution-audit counts unchanged;
- specialist presence timer active;
- one current specialist evidence file exists;
- evidence signature verifies with the dedicated public key;
- evidence `agent_id` is exactly `specialist-worker-01`;
- evidence is fresh after controlled heartbeat execution;
- Hermes heartbeat executable/unit/evidence remain intact;
- no provider/execution/coordinator credentials are installed in the presence unit;
- no provider call or execution call occurs;
- Mission Control remains read-only;
- specialist remains `unassignable` by registry precedence.

## Rollback boundary

If any invariant fails:

1. disable/remove only the specialist presence timer/service;
2. delete the specialist presence executable, dedicated key directory, and specialist evidence file;
3. daemon-reload systemd;
4. verify no specialist service/timer remains;
5. reverify Hermes heartbeat, Control API, monitoring, backups, registry, lifecycle, approval, and execution counts;
6. do not modify the specialist A5 registry row unless separately authorized.

## Explicitly not authorized by A6.4

- enabling or making the specialist assignable;
- starting an AI/provider worker runtime;
- adding provider credentials;
- giving a Control API execution/coordinator bearer token to the presence service;
- creating `task_handoffs` in production;
- adding handoff routes in production;
- creating/approving/accepting a handoff;
- appending a specialist `ASSIGNED` event;
- provider execution;
- automatic assignment/retry/reroute/delegation/execution;
- Mission Control mutation.

## Approval boundary

**Do not execute A6.4 until the CEO explicitly authorizes specialist presence activation.**
