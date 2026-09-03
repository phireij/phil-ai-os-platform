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
        if storefront.get(key) != value:
            fail(f"preproduction storefront state drift: {key}={storefront.get(key)!r}")

    if data.get("next_gate") != "finalize_catalog_complete_payment_timing_legal_confirmation_screen_recovery_and_go_no_go_without_real_payment_execution":
        fail("next executable gate drift")
    if data.get("production_publish_authorized") is not False:
        fail("preproduction readiness gained production publication authority")

    fulfillment = data["fulfillment"]
    if fulfillment.get("store_pickup_supported") is not True or fulfillment.get("legacy_shipping_provider") != "yamato-cool-takkyubin":
        fail("fulfillment source drift")
    if fulfillment.get("production_shipping_configuration_verified") is not True or fulfillment.get("production_shipping_rates_verified") is not True:
        fail("verified pre-production shipping state regressed")

    komoju = data["komoju"]
    if komoju.get("current_connection_state") != "live_dashboard_selected":
        fail("KOMOJU current state drift")
    if komoju.get("connection_method") != "komoju-sign-in-oauth-style" or komoju.get("manual_api_key_entry_expected") is not False:
        fail("KOMOJU integration model drift")
    for key in ("test_mode_connection_authorized", "test_mode_connected", "test_capture_refund_validated", "merchant_live_dashboard_access_verified", "merchant_available_payment_methods_verified", "live_mode_merchant_approval_verified", "production_enabled_payment_methods_finalized", "production_checkout_configuration_verified", "konbini_live_expiry_setting_verified"):
        if komoju.get(key) is not True:
            fail(f"verified KOMOJU readiness regressed: {key}")

    available = {"visa_mastercard", "jcb_amex_diners_discover", "konbini", "merpay", "paidy", "bank_transfer", "pay_easy"}
    if set(komoju.get("enabled_or_available_methods_shown", [])) != available:
        fail("KOMOJU merchant payment-method availability set drift")
    approved = ["visa_mastercard", "jcb_amex_diners_discover", "konbini", "merpay", "paidy"]
    if komoju.get("production_enabled_payment_methods") != approved:
        fail("CEO-approved production payment subset drift")
    if komoju.get("production_disabled_payment_methods") != ["bank_transfer", "pay_easy"]:
        fail("initially disabled production payment subset drift")
    if komoju.get("production_checkout_verification_run_id") != 33776964709 or komoju.get("production_checkout_verification_attempt") != 2:
        fail("checkout verification evidence drift")
    if komoju.get("konbini_live_expiry_days") != 3:
        fail("Live Konbini expiry must remain exactly 3 days")
    if komoju.get("konbini_live_expiry_evidence_class") != "owner_confirmed_live_dashboard_configuration":
        fail("Live Konbini expiry evidence classification drift")
    if komoju.get("paypay_status") != "application_under_review":
        fail("PayPay review status drift")
    if komoju.get("rakuten_pay_status") != "not_available_declined_or_no_longer_eligible":
        fail("Rakuten Pay availability status drift")
    for key in ("live_mode_authorized", "payment_execution_authorized"):
        if komoju.get(key) is not False:
            fail(f"KOMOJU execution authority must remain false: {key}")

    legal = data["legal_checkout_sync"]
    if legal.get("tokushoho_payment_methods_match_checkout") is not True or legal.get("tokushoho_shipping_fees_match_checkout") is not True:
        fail("verified payment-method/shipping legal sync regressed")
    for key in ("tokushoho_payment_timing_match_checkout", "final_confirmation_screen_reviewed"):
        if legal.get(key) is not False:
            fail(f"legal/checkout timing must remain pending: {key}")
    if legal.get("privacy_terms_implementation_reviewed") is not True:
        fail("verified privacy/terms implementation review regressed")

    expected_historical_evidence = {
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
    for key, value in expected_historical_evidence.items():
        if evidence.get(key) != value:
            fail(f"historical operator evidence drift: {key}={evidence.get(key)!r}")

    tokushoho = TOKUSHOHO.read_text(encoding="utf-8")
    for phrase in ("BOMBEO PHILIP GO", "050-1785-0575", "info@rubyscakedelights.shop", "tokushoho_publication_approved: false", "production_publish_authorized: false"):
        if phrase not in tokushoho:
            fail(f"Tokushoho safeguard missing: {phrase}")

    print("PHIL_AI_OS_RUBY_HOSTINGER_PREPRODUCTION_ENVIRONMENT_GREEN created=true wordpress=true woocommerce=true ssl=true checkout_qa=true shipping=true")
    print("PHIL_AI_OS_RUBY_KOMOJU_PAYMENT_SUBSET_GREEN live_selected=true methods_verified=true final_subset=true checkout_config_verified=true konbini_expiry_days=3 payment_execution=false")
    print("PHIL_AI_OS_RUBY_NEXT_GATE_GREEN action=finalize_catalog_legal_timing_recovery_go_no_go publish=false")


if __name__ == "__main__":
    main()
