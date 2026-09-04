#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "ops/readiness/ruby-isolated-final-confirmation-preview-2026-09-04.json"
CANDIDATE = ROOT / "ops/readiness/ruby-tokushoho-publication-candidate-2026-09-04.json"
HTML = ROOT / "apps/customer-experience/confirmation-preview.html"
MODULE = ROOT / "apps/customer-experience/src/confirmation-preview.mjs"
FIXTURE = ROOT / "apps/customer-experience/fixtures/final-confirmation.json"
TEST = ROOT / "apps/customer-experience/tests/confirmation-preview.test.mjs"
CX_VALIDATOR = ROOT / "apps/customer-experience/tools_validate_cx.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_ISOLATED_CONFIRMATION_PREVIEW_FAILED: {message}")


def main() -> None:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    require(record.get("version") == "ruby-isolated-final-confirmation-preview-v1", "readiness schema drift")
    executive = record["executive_roadmap"]
    require(executive["current_primary_sprint"] == 3, "Sprint 3 must remain current primary")
    require(executive["sprint4_parallel_acceleration"] is True, "Sprint 4 parallel acceleration missing")
    require(executive["formal_sprint4_entry"] is False, "formal Sprint 4 entry must remain false")

    preview = record["isolated_preview"]
    for key in (
        "green",
        "fixture_only",
        "preview_only",
        "pwa_offline_shell_integrated",
        "bilingual_en_ja",
        "disabled_final_order_control",
        "approved_payment_subset_enforced",
        "japan_2026_tax_exempt_posture_enforced",
        "cancellation_timing_policy_enforced",
    ):
        require(preview[key] is True, f"isolated preview regressed: {key}")
    require(preview["konbini_live_expiry_days_enforced"] == 3, "Konbini expiry enforcement drift")
    require(preview["yamato_cool_kanto_rate_jpy_enforced"] == 1350, "Kanto shipping enforcement drift")

    refs = {
        "html_ref": HTML,
        "module_ref": MODULE,
        "fixture_ref": FIXTURE,
        "test_ref": TEST,
        "static_validator_ref": CX_VALIDATOR,
    }
    for key, path in refs.items():
        require(preview[key] == str(path.relative_to(ROOT)).replace("\\", "/"), f"preview reference drift: {key}")
        require(path.is_file(), f"missing preview evidence file: {path.relative_to(ROOT)}")

    ci = record["ci_evidence"]
    require(ci["sprint4_customer_experience_run_id"] == 33813388111 and ci["sprint4_customer_experience_green"] is True, "Sprint 4 CI evidence drift")
    require(ci["integrated_readiness_run_id"] == 33813388104 and ci["integrated_readiness_green"] is True, "integrated CI evidence drift")
    require(ci["workflow_supply_chain_run_id"] == 33813388099 and ci["workflow_supply_chain_green"] is True, "supply-chain CI evidence drift")

    actual = record["actual_woocommerce_screen"]
    require(actual["reviewed"] is False, "isolated preview cannot claim actual WooCommerce screen review")
    require(actual["evidence_captured"] is False, "actual WooCommerce screen evidence cannot be invented")
    require(actual["satisfied_by_isolated_preview"] is False, "isolated preview cannot satisfy actual-screen gate")
    require(actual["real_order_required"] is False, "real order must not be required for review")
    require(actual["real_payment_required"] is False, "real payment must not be required for review")

    for key, value in record["authority"].items():
        require(value is False, f"authority expanded unexpectedly: {key}")

    screen = candidate["confirmation_screen"]
    require(screen["isolated_final_confirmation_preview_green"] is True, "candidate record lost isolated preview GREEN")
    require(screen["isolated_final_confirmation_preview_evidence_ref"] == "ops/readiness/ruby-isolated-final-confirmation-preview-2026-09-04.json", "candidate evidence ref drift")
    require(screen["isolated_preview_satisfies_actual_screen_gate"] is False, "candidate incorrectly treats isolated preview as actual evidence")
    require(screen["actual_final_screen_reviewed"] is False, "actual final screen unexpectedly GREEN")
    require(screen["actual_final_screen_evidence_captured"] is False, "actual screen evidence unexpectedly captured")
    require(screen["latest_capture_attempted"] is True, "candidate must retain the latest actual-screen capture attempt")
    require(screen["latest_capture_blocked_before_checkout"] is True, "candidate must retain fail-closed capture blocker")
    require(candidate["sprint3"]["formal_sprint3_closure"] is False, "Sprint 3 closed without final catalog")
    for key, value in candidate["authority"].items():
        require(value is False, f"candidate authority expanded unexpectedly: {key}")

    expected_fixture_boundary = {
        "fixture_only": True,
        "preview_only": True,
        "actual_final_confirmation_screen_reviewed": False,
        "order_creation_authorized": False,
        "mutation_authorized": False,
        "payment_execution_authorized": False,
        "production_publish_authorized": False,
    }
    for key, expected in expected_fixture_boundary.items():
        require(fixture.get(key) == expected, f"fixture authority/boundary drift: {key}")
    require(fixture["pricing"]["consumption_tax_status"] == "exempt", "fixture tax status drift")
    require(fixture["pricing"]["woocommerce_tax_enabled"] is False, "fixture unexpectedly enables tax")
    require(fixture["payment"]["method"] == "konbini" and fixture["payment"]["expiry_days"] == 3, "fixture Konbini evidence drift")

    html = HTML.read_text(encoding="utf-8")
    for phrase in (
        "No order submission",
        "Place order (preview only — disabled)",
        "This is not the actual WooCommerce final screen",
    ):
        require(phrase in html, f"preview safety marker missing: {phrase}")

    module = MODULE.read_text(encoding="utf-8")
    for phrase in (
        "isolated preview cannot claim actual final-screen acceptance",
        "order_creation_authorized",
        "payment_execution_authorized",
        "production_publish_authorized",
        "verified 3-day Live expiry",
    ):
        require(phrase in module, f"preview module safeguard missing: {phrase}")

    require(record["decision"] == "ISOLATED_FINAL_CONFIRMATION_PREVIEW_GREEN_ACTUAL_WOOCOMMERCE_SCREEN_PENDING_FAIL_CLOSED", "readiness decision drift")
    require(candidate["decision"] == "TOKUSHOHO_CANDIDATE_GREEN_ACTUAL_SCREEN_CAPTURE_BLOCKED_BY_PREPRODUCTION_CATALOG_FAIL_CLOSED", "candidate decision drift")

    print("PHIL_AI_OS_ISOLATED_FINAL_CONFIRMATION_PREVIEW_GREEN actual_woocommerce_screen=false order_creation=false payment_execution=false")
    print("PHIL_AI_OS_ACTUAL_WOOCOMMERCE_CONFIRMATION_SCREEN_PENDING_FAIL_CLOSED")


if __name__ == "__main__":
    main()
