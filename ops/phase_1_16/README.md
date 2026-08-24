# Phase 1.16 — Operational Alerting + Automated Safety Monitoring

This directory contains the first implementation of the Phil AI OS read-only operational safety monitor.

## Safety posture

The monitor is intentionally non-authoritative:

- it performs HTTP GET checks only against Phil AI OS;
- it does not approve, deny, consume, or execute tasks;
- it does not change routing flags or the execution kill switch;
- it does not poll Telegram or own a Telegram webhook;
- Telegram is outbound notification only;
- alert state is local and contains no provider credentials.

## Checks

Always enabled:

- Control API `/healthz`
- Control API `/readyz`

Optional safety snapshot checks, enabled only when `PHIL_AI_OS_SAFETY_SNAPSHOT_URL` is configured:

- audit consistency must be `CONSISTENT`
- audit issues must be `0`
- audit integrity must be `PASS`
- unknown approval links must be `0`
- multiple successes per approval must be `0`
- execution kill switch must be enabled
- routed execution must remain disabled
- live test must remain disabled

The snapshot evaluator accepts snake_case and camelCase variants for those fields. Strict mode treats absent safety fields as failures.

## Alert behavior

Alerts are sent on a healthy → unhealthy transition. Persistent failures are re-alerted after the configured cooldown (default 30 minutes). A recovery notification is sent when a failed check becomes healthy again.

If Telegram credentials are not configured, notifications are printed to stdout, which makes initial validation possible without sending messages.

## Local validation

```bash
cd ops/phase_1_16
python3 -m unittest -v
python3 monitor.py --print-config
python3 monitor.py --once
```

The implementation uses only the Python standard library.

## Deployment preparation

1. Copy `.env.example` to an operator-managed secret environment file outside the Git repository.
2. Reuse the existing Hermes Telegram bot token only for outbound `sendMessage`; do not create another poller/webhook owner.
3. Set the correct Telegram chat ID.
4. Confirm the deployed authenticated Control API safety/snapshot endpoint before setting `PHIL_AI_OS_SAFETY_SNAPSHOT_URL`.
5. Run `monitor.py --once` and confirm the expected safe result before enabling continuous monitoring.
6. Persist `/var/lib/phil-ai-os-monitor/state.json` so alert deduplication survives restarts.

## Required safety snapshot contract

The configured JSON endpoint should expose the following effective values while the Phase 1 maximum-safe posture is active:

```json
{
  "audit_consistency": "CONSISTENT",
  "audit_issues": 0,
  "audit_integrity": "PASS",
  "unknown_approval_links": 0,
  "multiple_successes_per_approval": 0,
  "execution_kill_switch": true,
  "routed_execution_enabled": false,
  "live_test_enabled": false
}
```

It may contain additional fields; they are ignored by this monitor.

## Current implementation status

Repository implementation is complete and unit-tested locally. Deployment validation against the live VPS Control API and Telegram channel is still required before Phase 1.16 can be marked COMPLETE.
