#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATTEMPT = ROOT / "ops/readiness/ruby-preproduction-final-screen-capture-attempt-2026-09-16.json"
CANDIDATE = ROOT / "ops/readiness/ruby-tokushoho-publication-candidate-2026-09-04.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_PREPRODUCTION_FINAL_SCREEN_CAPTURE_ATTEMPT_FAILED: {message}")


def main() -> None:
    attempt = json.loads(ATTEMPT.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))

    result = attempt["capture_result"]
    dependency = attempt["sprint_dependency"]
    authority = attempt["authority"]
    acceptance = attempt["acceptance"]

    require(attempt["source_main_sha"] == "0e91c9b15a689d65a4c4c25e8db607b10adcbfd3", "capture source main SHA drift")

    require(result["attempted"] is True, "capture attempt must be recorded")
    require(result["target_environment"] == "preproduction", "capture target must remain preproduction")
    require(result["target_host"] == "darkgreen-wallaby-680439.hostingersite.com", "capture host drift")
    require(result["store_api_get_http_status"] == 200, "Store API GET did not succeed")
    require(result["products_returned"] == 0, "latest probe product count drift")
    require(result["purchasable_preproduction_product_found"] is False, "blocker record must remain fail-closed")
    require(result["checkout_reached"] is False, "blocked attempt cannot claim checkout reached")
    require(result["final_action_reached"] is False, "blocked attempt cannot claim final action reached")
    require(result["final_action_invoked"] is False, "final action must not be invoked")
    require(result["screen_evidence_captured"] is False, "blocked attempt cannot claim captured screen evidence")
    require(result["retained_personal_data"] is False, "PII retention is forbidden")
    require(result["retained_secret_material"] is False, "secret retention is forbidden")
    require(result["blocking_reason"] == "no_purchasable_preproduction_product_available_for_disposable_qa_cart", "blocking reason drift")

    require(dependency["current_primary_sprint"] == 4, "Sprint 4 must remain current primary")
    require(dependency["sprint3_formally_closed_for_provisional_scope"] is True, "Sprint 3 provisional-scope closure drift")
    require(dependency["provisional_initial_launch_catalog_v1_approved"] is True, "provisional catalog approval drift")
    require(dependency["catalog_publication_facts_may_not_be_manufactured"] is True, "catalog fact boundary drift")
    require(dependency["actual_screen_capture_depends_on_preproduction_catalog_item"] is True, "catalog dependency must remain explicit")

    require(all(value is False for value in authority.values()), "capture attempt expanded authority")
    require(acceptance["actual_final_confirmation_screen_reviewed"] is False, "actual screen review must remain pending")
    require(acceptance["actual_final_confirmation_screen_green"] is False, "actual screen gate cannot be green")
    require(acceptance["checkout_legal_sync_complete"] is False, "checkout legal sync cannot be complete")
    require(acceptance["failure_is_fail_closed"] is True, "failed capture must remain classified fail-closed")

    screen = candidate["confirmation_screen"]
    require(screen["latest_capture_attempt_ref"] == "ops/readiness/ruby-preproduction-final-screen-capture-attempt-2026-09-16.json", "candidate attempt ref drift")
    require(screen["latest_capture_attempt_source_main_sha"] == attempt["source_main_sha"], "candidate source main SHA drift")
    require(screen["latest_capture_attempt_run_id"] is None, "read-only local probe must not claim a workflow run")
    require(screen["latest_store_api_get_http_status"] == 200, "candidate lost successful Store API GET status")
    require(screen["latest_products_returned"] == 0, "candidate product count drift")
    require(screen["latest_capture_attempted"] is True, "candidate lost capture attempt state")
    require(screen["latest_capture_blocked_before_checkout"] is True, "candidate lost fail-closed blocker")
    require(screen["actual_final_screen_reviewed"] is False, "candidate cannot close actual-screen gate")
    require(screen["actual_final_screen_evidence_captured"] is False, "candidate cannot claim evidence")
    roadmap = candidate["executive_roadmap"]
    require(roadmap["current_primary_sprint"] == 4, "candidate roadmap must keep Sprint 4 primary")
    require(roadmap["sprint3_formally_closed_for_provisional_scope"] is True, "candidate lost Sprint 3 closure")
    require(candidate["sprint3"]["formal_sprint3_closure"] is True, "Sprint 3 formal closure drift")
    require(candidate["sprint3"]["publication_catalog_content_complete"] is False, "publication content must remain pending")
    require(all(value is False for value in candidate["authority"].values()), "candidate authority expanded")

    print("PHIL_AI_OS_RUBY_PREPRODUCTION_FINAL_SCREEN_CAPTURE_ATTEMPT_RECORDED_GREEN")
    print("PHIL_AI_OS_RUBY_PREPRODUCTION_FINAL_SCREEN_CAPTURE_BLOCKED_NO_PRODUCT_FAIL_CLOSED")


if __name__ == "__main__":
    main()
