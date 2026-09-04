#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATTEMPT = ROOT / "ops/readiness/ruby-preproduction-final-screen-capture-attempt-2026-09-04.json"
CANDIDATE = ROOT / "ops/readiness/ruby-tokushoho-publication-candidate-2026-09-04.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_PREPRODUCTION_FINAL_SCREEN_CAPTURE_ATTEMPT_FAILED: {message}")


def main() -> None:
    attempt = json.loads(ATTEMPT.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))

    workflow = attempt["workflow"]
    result = attempt["capture_result"]
    dependency = attempt["sprint_dependency"]
    authority = attempt["authority"]
    acceptance = attempt["acceptance"]

    require(workflow["run_id"] == 33826576950, "unexpected workflow run id")
    require(workflow["head_branch"] == "main", "capture attempt was not run from main")
    require(workflow["head_sha"] == "c4d229c0930b3288f94fee8b53c1186ab7edea34", "capture attempt head SHA drift")
    require(workflow["failure_stage"] == "product_discovery_before_checkout", "unexpected failure stage")

    require(result["attempted"] is True, "capture attempt must be recorded")
    require(result["target_environment"] == "preproduction", "capture target must remain preproduction")
    require(result["target_host"] == "darkgreen-wallaby-680439.hostingersite.com", "capture host drift")
    require(result["purchasable_preproduction_product_found"] is False, "blocker record must remain fail-closed")
    require(result["checkout_reached"] is False, "blocked attempt cannot claim checkout reached")
    require(result["final_action_reached"] is False, "blocked attempt cannot claim final action reached")
    require(result["final_action_invoked"] is False, "final action must not be invoked")
    require(result["screen_evidence_captured"] is False, "blocked attempt cannot claim captured screen evidence")
    require(result["artifact_uploaded"] is False, "blocked attempt cannot claim an uploaded artifact")
    require(result["retained_personal_data"] is False, "PII retention is forbidden")
    require(result["retained_secret_material"] is False, "secret retention is forbidden")
    require(result["blocking_reason"] == "no_purchasable_preproduction_product_available_for_disposable_qa_cart", "blocking reason drift")

    require(dependency["current_primary_sprint"] == 3, "Sprint 3 must remain current primary")
    require(dependency["sprint4_parallel_acceleration"] is True, "Sprint 4 bounded parallel acceleration drift")
    require(dependency["formal_sprint4_entry"] is False, "formal Sprint 4 entry must remain false")
    require(dependency["final_owner_approved_production_catalog_ready"] is False, "final catalog must remain pending")
    require(dependency["actual_screen_capture_depends_on_preproduction_catalog_item"] is True, "catalog dependency must remain explicit")

    require(all(value is False for value in authority.values()), "capture attempt expanded authority")
    require(acceptance["actual_final_confirmation_screen_reviewed"] is False, "actual screen review must remain pending")
    require(acceptance["actual_final_confirmation_screen_green"] is False, "actual screen gate cannot be green")
    require(acceptance["checkout_legal_sync_complete"] is False, "checkout legal sync cannot be complete")
    require(acceptance["failure_is_fail_closed"] is True, "failed capture must remain classified fail-closed")

    screen = candidate["confirmation_screen"]
    require(screen["latest_capture_attempt_ref"] == "ops/readiness/ruby-preproduction-final-screen-capture-attempt-2026-09-04.json", "candidate attempt ref drift")
    require(screen["latest_capture_attempt_run_id"] == 33826576950, "candidate run id drift")
    require(screen["latest_capture_attempted"] is True, "candidate lost capture attempt state")
    require(screen["latest_capture_blocked_before_checkout"] is True, "candidate lost fail-closed blocker")
    require(screen["actual_final_screen_reviewed"] is False, "candidate cannot close actual-screen gate")
    require(screen["actual_final_screen_evidence_captured"] is False, "candidate cannot claim evidence")
    require(candidate["sprint3"]["final_owner_approved_production_catalog_ready"] is False, "Sprint 3 final catalog must remain pending")
    require(all(value is False for value in candidate["authority"].values()), "candidate authority expanded")

    print("PHIL_AI_OS_RUBY_PREPRODUCTION_FINAL_SCREEN_CAPTURE_ATTEMPT_RECORDED_GREEN")
    print("PHIL_AI_OS_RUBY_PREPRODUCTION_FINAL_SCREEN_CAPTURE_BLOCKED_NO_PRODUCT_FAIL_CLOSED")


if __name__ == "__main__":
    main()
