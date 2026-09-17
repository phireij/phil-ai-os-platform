#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/operations/launch-recovery-near-cutover-evidence.schema.json"
TEMPLATE = ROOT / "ops/readiness/ruby-launch-recovery-near-cutover-evidence.template.json"
GATE = ROOT / "ops/readiness/ruby-launch-recovery-acceptance-gate-2026-09-02.json"
SECURITY = ROOT / "ops/readiness/sprint7-security-recovery-readiness.json"

CHECK_KEYS = (
    "source_sqlite_quick_check_ok",
    "restored_sqlite_quick_check_ok",
    "row_counts_match",
    "backup_timer_active",
    "backup_monitor_active",
    "control_api_health_ok",
    "rollback_abort_path_confirmed",
)
AUTHORITY_KEYS = (
    "production_activation_authorized",
    "automatic_production_rollback_authorized",
    "automatic_production_retry_authorized",
    "dns_cutover_authorized",
    "payment_execution_authorized",
    "order_creation_authorized",
)
PENDING = "PENDING_NEAR_CUTOVER_RECHECK_FAIL_CLOSED"
GREEN = "NEAR_CUTOVER_RECOVERY_ACCEPTANCE_GREEN"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_SPRINT_7_LAUNCH_RECOVERY_EVIDENCE_FAILED: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_evidence(data: dict, *, expect_pending: bool | None = None) -> None:
    require(data.get("version") == "ruby-launch-recovery-near-cutover-evidence-v1", "evidence version drift")
    require(data.get("evidence_scope") == "near_cutover_recovery_recheck", "evidence scope drift")
    require(data.get("contains_secret_material") is False, "secret material must not be retained")

    checks = data.get("checks")
    require(isinstance(checks, dict), "checks object missing")
    require(set(checks) == set(CHECK_KEYS), "recovery check set drift")
    require(all(isinstance(checks[key], bool) for key in CHECK_KEYS), "recovery checks must be boolean")

    authority = data.get("authority")
    require(isinstance(authority, dict), "authority object missing")
    require(set(authority) == set(AUTHORITY_KEYS), "authority field set drift")
    for key in AUTHORITY_KEYS:
        require(authority[key] is False, f"authority expanded: {key}")

    evidence_refs = data.get("evidence_refs")
    require(isinstance(evidence_refs, list), "evidence_refs must be a list")
    require(all(isinstance(item, str) and item for item in evidence_refs), "evidence_refs must contain non-empty strings")
    require(len(evidence_refs) == len(set(evidence_refs)), "evidence_refs must be unique")

    green_prerequisites = (
        data.get("captured_at") is not None
        and isinstance(data.get("run_id"), int)
        and data["run_id"] > 0
        and data.get("near_cutover_window_confirmed") is True
        and all(checks[key] is True for key in CHECK_KEYS)
        and len(evidence_refs) > 0
    )
    evidence_complete = data.get("evidence_complete")
    acceptance_green = data.get("acceptance_green")
    require(isinstance(evidence_complete, bool), "evidence_complete must be boolean")
    require(isinstance(acceptance_green, bool), "acceptance_green must be boolean")

    if acceptance_green:
        require(green_prerequisites, "GREEN acceptance requires every near-cutover recovery prerequisite")
        require(evidence_complete is True, "GREEN acceptance requires complete evidence")
        require(data.get("decision") == GREEN, "GREEN acceptance decision drift")
    else:
        require(data.get("decision") == PENDING, "pending recovery evidence decision drift")
        require(evidence_complete is False, "pending recovery evidence cannot claim complete evidence")

    if evidence_complete:
        require(acceptance_green is True, "complete recovery evidence must resolve to GREEN acceptance")

    if expect_pending is True:
        require(data.get("captured_at") is None, "pending template cannot claim capture time")
        require(data.get("run_id") is None, "pending template cannot claim run id")
        require(data.get("near_cutover_window_confirmed") is False, "pending template cannot claim cutover timing")
        require(all(checks[key] is False for key in CHECK_KEYS), "pending template cannot pre-claim recovery checks")
        require(evidence_refs == [], "pending template cannot pre-claim evidence references")
        require(evidence_complete is False and acceptance_green is False, "pending template must remain fail-closed")


