# AO-MVP Persistent Service Boundary — Phase 0 Acceptance

Status: DEVELOPMENT-BRANCH CONTRACT ONLY

The AO-MVP now has deterministic contracts for recurring cadence, single-worker lease exclusion, heartbeat/crash recovery, durable dispatch replay protection, persistent per-work lifecycle state, independent verification, and non-authorizing approval escalation.

This does **not** mean a continuously running production service is deployed. No daemon, VPS service, provider executor, production mutation adapter, live customer messaging, payment/order execution, PR merge, DNS change, or KCFC production action is authorized by this acceptance.

## Fail-closed invariants
- A1 capability allowlist and explicit denylist remain authoritative.
- Scheduler decisions never grant execution authority.
- A lease prevents concurrent service workers; expired leases may be recovered.
- Durable dispatch IDs prevent duplicate simulated dispatch after restart.
- Terminal work records are immutable.
- Unknown/failed adapter evidence cannot become verified success.
- Escalation cannot approve itself or widen authority.
- Mission Control remains read-only.

## Next gate
Moving from development-branch service contracts to an actually hosted recurring orchestrator requires a separate runtime/deployment plan and evidence for persistence, secrets isolation, observability, restart behavior, and rollback. Production/provider mutations remain separately gated.
