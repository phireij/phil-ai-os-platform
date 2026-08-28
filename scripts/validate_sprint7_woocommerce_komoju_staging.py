#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "ops/readiness/ruby-woocommerce-komoju-staging-readiness.json"
PROFILE = ROOT / "ops/readiness/verified-ruby-business-profile.template.json"
TOKUSHOHO = ROOT / "docs/RUBY_TOKUSHOHO_EXPANSION_DRAFT_2026-08-29.md"
PLAN = ROOT / "docs/RUBY_WOOCOMMERCE_KOMOJU_STAGING_CONFIGURATION_PLAN_2026-08-29.md"
KOMOJU_RUNBOOK = ROOT / "docs/SPRINT_7_KOMOJU_ACTIVATION_RUNBOOK_2026-08-28.md"
WOO_RUNBOOK = ROOT / "docs/SPRINT_7_WOOCOMMERCE_STAGING_CUTOVER_RUNBOOK_2026-08-28.md"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_RUBY_WOO_KOMOJU_STAGING_FAILED: {message}")


def require(text: str, phrases: tuple[str, ...], label: str) -> None:
    for phrase in phrases:
        if phrase not in text:
            fail(f"{label} missing: {phrase}")


def main() -> None:
    data = json.loads(READINESS.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))

    if profile.get("profile_complete") is not True or profile.get("production_publish_authorized") is not False:
        fail("canonical business profile state drift")

    business = data["business_profile"]
    if business.get("verified_profile_complete") is not True or business.get("resolved_fields") != 15:
        fail("staging business-profile prerequisite drift")
    if business.get("contact_phone_verified") is not True:
        fail("phone verification drift")
    if business.get("tokushoho_source_reconciled") is not True:
        fail("Tokushoho source must remain reconciled")
    if business.get("tokushoho_publication_approved") is not False:
        fail("Tokushoho publication must remain pending")

    storefront = data["storefront"]
    if storefront.get("target") != "hostinger-managed-wordpress-woocommerce":
        fail("storefront target drift")
    if storefront.get("public_domain") != "https://www.rubyscakedelights.shop/":
        fail("public-domain drift")
    if storefront.get("staging_first_required") is not True:
        fail("staging-first requirement drift")
    for key in ("staging_environment_created", "wordpress_ready", "woocommerce_ready", "ssl_verified", "checkout_qa_green", "production_cutover_authorized"):
        if storefront.get(key) is not False:
            fail(f"staging/live gate must remain open: {key}")

    fulfillment = data["fulfillment"]
    if fulfillment.get("store_pickup_supported") is not True:
        fail("store pickup must remain supported")
    if fulfillment.get("legacy_shipping_provider") != "yamato-cool-takkyubin":
        fail("legacy Yamato shipping source drift")
    if fulfillment.get("legacy_kanto_rate_jpy") != 1350:
        fail("legacy Kanto shipping rate drift")
    if fulfillment.get("legacy_other_regions_rate_range_jpy") != [1500, 1800]:
        fail("legacy other-region shipping range drift")
    for key in ("production_shipping_configuration_verified", "production_shipping_rates_verified"):
        if fulfillment.get(key) is not False:
            fail(f"production shipping gate must remain open: {key}")
    if fulfillment.get("mid_september_hours_recheck_required") is not True:
        fail("mid-September hours recheck safeguard missing")

    komoju = data["komoju"]
    expected = {
        "provider": "komoju",
        "integration": "official-woocommerce-plugin",
        "connection_method": "komoju-sign-in-oauth-style",
        "automatic_secret_and_webhook_configuration": True,
        "manual_api_key_entry_expected": False,
        "current_connection_state": "not_configured",
        "test_mode_required_before_live": True,
    }
    for key, value in expected.items():
        if komoju.get(key) != value:
            fail(f"KOMOJU staging contract drift: {key}={komoju.get(key)!r}")
    if komoju.get("legacy_disclosed_card_brands") != ["Visa", "Mastercard", "JCB", "American Express", "Diners Club"]:
        fail("legacy disclosed card brands drift")
    for key in (
        "test_mode_connection_authorized",
        "test_mode_connected",
        "merchant_available_payment_methods_verified",
        "production_enabled_payment_methods_finalized",
        "live_mode_merchant_approval_verified",
        "live_mode_authorized",
        "payment_execution_authorized",
    ):
        if komoju.get(key) is not False:
            fail(f"KOMOJU gate must remain open: {key}")

    legal = data["legal_checkout_sync"]
    for key, value in legal.items():
        if value is not False:
            fail(f"legal/checkout sync must remain incomplete: {key}")

    if data.get("next_gate") != "create_hostinger_wordpress_woocommerce_staging_without_public_cutover_or_live_payments":
        fail("next executable gate drift")
    if data.get("production_publish_authorized") is not False:
        fail("staging readiness gained production publication authority")

    tokushoho = TOKUSHOHO.read_text(encoding="utf-8")
    require(tokushoho, (
        "BOMBEO PHILIP GO",
        "050-1785-0575",
        "info@rubyscakedelights.shop",
        "ヤマト運輸（クール宅急便）",
        "関東：一律 1,350円",
        "tokushoho_source_reconciled: true",
        "tokushoho_publication_approved: false",
        "production_publish_authorized: false",
    ), "Tokushoho reconciled draft")

    plan = PLAN.read_text(encoding="utf-8")
    require(plan, (
        "READY FOR STAGING PREPARATION / NO PUBLIC CUTOVER / NO PAYMENT ACTIVATION AUTHORIZED",
        "KOMOJU Payments",
        "Sign into KOMOJU",
        "Test Mode",
        "legacy Ruby legal page disclosed",
        "Yamato Transport Cool TA-Q-BIN",
        "Create the Hostinger WordPress/WooCommerce staging environment",
        "PHIL_AI_OS_RUBY_WOOCOMMERCE_KOMOJU_STAGING_PLAN_READY_NEXT_GATE_CREATE_STAGING",
    ), "staging configuration plan")

    require(KOMOJU_RUNBOOK.read_text(encoding="utf-8"), (
        "komoju-sign-in-oauth-style" if False else "Sign into KOMOJU",
        "automatically configures the KOMOJU secret key and webhooks",
        "deprecated legacy `Komoju` payment method",
        "Test Mode",
        "PHIL_AI_OS_SPRINT_7_KOMOJU_RUNBOOK_READY_NOT_AUTHORIZED",
    ), "KOMOJU runbook")

    require(WOO_RUNBOOK.read_text(encoding="utf-8"), (
        "Verified Ruby Business Profile complete — **15/15 resolved**",
        "Yamato Transport Cool TA-Q-BIN",
        "store pickup",
        "production shipping configuration/rates are verified",
        "PHIL_AI_OS_SPRINT_7_WOOCOMMERCE_CUTOVER_RUNBOOK_READY_NOT_AUTHORIZED",
    ), "WooCommerce staging runbook")

    print("PHIL_AI_OS_RUBY_WOO_KOMOJU_STAGING_READINESS_GREEN profile=15of15 tokushoho_reconciled=true")
    print("PHIL_AI_OS_RUBY_FULFILLMENT_RECONCILIATION_GREEN pickup=true yamato_legacy=true shipping_production_verified=false")
    print("PHIL_AI_OS_RUBY_KOMOJU_CURRENT_INTEGRATION_GREEN connection=sign_in_oauth_style test_mode_authorized=false live_mode=false")
    print("PHIL_AI_OS_RUBY_STAGING_NEXT_GATE_GREEN action=create_hostinger_wordpress_woocommerce_staging publish=false")


if __name__ == "__main__":
    main()