def validate_contract() -> None:
    schema = load(SCHEMA)
    template = load(TEMPLATE)
    gate = load(GATE)
    security = load(SECURITY)

    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "schema draft drift")
    require(schema.get("additionalProperties") is False, "schema must reject unknown top-level fields")
    required = set(schema.get("required") or [])
    for field in (
        "version",
        "evidence_scope",
        "captured_at",
        "run_id",
        "near_cutover_window_confirmed",
        "checks",
        "evidence_refs",
        "contains_secret_material",
        "authority",
        "evidence_complete",
        "acceptance_green",
        "decision",
    ):
        require(field in required, f"schema required field missing: {field}")

    props = schema.get("properties") or {}
    require(props.get("version", {}).get("const") == "ruby-launch-recovery-near-cutover-evidence-v1", "schema version const drift")
    require(props.get("evidence_scope", {}).get("const") == "near_cutover_recovery_recheck", "schema scope const drift")
    require(props.get("contains_secret_material", {}).get("const") is False, "schema must forbid secret material")
    schema_authority = props.get("authority", {}).get("properties") or {}
    for key in AUTHORITY_KEYS:
        require(schema_authority.get(key, {}).get("const") is False, f"schema authority expanded: {key}")

    validate_evidence(template, expect_pending=True)

    require(gate.get("version") == "ruby-launch-recovery-acceptance-gate-v1", "launch recovery gate version drift")
    contract = gate.get("near_cutover_evidence_contract")
    require(isinstance(contract, dict), "launch recovery evidence contract linkage missing")
    require(contract.get("status") == "contract_ready_execution_deferred_until_near_cutover", "recovery contract status drift")
    require(contract.get("schema_ref") == "contracts/operations/launch-recovery-near-cutover-evidence.schema.json", "recovery schema ref drift")
    require(contract.get("template_ref") == "ops/readiness/ruby-launch-recovery-near-cutover-evidence.template.json", "recovery template ref drift")
    require(contract.get("validator_ref") == "scripts/validate_sprint7_launch_recovery_evidence.py", "recovery validator ref drift")
    require(contract.get("historical_baseline_satisfies_contract") is False, "historical baseline cannot satisfy launch-fresh evidence")
    require(contract.get("fresh_execution_performed") is False, "near-cutover recovery execution was claimed prematurely")

    baseline = gate.get("current_baseline") or {}
    require(baseline.get("status") == "green_current_not_launch_fresh", "historical recovery baseline status drift")
    require(baseline.get("source_sqlite_quick_check") == "ok", "historical source quick_check regressed")
    require(baseline.get("restored_sqlite_quick_check") == "ok", "historical restore quick_check regressed")
    require(baseline.get("row_counts_match") is True, "historical restore row counts regressed")
    require(baseline.get("backup_timer_active") is True, "historical backup timer evidence regressed")
    require(baseline.get("backup_monitor_active") is True, "historical backup monitor evidence regressed")
    require(baseline.get("control_api_health") == "ok", "historical Control API health evidence regressed")

    launch = gate.get("launch_time_acceptance") or {}
    require(set(launch) == {"fresh_run_completed_near_cutover", *CHECK_KEYS}, "launch-time recovery field set drift")
    require(all(value is False for value in launch.values()), "launch-time recovery evidence must remain pending until a fresh cutover-window run")
    execution = gate.get("execution") or {}
    require(execution.get("current_baseline_can_authorize_cutover") is False, "historical baseline cannot authorize cutover")
    require(execution.get("launch_recovery_gate_green") is False, "launch recovery gate became GREEN without fresh evidence")
    require(execution.get("cutover_ready_from_recovery_perspective") is False, "recovery gate cannot permit cutover yet")
    require(gate.get("decision") == PENDING, "launch recovery gate decision drift")

    control = next((item for item in security.get("controls", []) if item.get("id") == "control-plane-backup-restore"), None)
    require(isinstance(control, dict), "security recovery control missing")
    require(control.get("status") == "historically_validated_launch_recheck_required", "security recovery timing status drift")
    requirement = str(control.get("launch_requirement", ""))
    require("immediately before production cutover" in requirement, "near-cutover timing safeguard missing")

    print("PHIL_AI_OS_SPRINT_7_LAUNCH_RECOVERY_EVIDENCE_CONTRACT_GREEN template=pending authority=false secrets=false")
    print("PHIL_AI_OS_SPRINT_7_LAUNCH_RECOVERY_RECHECK_DEFERRED_CORRECTLY near_cutover_required=true gate_green=false")


def self_test() -> None:
    base = load(TEMPLATE)
    good = copy.deepcopy(base)
    good.update({
        "captured_at": "2026-09-29T00:00:00Z",
        "run_id": 99999999999,
        "near_cutover_window_confirmed": True,
        "evidence_refs": ["synthetic:self-test/recovery-run"],
        "evidence_complete": True,
        "acceptance_green": True,
        "decision": GREEN,
    })
    for key in CHECK_KEYS:
        good["checks"][key] = True
    validate_evidence(good)

    partial = copy.deepcopy(good)
    partial["checks"]["restored_sqlite_quick_check_ok"] = False
    try:
        validate_evidence(partial)
    except SystemExit:
        pass
    else:
        fail("self-test accepted incomplete restore evidence")

    authority_drift = copy.deepcopy(good)
    authority_drift["authority"]["production_activation_authorized"] = True
    try:
        validate_evidence(authority_drift)
    except SystemExit:
        pass
    else:
        fail("self-test accepted expanded production authority")

    print("PHIL_AI_OS_SPRINT_7_LAUNCH_RECOVERY_EVIDENCE_SELF_TEST_GREEN")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, help="Validate a populated near-cutover recovery evidence file")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    validate_contract()
    if args.self_test:
        self_test()
    if args.evidence is not None:
        validate_evidence(load(args.evidence.resolve()))
        print(f"PHIL_AI_OS_SPRINT_7_LAUNCH_RECOVERY_EVIDENCE_FILE_GREEN path={args.evidence}")


if __name__ == "__main__":
    main()
