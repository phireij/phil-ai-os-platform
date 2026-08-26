# Phase 1.22 — Monitoring Gap Decision

Status: **REMEDIATION REQUIRED BEFORE ROUTINE ACTIVATION**  
Date: 2026-08-26

## Evidence reviewed

GitHub Actions run `32924513075` completed successfully and proved the monitoring process itself is installed and running:

- `phil-ai-os-monitor.service`: enabled and active/running.
- `Result=success`, `ExecMainStatus=0`, `NRestarts=0`.
- Monitor process is present.
- Telegram notifier implementation is configured through the monitor environment.
- Control API contains durable approval/execution integrity checks.
- Production execution allowlist remains `general` only.
- Validation made no provider call and no production change.

## Gap decision

**Monitoring is operational, but its safety expectations are stale relative to the current governed execution architecture. Phase 1.22 routine activation must remain blocked until this is reconciled.**

Recent monitor logs repeatedly report three failures:

1. `execution_kill_switch`: monitor expects `true`, while the governed execution baseline intentionally has the kill switch available but not engaged (`false`).
2. `routed_execution_enabled`: monitor expects `false`, while routed execution is now intentionally enabled as the controlled execution boundary.
3. `backup_status`: the monitor reports the latest backup status as stale relative to its configured maximum age.

The first two are configuration/policy expectation drift caused by the platform progressing beyond the Phase 1.16 safety baseline. They should not be silenced blindly; the monitor must be updated to validate the current intended state instead.

The backup finding requires reconciliation with the already-installed backup timer and backup self-heal path. We must determine whether the status file consumed by the monitor is stale despite successful scheduled backups, or whether backup freshness genuinely needs remediation.

## Required remediation

Before the Phase 1.22 no-provider negative-path suite and pre-activation gate can be considered sufficient:

- Update the monitor's expected governed state to reflect the current intentional execution architecture: routed execution enabled, emergency kill switch available but normally not engaged, live-test gate disabled, and production task allowlist constrained.
- Preserve fail-closed alerting for unexpected changes rather than removing the checks.
- Reconcile backup freshness/status-file production with the active backup and self-heal timers.
- Validate monitor recovery after remediation and confirm no persistent false safety alerts remain.
- Confirm Telegram alert/recovery behavior remains intact.

## Activation boundary

No `routine` production activation is authorized by this decision.

Production remains `PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=general`.

## Next action

Run **Phase 1.22 Monitoring Baseline & Backup Freshness Reconciliation**. This should first discover the exact monitor environment and backup status producer/consumer relationship, then apply only the minimum evidence-backed configuration/code change required.

`PHIL_AI_OS_PHASE_1_22_MONITORING_GAP_DECISION_REMEDIATION_REQUIRED`
