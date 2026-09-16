#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATTEMPT = ROOT / "ops/readiness/ruby-preproduction-final-screen-capture-attempt-2026-09-16.json"
CANDIDATE = ROOT / "ops/readiness/ruby-tokushoho-publication-candidate-2026-09-04.json"
ACTUAL_EVIDENCE = ROOT / "ops/readiness/ruby-actual-woocommerce-final-confirmation-screen-evidence-2026-09-16.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_PREPRODUCTION_FINAL_SCREEN_CAPTURE_ATTEMPT_FAILED: {message}")


def main() -> None:
    attempt = json.loads(ATTEMPT.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    evidence = json.loads(ACTUAL_EVIDENCE.read_text(encoding="utf-8"))

    result = attempt["capture_result"]
    dependency = attempt["sprint_dependency"]
    authority = attempt["authority"]
    acceptance = attempt["acceptance"]

    require(attempt["source_main_sha"] == "0e91c9b15a689d65a4c4c25e8db607b10adcbfd3", "capture source main SHA drift")

    require(result["attempted"] is True, "capture attempt must be recorded")
    require(result["target_environment"] == "preproduction", "capture target must remain preproduction")
    require(result["target_host"] == "darkgreen-wallaby-680439.hostingersite.com", "capture host drift")
    require(result["store_api_get_http_status"] == 200, "Store API GET did not succeed")
    require(result["products_returned"] == 1, "latest probe product count drift")
    require(result["purchasable_preproduction_product_found"] is True, "purchasable preproduction product evidence missing")
    require(result["checkout_reached"] is True, "actual checkout was not reached")
    require(result["final_action_reached"] is True, "final action was not reached")
    require(result["final_action_invoked"] is False, "final action must not be invoked")
    require(result["screen_evidence_captured"] is True, "sanitized screen evidence missing")
    require(result["redaction_applied"] is True, "capture redaction missing")
    require(len(result["sanitized_capture_sha256"]) == 64, "capture SHA-256 invalid")
    capture = ROOT / result["sanitized_capture_ref"]
    require(capture.is_file(), "sanitized capture artifact missing")
    require(hashlib.sha256(capture.read_bytes()).hexdigest() == result["sanitized_capture_sha256"], "sanitized capture digest drift")
    secondary_capture = ROOT / result["secondary_sanitized_capture_ref"]
    require(secondary_capture.is_file(), "secondary sanitized capture artifact missing")
    require(hashlib.sha256(secondary_capture.read_bytes()).hexdigest() == result["secondary_sanitized_capture_sha256"], "secondary sanitized capture digest drift")
    require(result["retained_personal_data"] is False, "PII retention is forbidden")
    require(result["retained_secret_material"] is False, "secret retention is forbidden")
    require(result["blocking_reason"] is None, "GREEN capture cannot retain a blocking reason")

    require(dependency["current_primary_sprint"] == 4, "Sprint 4 must remain current primary")
    require(dependency["sprint3_formally_closed_for_provisional_scope"] is True, "Sprint 3 provisional-scope closure drift")
    require(dependency["provisional_initial_launch_catalog_v1_approved"] is True, "provisional catalog approval drift")
    require(dependency["catalog_publication_facts_may_not_be_manufactured"] is True, "catalog fact boundary drift")
    require(dependency["actual_screen_capture_depends_on_preproduction_catalog_item"] is True, "catalog dependency must remain explicit")

    require(all(value is False for value in authority.values()), "capture attempt expanded authority")
    require(acceptance["actual_final_confirmation_screen_reviewed"] is True, "actual screen review evidence missing")
    require(acceptance["actual_final_confirmation_screen_green"] is True, "actual screen gate must record GREEN")
    require(acceptance["checkout_legal_sync_complete"] is True, "checkout legal sync must record completion")
    require(acceptance["failure_is_fail_closed"] is True, "fail-closed safeguard drift")

    screen = candidate["confirmation_screen"]
    require(screen["latest_capture_attempt_ref"] == "ops/readiness/ruby-preproduction-final-screen-capture-attempt-2026-09-16.json", "candidate attempt ref drift")
    require(screen["latest_capture_attempt_source_main_sha"] == attempt["source_main_sha"], "candidate source main SHA drift")
    require(screen["latest_capture_attempt_run_id"] is None, "read-only local probe must not claim a workflow run")
    require(screen["latest_store_api_get_http_status"] == 200, "candidate lost successful Store API GET status")
    require(screen["latest_products_returned"] == 1, "candidate product count drift")
    require(screen["latest_capture_attempted"] is True, "candidate lost capture attempt state")
    require(screen["latest_capture_blocked_before_checkout"] is False, "candidate incorrectly claims checkout remained unreachable")
    require(screen["actual_final_screen_reviewed"] is True, "candidate lost actual-screen review")
    require(screen["actual_final_screen_evidence_captured"] is True, "candidate lost sanitized screen evidence")
    require(screen["actual_final_screen_green"] is True, "actual screen GREEN state missing")
    require(screen["latest_actual_screen_evidence_ref"] == str(ACTUAL_EVIDENCE.relative_to(ROOT)), "candidate actual-evidence ref drift")

    require(evidence["evidence_complete"] is True, "actual evidence must be complete")
    require(evidence["actual_final_confirmation_screen_reviewed"] is True, "actual evidence lost review state")
    require(evidence["contains_personal_data"] is False and evidence["contains_secret_material"] is False, "actual evidence hygiene drift")
    require(all(evidence["observations"].values()), "actual evidence observations must all be GREEN")
    require(evidence["final_acceptance_window"]["acceptance_state"] == "GREEN", "final acceptance state drift")
    require(evidence["final_acceptance_window"]["order_approval_restored_after_review"] is True, "Order Approval was not restored")
    require(evidence["final_acceptance_window"]["order_created"] is False, "acceptance must not create an order")
    require(evidence["final_acceptance_window"]["payment_executed"] is False, "acceptance must not execute payment")
    roadmap = candidate["executive_roadmap"]
    require(roadmap["current_primary_sprint"] == 4, "candidate roadmap must keep Sprint 4 primary")
    require(roadmap["sprint3_formally_closed_for_provisional_scope"] is True, "candidate lost Sprint 3 closure")
    require(candidate["sprint3"]["formal_sprint3_closure"] is True, "Sprint 3 formal closure drift")
    require(candidate["sprint3"]["publication_catalog_content_complete"] is False, "publication content must remain pending")
    require(all(value is False for value in candidate["authority"].values()), "candidate authority expanded")

    print("PHIL_AI_OS_RUBY_PREPRODUCTION_FINAL_SCREEN_ACCEPTANCE_GREEN_NO_TRANSACTION")


if __name__ == "__main__":
    main()
