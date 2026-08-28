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
    storefront = data["storefront"]
    migration = data["migration"]
    woo = data["woocommerce"]
    komoju = data["komoju"]
    legal = data["legal_and_fulfillment"]

    expected_storefront = {
        "public_domain": "https://www.rubyscakedelights.shop/",
        "current_platform": "hostinger-website-builder",
        "current_source_role": "reference-only",
        "target_platform": "hostinger-managed-wordpress-woocommerce",
        "phil_ai_os_runtime": "hostinger-vps-separate-control-plane",
    }
    for key, value in expected_storefront.items():
        if storefront.get(key) != value:
            fail(f"storefront architecture drift: {key}={storefront.get(key)!r}")

    if migration.get("copy_sections") != ["store_information", "contact_information", "policies"]:
        fail("migration copy scope drift")
    if migration.get("exclude_sections") != ["products", "categories"]:
        fail("migration exclusion scope drift")
    if migration.get("field_verification_required") is not True:
        fail("migration verification must remain required")
    if migration.get("verified_business_profile_complete") is not True:
        fail("verified business profile completion must match 15/15 canonical profile")
    if migration.get("contact_phone_verified") is not True:
        fail("contact phone verification must remain complete")
    if migration.get("old_test_catalog_authoritative") is not False:
        fail("old test catalog must never become authoritative")

    if profile.get("profile_complete") is not True or profile.get("production_publish_authorized") is not False:
        fail("canonical profile must be complete but publication-gated")
    phone = profile["contact_information"]["phone"]
    if phone.get("value") != "050-1785-0575" or phone.get("verification_status") != "verified":
        fail("canonical phone verification drift")

    required_true = (
        "staging_first_required",
        "ssl_verification_required",
        "checkout_qa_required",
        "backup_restore_gate_required",
        "rollback_plan_required",
    )
    for key in required_true:
        if woo.get(key) is not True:
            fail(f"WooCommerce readiness gate must remain required: {key}")
    if woo.get("staging_environment_created") is not False:
        fail("staging environment must not be assumed created")

    for key in (
        "production_credentials_authorized",
        "live_api_connectivity_authorized",
        "live_mutation_authorized",
        "dns_or_site_cutover_authorized",
    ):
        if woo.get(key) is not False:
            fail(f"WooCommerce production authority drift: {key}")

    if komoju.get("provider") != "komoju" or komoju.get("integration_mode") != "woocommerce_plugin":
        fail("KOMOJU integration contract drift")
    if komoju.get("connection_method") != "komoju-sign-in-oauth-style":
        fail("KOMOJU WooCommerce connection method drift")
    if komoju.get("current_connection_state") != "not_configured":
        fail("KOMOJU connection state must remain not_configured")
    for key in ("test_mode_activation_authorized", "test_mode_validated", "live_mode_authorized", "payment_execution_authorized"):
        if komoju.get(key) is not False:
            fail(f"KOMOJU authority/readiness drift: {key}")

    if legal.get("tokushoho_source_reconciled") is not True:
        fail("Tokushoho source reconciliation must remain recorded")
    for key in ("tokushoho_publication_approved", "production_shipping_rates_verified", "production_payment_methods_verified"):
        if legal.get(key) is not False:
            fail(f"production legal/fulfillment gate must remain open: {key}")
    if legal.get("store_pickup_supported") is not True or legal.get("legacy_yamato_cool_shipping_preserved_for_staging_verification") is not True:
        fail("pickup/shipping reconciliation drift")

    if staging["business_profile"].get("verified_profile_complete") is not True:
        fail("staging record profile state drift")
    if staging["storefront"].get("staging_environment_created") is not False:
        fail("staging record must not assume Hostinger staging exists")
    if staging["komoju"].get("manual_api_key_entry_expected") is not False:
        fail("current official WooCommerce flow must not assume manual API-key entry")
    if staging["komoju"].get("test_mode_connection_authorized") is not False:
        fail("KOMOJU Test Mode remains a separate authorization gate")
    if staging["komoju"].get("live_mode_authorized") is not False or staging["komoju"].get("payment_execution_authorized") is not False:
        fail("KOMOJU Live/payment authority drift")
    if staging.get("production_publish_authorized") is not False:
        fail("staging record gained publication authority")

    for rel in data.get("evidence", []):
        if not (ROOT / rel).is_file():
            fail(f"missing deployment evidence file: {rel}")

    migration_schema = json.loads((ROOT / "contracts/commerce/site-migration-source.schema.json").read_text(encoding="utf-8"))
    props = migration_schema["properties"]
    if props["public_domain"].get("const") != "https://www.rubyscakedelights.shop/":
        fail("migration schema public domain drift")
    if props["source_platform"].get("const") != "hostinger-website-builder":
        fail("migration schema source platform drift")
    if props["source_role"].get("const") != "reference-only":
        fail("migration schema source role drift")
    if props["production_authority"].get("const") is not False:
        fail("migration schema gained production authority")

    payment_schema = json.loads((ROOT / "contracts/cx/payment-handoff-intent.schema.json").read_text(encoding="utf-8"))
    pprops = payment_schema["properties"]
    expected_payment = {
        "provider": "komoju",
        "integration_mode": "woocommerce_plugin",
        "connection_state": "not_configured",
        "order_creation_authorized": False,
        "payment_execution_authorized": False,
        "live_mode_authorized": False,
    }
    for key, value in expected_payment.items():
        if pprops[key].get("const") != value:
            fail(f"payment handoff schema drift: {key}")

    marker_files = {
        "docs/SPRINT_7_WOOCOMMERCE_STAGING_CUTOVER_RUNBOOK_2026-08-28.md": "PHIL_AI_OS_SPRINT_7_WOOCOMMERCE_CUTOVER_RUNBOOK_READY_NOT_AUTHORIZED",
        "docs/SPRINT_7_KOMOJU_ACTIVATION_RUNBOOK_2026-08-28.md": "PHIL_AI_OS_SPRINT_7_KOMOJU_RUNBOOK_READY_NOT_AUTHORIZED",
    }
    for rel, marker in marker_files.items():
        if marker not in (ROOT / rel).read_text(encoding="utf-8"):
            fail(f"missing runbook marker in {rel}")

    print("PHIL_AI_OS_SPRINT_7_DEPLOYMENT_READINESS_GREEN staging_first=true verified_profile=true phone_verified=true")
    print("PHIL_AI_OS_SPRINT_7_STAGING_GATE_OPEN environment_created=false checkout_green=false")
    print("PHIL_AI_OS_SPRINT_7_PRODUCTION_ACTIVATION_BOUNDARY_GREEN woo=false komoju=false dns=false")


if __name__ == "__main__":
    main()
