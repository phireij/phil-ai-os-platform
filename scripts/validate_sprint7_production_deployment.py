#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "ops/readiness/sprint7-production-deployment-readiness.json"
PROFILE = ROOT / "ops/readiness/verified-ruby-business-profile.template.json"
STAGING = ROOT / "ops/readiness/ruby-woocommerce-komoju-staging-readiness.json"
APPROVAL = ROOT / "ops/readiness/ruby-tokushoho-owner-approval-2026-09-04.json"
TIMING_DOC = ROOT / "docs/RUBY_PAYMENT_TIMING_TOKUSHOHO_RECONCILIATION_2026-09-04.md"
CANDIDATE_DOC = ROOT / "docs/RUBY_TOKUSHOHO_FINAL_PUBLICATION_CANDIDATE_2026-09-04.md"
SCREEN_CHECKLIST = ROOT / "docs/RUBY_FINAL_CONFIRMATION_SCREEN_REVIEW_CHECKLIST_2026-09-04.md"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_SPRINT_7_DEPLOYMENT_READINESS_FAILED: {message}")


def main() -> None:
    data = json.loads(READINESS.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    staging = json.loads(STAGING.read_text(encoding="utf-8"))
    approval_record = json.loads(APPROVAL.read_text(encoding="utf-8"))

    if data.get("version") != "sprint7-production-deployment-readiness-v5":
        fail("deployment readiness schema drift")
    if profile.get("profile_complete") is not True or profile.get("production_publish_authorized") is not False:
        fail("canonical profile state drift")

    migration = data["migration"]
    if migration.get("verified_business_profile_complete") is not True or migration.get("contact_phone_verified") is not True:
        fail("verified business prerequisites drift")
    if migration.get("old_test_catalog_authoritative") is not False:
        fail("old test catalog must remain non-authoritative")

    woo = data["woocommerce"]
    for key in ("parallel_preproduction_first_required", "native_hostinger_staging_requires_existing_wordpress", "native_staging_plan_eligibility_verified", "ssl_verification_required", "checkout_qa_required", "backup_restore_gate_required", "rollback_plan_required", "preproduction_environment_created", "wordpress_ready", "woocommerce_ready", "ssl_verified", "checkout_qa_green"):
        if woo.get(key) is not True:
            fail(f"WooCommerce preproduction readiness drift: {key}")
    if woo.get("preproduction_url") != "https://darkgreen-wallaby-680439.hostingersite.com/" or woo.get("hosting_plan") != "Business Web Hosting":
        fail("WooCommerce deployment identity drift")
    for key in ("production_credentials_authorized", "live_api_connectivity_authorized", "live_mutation_authorized", "dns_or_site_cutover_authorized"):
        if woo.get(key) is not False:
            fail(f"WooCommerce production authority drift: {key}")

    approved = ["visa_mastercard", "jcb_amex_diners_discover", "konbini", "merpay", "paidy"]
    komoju = data["komoju"]
    if komoju.get("current_connection_state") != "live_dashboard_selected" or komoju.get("connection_method") != "komoju-sign-in-oauth-style":
        fail("KOMOJU connection state/model drift")
    for key in ("test_mode_activation_authorized", "test_mode_validated", "merchant_live_dashboard_access_verified", "merchant_available_payment_methods_verified", "production_enabled_payment_methods_finalized", "production_checkout_configuration_verified", "konbini_live_expiry_setting_verified"):
        if komoju.get(key) is not True:
            fail(f"KOMOJU verified state regressed: {key}")
    if komoju.get("production_enabled_payment_methods") != approved:
        fail("KOMOJU approved production subset drift")
    if komoju.get("production_checkout_verification_run_id") != 33776964709 or komoju.get("production_checkout_verification_attempt") != 2:
        fail("KOMOJU checkout verification evidence drift")
    if komoju.get("konbini_live_expiry_days") != 3:
        fail("KOMOJU Live Konbini expiry must remain exactly 3 days")
    for key in ("live_mode_authorized", "payment_execution_authorized"):
        if komoju.get(key) is not False:
            fail(f"KOMOJU live authority drift: {key}")

    legal = data["legal_and_fulfillment"]
    for key in ("tokushoho_source_reconciled", "tokushoho_publication_candidate_ready", "tokushoho_candidate_text_approved", "store_pickup_supported", "production_shipping_rates_verified", "production_payment_methods_verified", "production_payment_timing_verified", "static_confirmation_screen_checklist_ready"):
        if legal.get(key) is not True:
            fail(f"legal/fulfillment readiness drift: {key}")
    if legal.get("tokushoho_publication_candidate_ref") != "docs/RUBY_TOKUSHOHO_FINAL_PUBLICATION_CANDIDATE_2026-09-04.md" or not CANDIDATE_DOC.is_file():
        fail("Tokushoho publication candidate evidence missing")
    if legal.get("tokushoho_candidate_text_approval_ref") != "ops/readiness/ruby-tokushoho-owner-approval-2026-09-04.json":
        fail("Tokushoho text-approval evidence ref drift")
    if legal.get("payment_timing_reconciliation_ref") != "docs/RUBY_PAYMENT_TIMING_TOKUSHOHO_RECONCILIATION_2026-09-04.md" or not TIMING_DOC.is_file():
        fail("payment-timing reconciliation evidence missing")
    if legal.get("static_confirmation_screen_checklist_ref") != "docs/RUBY_FINAL_CONFIRMATION_SCREEN_REVIEW_CHECKLIST_2026-09-04.md" or not SCREEN_CHECKLIST.is_file():
        fail("static confirmation-screen checklist evidence missing")
    if legal.get("tokushoho_publication_execution_approved") is not False or legal.get("tokushoho_publication_approved") is not False:
        fail("candidate-text approval leaked into publication execution")
    if legal.get("final_confirmation_screen_reviewed") is not False:
        fail("actual final confirmation screen changed without evidence")

    if approval_record.get("decision_scope") != "candidate_text_approval_only" or approval_record.get("approval_recorded") is not True or approval_record.get("candidate_text_approved") is not True:
        fail("canonical CEO text-approval evidence drift")
    for key, value in approval_record["authority"].items():
        if value is not False:
            fail(f"CEO candidate-text approval expanded authority: {key}")

    sfront = staging["storefront"]
    expected = {
        "parallel_preproduction_environment_created": True,
        "preproduction_url": "https://darkgreen-wallaby-680439.hostingersite.com/",
        "hosting_plan": "Business Web Hosting",
        "native_staging_plan_eligibility_verified": True,
        "wordpress_ready": True,
        "woocommerce_ready": True,
        "ssl_verified": True,
        "checkout_qa_green": True,
        "production_cutover_authorized": False,
    }
    for key, value in expected.items():
        if sfront.get(key) != value:
            fail(f"preproduction record drift: {key}")

    if staging.get("version") != "ruby-woocommerce-komoju-staging-readiness-v5":
        fail("staging readiness schema not reconciled")
    if staging.get("next_gate") != "finalize_catalog_review_actual_confirmation_screen_then_separate_publication_execution_recovery_and_go_no_go_without_real_payment_execution":
        fail("next gate drift")

    skomoju = staging["komoju"]
    for key in ("test_mode_connected", "merchant_live_dashboard_access_verified", "merchant_available_payment_methods_verified", "live_mode_merchant_approval_verified", "production_enabled_payment_methods_finalized", "production_checkout_configuration_verified", "konbini_live_expiry_setting_verified"):
        if skomoju.get(key) is not True:
            fail(f"KOMOJU staging evidence regressed: {key}")
    if skomoju.get("production_enabled_payment_methods") != approved or skomoju.get("konbini_live_expiry_days") != 3:
        fail("KOMOJU staging payment subset/expiry drift")
    if skomoju.get("live_mode_authorized") is not False or skomoju.get("payment_execution_authorized") is not False:
        fail("KOMOJU staging live/payment authority drift")

    slegal = staging["legal_checkout_sync"]
    for key in ("tokushoho_payment_timing_match_checkout", "tokushoho_publication_candidate_ready", "tokushoho_candidate_text_approved", "static_confirmation_screen_checklist_ready"):
        if slegal.get(key) is not True:
            fail(f"staging legal sync regressed: {key}")
    if slegal.get("tokushoho_publication_execution_approved") is not False:
        fail("staging publication execution unexpectedly approved")
    if slegal.get("final_confirmation_screen_reviewed") is not False:
        fail("actual final confirmation screen changed without evidence")
    if staging.get("production_publish_authorized") is not False:
        fail("preproduction record gained publication authority")

    for rel in data.get("evidence", []):
        if not (ROOT / rel).is_file():
            fail(f"missing deployment evidence file: {rel}")

    print("PHIL_AI_OS_SPRINT_7_DEPLOYMENT_READINESS_GREEN preproduction_created=true komoju_subset=true checkout_config_verified=true konbini_expiry_days=3 payment_timing=true")
    print("PHIL_AI_OS_SPRINT_7_TOKUSHOHO_TEXT_APPROVAL_GREEN candidate_text=true publication_execution=false actual_screen=false")
    print("PHIL_AI_OS_SPRINT_7_PRODUCTION_ACTIVATION_BOUNDARY_GREEN woo=false komoju_payment_execution=false publish=false dns=false")


if __name__ == "__main__":
    main()
