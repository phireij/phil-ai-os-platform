#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "ops/readiness/sprint7-production-deployment-readiness.json"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_SPRINT_7_DEPLOYMENT_READINESS_FAILED: {message}")


def main() -> None:
    data = json.loads(READINESS.read_text(encoding="utf-8"))
    storefront = data["storefront"]
    migration = data["migration"]
    woo = data["woocommerce"]
    komoju = data["komoju"]

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
    if migration.get("verified_business_profile_complete") is not False:
        fail("verified business profile must not be assumed complete")
    if migration.get("contact_phone_verified") is not False:
        fail("contact phone must remain unverified until explicitly updated")
    if migration.get("old_test_catalog_authoritative") is not False:
        fail("old test catalog must never become authoritative")

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

    required_false = (
        "production_credentials_authorized",
        "live_api_connectivity_authorized",
        "live_mutation_authorized",
        "dns_or_site_cutover_authorized",
    )
    for key in required_false:
        if woo.get(key) is not False:
            fail(f"WooCommerce production authority drift: {key}")

    if komoju.get("provider") != "komoju" or komoju.get("integration_mode") != "woocommerce_plugin":
        fail("KOMOJU integration contract drift")
    if komoju.get("current_connection_state") != "not_configured":
        fail("KOMOJU connection state must remain not_configured")
    for key in ("test_mode_activation_authorized", "live_mode_authorized", "payment_execution_authorized"):
        if komoju.get(key) is not False:
            fail(f"KOMOJU authority drift: {key}")

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
        text = (ROOT / rel).read_text(encoding="utf-8")
        if marker not in text:
            fail(f"missing runbook marker in {rel}")

    print("PHIL_AI_OS_SPRINT_7_DEPLOYMENT_READINESS_GREEN staging_first=true verified_profile=false")
    print("PHIL_AI_OS_SPRINT_7_PRODUCTION_ACTIVATION_BOUNDARY_GREEN woo=false komoju=false dns=false")


if __name__ == "__main__":
    main()
