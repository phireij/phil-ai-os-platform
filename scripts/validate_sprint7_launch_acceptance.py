#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "ops/readiness/sprint7-launch-acceptance.json"
PROFILE = ROOT / "ops/readiness/verified-ruby-business-profile.template.json"
STAGING = ROOT / "ops/readiness/ruby-woocommerce-komoju-staging-readiness.json"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_SPRINT_7_LAUNCH_ACCEPTANCE_FAILED: {message}")


def main() -> None:
    data = json.loads(READINESS.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    staging = json.loads(STAGING.read_text(encoding="utf-8"))
    engineering = data["bounded_engineering_readiness"]
    live = data["live_launch_gates"]
    baseline = data["authority_baseline"]

    if engineering.get("integrated_regression_baseline_tests") != 165:
        fail("integrated regression baseline must remain 165")
    for key in (
        "security_recovery_package_ready",
        "deployment_migration_runbooks_ready",
        "channel_activation_runbooks_ready",
        "operator_documentation_ready",
        "final_current_head_ci_required",
    ):
        if engineering.get(key) is not True:
            fail(f"bounded engineering readiness flag drift: {key}")

    if live.get("verified_ruby_business_profile_complete") is not True:
        fail("verified Ruby Business Profile must remain complete")
    if profile.get("profile_complete") is not True:
        fail("launch profile gate must match canonical 15/15 profile")
    if live.get("contact_phone_verified") is not True:
        fail("contact phone verification must remain complete once recorded")
    phone = profile["contact_information"]["phone"]
    if phone.get("value") != "050-1785-0575" or phone.get("verification_status") != "verified":
        fail("launch gate phone verification must match the verified Ruby Business Profile")
    if live.get("tokushoho_source_reconciled") is not True:
        fail("Tokushoho source reconciliation must remain complete")

    required_live_false = (
        "tokushoho_publication_approved",
        "fresh_launch_time_backup_restore_check_green",
        "woocommerce_preproduction_qa_green",
        "woocommerce_production_activation_approved",
        "woocommerce_production_credentials_configured",
        "komoju_test_mode_validated",
        "komoju_live_mode_approved",
        "production_shipping_configuration_verified",
        "production_payment_methods_verified",
        "external_channel_live_activation_approved",
        "production_cutover_approved",
        "ceo_signoff_recorded",
        "cto_signoff_recorded",
    )
    for key in required_live_false:
        if live.get(key) is not False:
            fail(f"live launch gate must not be assumed complete: {key}")

    if staging["business_profile"].get("verified_profile_complete") is not True:
        fail("preproduction readiness profile state drift")
    if staging["business_profile"].get("tokushoho_source_reconciled") is not True:
        fail("preproduction readiness Tokushoho reconciliation drift")
    sfront = staging["storefront"]
    if sfront.get("parallel_preproduction_first_required") is not True:
        fail("parallel preproduction requirement drift")
    if sfront.get("parallel_preproduction_environment_created") is not False:
        fail("launch acceptance must not assume preproduction environment created")
    if sfront.get("native_hostinger_wordpress_staging_requires_existing_wordpress") is not True:
        fail("Hostinger native staging prerequisite drift")
    if staging["komoju"].get("test_mode_connected") is not False:
        fail("launch acceptance must not assume KOMOJU Test Mode connected")
    if staging.get("production_publish_authorized") is not False:
        fail("preproduction readiness gained publication authority")

    expected_baseline = {
        "autonomy": "A0",
        "task_class_allowlist": ["general"],
        "assigned_agent": "hermes",
        "specialists_enabled": False,
        "mission_control_mutation_authorized": False,
        "live_launch_authorized": False,
    }
    for key, value in expected_baseline.items():
        if baseline.get(key) != value:
            fail(f"authority baseline drift: {key}")

    for rel in data.get("evidence", []):
        if not (ROOT / rel).is_file():
            fail(f"missing launch-acceptance evidence file: {rel}")

    operator = (ROOT / "docs/SPRINT_7_OPERATOR_QUICK_START_2026-08-28.md").read_text(encoding="utf-8")
    if "PHIL_AI_OS_SPRINT_7_OPERATOR_GUIDE_READY" not in operator:
        fail("operator guide marker missing")
    if "does not automatically grant Operations Hub Telegram authority" not in operator:
        fail("operator guide Telegram authority separation missing")

    acceptance = (ROOT / "docs/SPRINT_7_LAUNCH_ACCEPTANCE_MATRIX_2026-08-28.md").read_text(encoding="utf-8")
    if "PHIL_AI_OS_SPRINT_7_LAUNCH_ACCEPTANCE_PACKAGE_READY_NOT_SIGNED" not in acceptance:
        fail("launch acceptance marker missing")
    for phrase in (
        "Ruby business profile | **COMPLETE — 15/15 RESOLVED**",
        "Contact phone | **VERIFIED — 050-1785-0575**",
        "Tokushoho source | **RECONCILED / PUBLICATION APPROVAL PENDING**",
        "WooCommerce pre-production QA | **NOT YET GREEN**",
        "KOMOJU Test Mode | **NOT VALIDATED**",
        "CEO sign-off | **NOT RECORDED**",
        "CTO sign-off | **NOT RECORDED**",
    ):
        if phrase not in acceptance:
            fail(f"launch state statement missing: {phrase}")

    print("PHIL_AI_OS_SPRINT_7_OPERATOR_AND_ACCEPTANCE_GREEN engineering_package=true live_launch=false profile_complete=true phone_verified=true")
    print("PHIL_AI_OS_SPRINT_7_PREPRODUCTION_PAYMENT_GATES_OPEN preproduction=false komoju_test=false shipping=false payment_methods=false")
    print("PHIL_AI_OS_SPRINT_7_SIGNOFF_BOUNDARY_GREEN ceo=false cto=false cutover=false")


if __name__ == "__main__":
    main()
