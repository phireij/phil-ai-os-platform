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
    )
    for key in required_true:
        if woo.get(key) is not True:
            fail(f"WooCommerce preproduction readiness drift: {key}")
    if woo.get("preproduction_url") != "https://darkgreen-wallaby-680439.hostingersite.com/":
        fail("preproduction URL drift")
    if woo.get("hosting_plan") != "Business Web Hosting":
        fail("hosting plan drift")
    if woo.get("checkout_qa_green") is not False:
        fail("checkout QA must remain open")
    for key in ("production_credentials_authorized", "live_api_connectivity_authorized", "live_mutation_authorized", "dns_or_site_cutover_authorized"):
        if woo.get(key) is not False:
            fail(f"WooCommerce production authority drift: {key}")

    komoju = data["komoju"]
    if komoju.get("current_connection_state") != "not_configured" or komoju.get("connection_method") != "komoju-sign-in-oauth-style":
        fail("KOMOJU connection state/model drift")
    for key in ("test_mode_activation_authorized", "test_mode_validated", "live_mode_authorized", "payment_execution_authorized"):
        if komoju.get(key) is not False:
            fail(f"KOMOJU authority drift: {key}")

    legal = data["legal_and_fulfillment"]
    if legal.get("tokushoho_source_reconciled") is not True or legal.get("store_pickup_supported") is not True:
        fail("legal/fulfillment source drift")
    for key in ("tokushoho_publication_approved", "production_shipping_rates_verified", "production_payment_methods_verified"):
        if legal.get(key) is not False:
            fail(f"production legal/fulfillment gate must remain open: {key}")

    sfront = staging["storefront"]
    expected = {
        "parallel_preproduction_environment_created": True,
        "preproduction_url": "https://darkgreen-wallaby-680439.hostingersite.com/",
        "hosting_plan": "Business Web Hosting",
        "native_staging_plan_eligibility_verified": True,
        "wordpress_ready": True,
        "woocommerce_ready": True,
        "ssl_verified": True,
        "checkout_qa_green": False,
        "production_cutover_authorized": False,
    }
    for key, value in expected.items():
        if sfront.get(key) != value:
            fail(f"preproduction record drift: {key}")
    if staging.get("next_gate") != "configure_woocommerce_baseline_and_load_verified_ruby_business_legal_content_without_komoju_connection":
        fail("next gate drift")
    if staging["komoju"].get("test_mode_connection_authorized") is not False or staging["komoju"].get("live_mode_authorized") is not False:
        fail("KOMOJU staging authority drift")
    if staging.get("production_publish_authorized") is not False:
        fail("preproduction record gained publication authority")

    for rel in data.get("evidence", []):
        if not (ROOT / rel).is_file():
            fail(f"missing deployment evidence file: {rel}")

    print("PHIL_AI_OS_SPRINT_7_DEPLOYMENT_READINESS_GREEN preproduction_created=true wordpress=true woocommerce=true ssl=true checkout_qa=false")
    print("PHIL_AI_OS_SPRINT_7_NEXT_GATE_GREEN configure_baseline_content=true komoju=false")
    print("PHIL_AI_OS_SPRINT_7_PRODUCTION_ACTIVATION_BOUNDARY_GREEN woo=false komoju=false dns=false")


if __name__ == "__main__":
    main()
