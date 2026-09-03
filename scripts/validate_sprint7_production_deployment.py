#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "ops/readiness/sprint7-production-deployment-readiness.json"
PROFILE = ROOT / "ops/readiness/verified-ruby-business-profile.template.json"
STAGING = ROOT / "ops/readiness/ruby-woocommerce-komoju-staging-readiness.json"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_SPRINT_7_DEPLOYMENT_READINESS_FAILED: {message}")


def main() -> None:
    data = json.loads(READINESS.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    staging = json.loads(STAGING.read_text(encoding="utf-8"))

    if profile.get("profile_complete") is not True or profile.get("production_publish_authorized") is not False:
        fail("canonical profile state drift")

    migration = data["migration"]
    if migration.get("verified_business_profile_complete") is not True or migration.get("contact_phone_verified") is not True:
        fail("verified business prerequisites drift")
    if migration.get("old_test_catalog_authoritative") is not False:
        fail("old test catalog must remain non-authoritative")

    woo = data["woocommerce"]
    required_true = (
        "parallel_preproduction_first_required",
        "native_hostinger_staging_requires_existing_wordpress",
        "native_staging_plan_eligibility_verified",
        "ssl_verification_required",
        "checkout_qa_required",
        "backup_restore_gate_required",
        "rollback_plan_required",
        "preproduction_environment_created",
        "wordpress_ready",
        "woocommerce_ready",
        "ssl_verified",
        "checkout_qa_green",
    )
    for key in required_true:
        if woo.get(key) is not True:
            fail(f"WooCommerce preproduction readiness drift: {key}")
    if woo.get("preproduction_url") != "https://darkgreen-wallaby-680439.hostingersite.com/":
        fail("preproduction URL drift")
    if woo.get("hosting_plan") != "Business Web Hosting":
        fail("hosting plan drift")
    for key in ("production_credentials_authorized", "live_api_connectivity_authorized", "live_mutation_authorized", "dns_or_site_cutover_authorized"):
        if woo.get(key) is not False:
            fail(f"WooCommerce production authority drift: {key}")

    komoju = data["komoju"]
    if komoju.get("current_connection_state") != "live_dashboard_selected" or komoju.get("connection_method") != "komoju-sign-in-oauth-style":
        fail("KOMOJU connection state/model drift")
    for key in ("test_mode_activation_authorized", "test_mode_validated", "merchant_live_dashboard_access_verified", "merchant_available_payment_methods_verified"):
        if komoju.get(key) is not True:
            fail(f"KOMOJU verified state regressed: {key}")
    if komoju.get("production_enabled_payment_methods_finalized") is not False:
        fail("KOMOJU production payment subset changed without reconciliation")
    for key in ("live_mode_authorized", "payment_execution_authorized"):
        if komoju.get(key) is not False:
            fail(f"KOMOJU live authority drift: {key}")

    legal = data["legal_and_fulfillment"]
    if legal.get("tokushoho_source_reconciled") is not True or legal.get("store_pickup_supported") is not True:
        fail("legal/fulfillment source drift")
    if legal.get("production_shipping_rates_verified") is not True:
        fail("pre-production shipping verification regressed")
    for key in ("tokushoho_publication_approved", "production_payment_methods_verified"):
        if legal.get(key) is not False:
            fail(f"production legal/payment gate must remain open: {key}")

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
    if staging.get("next_gate") != "finalize_catalog_payment_subset_checkout_recovery_and_go_no_go_without_real_payment_execution":
        fail("next gate drift")
    skomoju = staging["komoju"]
    if skomoju.get("current_connection_state") != "live_dashboard_selected" or skomoju.get("test_mode_connected") is not True:
        fail("KOMOJU staging Live-dashboard/Test baseline drift")
    for key in ("merchant_live_dashboard_access_verified", "merchant_available_payment_methods_verified", "live_mode_merchant_approval_verified"):
        if skomoju.get(key) is not True:
            fail(f"KOMOJU staging merchant evidence regressed: {key}")
    if skomoju.get("production_enabled_payment_methods_finalized") is not False:
        fail("KOMOJU staging payment subset unexpectedly finalized")
    if skomoju.get("live_mode_authorized") is not False or skomoju.get("payment_execution_authorized") is not False:
        fail("KOMOJU staging live/payment authority drift")
    if staging.get("production_publish_authorized") is not False:
        fail("preproduction record gained publication authority")

    for rel in data.get("evidence", []):
        if not (ROOT / rel).is_file():
            fail(f"missing deployment evidence file: {rel}")

    print("PHIL_AI_OS_SPRINT_7_DEPLOYMENT_READINESS_GREEN preproduction_created=true wordpress=true woocommerce=true ssl=true checkout_qa=true shipping=true komoju_live_dashboard=true")
    print("PHIL_AI_OS_SPRINT_7_NEXT_GATE_GREEN catalog_payment_subset_checkout_recovery_go_no_go=true payment_execution=false")
    print("PHIL_AI_OS_SPRINT_7_PRODUCTION_ACTIVATION_BOUNDARY_GREEN woo=false komoju_payment_execution=false dns=false")


if __name__ == "__main__":
    main()
