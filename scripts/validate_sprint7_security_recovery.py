#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "ops/readiness/sprint7-security-recovery-readiness.json"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_SPRINT_7_SECURITY_RECOVERY_FAILED: {message}")


def main() -> None:
    data = json.loads(READINESS.read_text(encoding="utf-8"))
    baseline = data["authority_baseline"]

    expected = {
        "autonomy": "A0",
        "task_class_allowlist": ["general"],
        "assigned_agent": "hermes",
        "specialists_enabled": False,
        "mission_control_mutation_authorized": False,
        "production_activation_authorized": False,
        "automatic_production_retry_authorized": False,
        "automatic_production_rollback_authorized": False,
    }
    for key, value in expected.items():
        if baseline.get(key) != value:
            fail(f"authority baseline drift: {key}={baseline.get(key)!r}")

    required_controls = {
        "control-plane-backup-restore",
        "approval-replay-protection",
        "execution-boundary-default-deny",
        "woocommerce-credential-boundary",
        "production-secret-handling",
        "rollback-abort-governance",
        "fail-closed-launch-blockers",
    }
    controls = {item["id"]: item for item in data["controls"]}
    missing = required_controls - controls.keys()
    if missing:
        fail(f"missing controls: {sorted(missing)}")

    allowed_status = {
        "historically_validated_launch_recheck_required",
        "current_green",
        "plan_ready_activation_not_authorized",
        "active",
    }
    evidence_count = 0
    for control in controls.values():
        if control.get("status") not in allowed_status:
            fail(f"invalid status for {control['id']}: {control.get('status')}")
        evidence = control.get("evidence") or []
        if not evidence:
            fail(f"control lacks evidence: {control['id']}")
        for rel in evidence:
            path = ROOT / rel
            if not path.is_file():
                fail(f"missing evidence file: {rel}")
            evidence_count += 1
        if not control.get("launch_requirement"):
            fail(f"control lacks launch requirement: {control['id']}")

    blockers = data.get("launch_blockers") or []
    if len(blockers) < 6:
        fail("launch blocker set is incomplete")
    for blocker in blockers:
        if blocker.get("blocking") is not True:
            fail(f"launch blocker must remain fail-closed: {blocker.get('id')}")
        if not blocker.get("resolution"):
            fail(f"launch blocker lacks resolution: {blocker.get('id')}")

    markers = {
        "docs/SPRINT_7_SECURITY_RECOVERY_READINESS_MATRIX_2026-08-28.md": "PHIL_AI_OS_SPRINT_7_SECURITY_RECOVERY_READINESS_BOUNDED",
        "docs/SPRINT_7_PRODUCTION_SECRET_HANDLING_PLAN_2026-08-28.md": "PHIL_AI_OS_SPRINT_7_SECRET_HANDLING_PLAN_READY_NOT_AUTHORIZED",
        "docs/SPRINT_7_ROLLBACK_ABORT_MATRIX_2026-08-28.md": "PHIL_AI_OS_SPRINT_7_ROLLBACK_ABORT_MATRIX_READY_NOT_AUTHORIZED",
    }
    for rel, marker in markers.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        if marker not in text:
            fail(f"missing readiness marker in {rel}")

    phase117 = (ROOT / "docs/PHASE_1_17_IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    for historical_marker in (
        "PHIL_AI_OS_PHASE_1_17_BACKUP_TIMER_ACTIVE",
        "PHIL_AI_OS_PHASE_1_17_ISOLATED_RESTORE_OK",
        "PHIL_AI_OS_PHASE_1_17_BACKUP_MONITOR_OK",
    ):
        if historical_marker not in phase117:
            fail(f"missing Phase 1.17 evidence marker: {historical_marker}")

    sprint6 = (ROOT / "docs/SPRINT_6_FORMAL_CLOSURE_2026-08-28.md").read_text(encoding="utf-8")
    if "one-time approval decision/replay protection" not in sprint6:
        fail("Sprint 6 replay-protection evidence missing")
    if "zero automatic execution/reply/mutation/retry/rollback authority" not in sprint6:
        fail("Sprint 6 zero-authority evidence missing")

    print(
        "PHIL_AI_OS_SPRINT_7_SECURITY_RECOVERY_GREEN "
        f"controls={len(controls)} blockers={len(blockers)} evidence_refs={evidence_count}"
    )
    print(
        "PHIL_AI_OS_SPRINT_7_LAUNCH_AUTHORITY_BOUNDARY_GREEN "
        "production_activation=false autonomy=A0 task_class=general assigned_agent=hermes"
    )


if __name__ == "__main__":
    main()
