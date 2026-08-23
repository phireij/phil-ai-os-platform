# Phase 1.16 — Operational Alerting + Automated Safety Monitoring

**Status:** STARTED

## Objective

Add automated detection and operator-visible alerting for safety, audit, approval, provider-routing, usage-accounting, and runtime-health degradation without expanding autonomous execution authority.

## Safety posture

The production-safe defaults remain unchanged:

```text
PHIL_AI_OS_ROUTED_EXECUTION_ENABLED=false
PHIL_AI_OS_EXECUTION_KILL_SWITCH=true
PHIL_AI_OS_EXECUTION_SIMULATE_PRIMARY_FAILURE=false
PHIL_AI_OS_LIVE_TEST_ENABLED=false
```

## Planned controls

1. Deterministic safety-monitor checks over existing Control API state.
2. Severity classification (`info`, `warning`, `critical`).
3. Durable alert/event records with deduplication and timestamps.
4. Detection of audit-consistency failures and approval/execution anomalies.
5. Detection of provider-routing or usage-accounting anomalies.
6. Mission Control read-only alert visibility.
7. Operator notification path for critical alerts.
8. Recovery/clear semantics that preserve alert history.
9. Zero-provider-usage monitoring path.
10. Regression validation proving monitoring cannot execute tasks or bypass approval policy.

## Acceptance gate

Phase 1.16 is complete only after the monitoring path is validated against controlled fault cases and the final safety/audit consistency checks remain clean.
