#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "ops/readiness/ruby-woocommerce-komoju-staging-readiness.json"
EVIDENCE = ROOT / "ops/readiness/ruby-hostinger-preproduction-evidence.template.json"
PROFILE = ROOT / "ops/readiness/verified-ruby-business-profile.template.json"
TOKUSHOHO = ROOT / "docs/RUBY_TOKUSHOHO_EXPANSION_DRAFT_2026-08-29.md"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_RUBY_WOO_KOMOJU_STAGING_FAILED: {message}")


def main() -> None:
    data = json.loads(READINESS.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))

    if profile.get("profile_complete") is not True or profile.get("production_publish_authorized") is not False:
        fail("canonical business profile state drift")

    business = data["business_profile"]
    if business.get("verified_profile_complete") is not True or business.get("resolved_fields") != 15:
        fail("business-profile prerequisite drift")
    if business.get("contact_phone_verified") is not True or business.get("tokushoho_source_reconciled") is not True:
        fail("verified phone/Tokushoho prerequisite drift")
    if business.get("tokushoho_publication_approved") is not False:
        fail("Tokushoho publication must remain pending")

    storefront = data["storefront"]
    expected = {
        "target": "hostinger-managed-wordpress-woocommerce",
        "current_public_platform": "hostinger-website-builder",
        "public_domain": "https://www.rubyscakedelights.shop/",
        "parallel_preproduction_first_required": True,
        "parallel_preproduction_environment_created": True,
        "preproduction_url": "https://darkgreen-wallaby-680439.hostingersite.com/",
        "hosting_plan": "Business Web Hosting",
        "native_hostinger_wordpress_staging_requires_existing_wordpress": True,
        "native_staging_plan_eligibility_verified": True,
        "native_staging_menu_located": False,
        "wordpress_ready": True,
        "woocommerce_ready": True,
        "ssl_verified": True,
        "checkout_qa_green": False,
        "production_cutover_authorized": False,
    }
    for key, value in expected.items():
        if storefront.get(key) != value:
            fail(f"preproduction storefront state drift: {key}={storefront.get(key)!r}")

    if data.get("next_gate") != "configure_woocommerce_baseline_and_load_verified_ruby_business_legal_content_without_komoju_connection":
        fail("next executable gate drift")
    if data.get("production_publish_authorized") is not False:
        fail("preproduction readiness gained production publication authority")

    fulfillment = data["fulfillment"]
    if fulfillment.get("store_pickup_supported") is not True or fulfillment.get("legacy_shipping_provider") != "yamato-cool-takkyubin":
        fail("fulfillment source drift")
    if fulfillment.get("legacy_kanto_rate_jpy") != 1350 or fulfillment.get("legacy_other_regions_rate_range_jpy") != [1500, 1800]:
        fail("legacy shipping-rate source drift")
    for key in ("production_shipping_configuration_verified", "production_shipping_rates_verified"):
        if fulfillment.get(key) is not False:
            fail(f"shipping gate must remain open: {key}")

    komoju = data["komoju"]
    if komoju.get("current_connection_state") != "not_configured":
        fail("KOMOJU must remain disconnected")
    if komoju.get("connection_method") != "komoju-sign-in-oauth-style" or komoju.get("manual_api_key_entry_expected") is not False:
        fail("KOMOJU integration model drift")
    for key in ("test_mode_connection_authorized", "test_mode_connected", "merchant_available_payment_methods_verified", "production_enabled_payment_methods_finalized", "live_mode_merchant_approval_verified", "live_mode_authorized", "payment_execution_authorized"):
        if komoju.get(key) is not False:
            fail(f"KOMOJU gate must remain open: {key}")

    for key, value in data["legal_checkout_sync"].items():
        if value is not False:
            fail(f"legal/checkout sync must remain incomplete: {key}")

    expected_evidence = {
        "public_domain_unchanged": True,
        "current_public_platform": "hostinger-website-builder",
        "preproduction_url": "https://darkgreen-wallaby-680439.hostingersite.com/",
        "wordpress_admin_reachable": True,
        "woocommerce_active": True,
        "https_ssl_green": True,
        "hostinger_native_wordpress_staging_menu_available": False,
        "hostinger_native_wordpress_staging_plan_eligible": True,
        "hosting_plan_name": "Business Web Hosting",
        "komoju_test_mode_connected": False,
        "komoju_live_mode_connected": False,
        "production_cutover_authorized": False,
        "evidence_complete": True,
    }
    for key, value in expected_evidence.items():
        if evidence.get(key) != value:
            fail(f"operator evidence drift: {key}={evidence.get(key)!r}")

    tokushoho = TOKUSHOHO.read_text(encoding="utf-8")
    for phrase in ("BOMBEO PHILIP GO", "050-1785-0575", "info@rubyscakedelights.shop", "tokushoho_publication_approved: false", "production_publish_authorized: false"):
        if phrase not in tokushoho:
            fail(f"Tokushoho safeguard missing: {phrase}")

    print("PHIL_AI_OS_RUBY_HOSTINGER_PREPRODUCTION_ENVIRONMENT_GREEN created=true wordpress=true woocommerce=true ssl=true")
    print("PHIL_AI_OS_RUBY_HOSTINGER_PLAN_GREEN plan=Business_Web_Hosting native_staging_eligible=true menu_located=false")
    print("PHIL_AI_OS_RUBY_KOMOJU_BOUNDARY_GREEN test_mode=false live_mode=false payment_execution=false")
    print("PHIL_AI_OS_RUBY_NEXT_GATE_GREEN action=configure_woocommerce_baseline_and_verified_content publish=false")


if __name__ == "__main__":
    main()
