#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "ops/readiness/sprint7-launch-acceptance.json"
PROFILE = ROOT / "ops/readiness/verified-ruby-business-profile.template.json"
STAGING = ROOT / "ops/readiness/ruby-woocommerce-komoju-staging-readiness.json"
CUTOVER_RUNBOOK = ROOT / "docs/SPRINT_7_FINAL_CUTOVER_CONTROL_RUNBOOK_2026-09-02.md"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_SPRINT_7_LAUNCH_ACCEPTANCE_FAILED: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def main() -> None:
    data = json.loads(READINESS.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    staging = json.loads(STAGING.read_text(encoding="utf-8"))

    require(data.get("version") == "sprint7-launch-acceptance-v3", "launch acceptance schema drift")

    engineering = data["bounded_engineering_readiness"]
    for key in ("current_head_integrated_regression_required", "isolated_runtime_smoke_required", "security_recovery_package_ready", "deployment_migration_runbooks_ready", "channel_activation_runbooks_ready", "operator_documentation_ready", "final_current_head_ci_required"):
        require(engineering.get(key) is True, f"bounded engineering readiness drift: {key}")

    verified = data["verified_readiness"]
    require(verified["verified_ruby_business_profile_complete"] is True and profile.get("profile_complete") is True, "verified profile completion drift")
    require(verified["contact_phone_verified"] is True, "contact phone verification drift")
    phone = profile["contact_information"]["phone"]
    require(phone.get("value") == "050-1785-0575" and phone.get("verification_status") == "verified", "launch phone verification mismatch")
    for key in (
        "tokushoho_source_reconciled",
        "woocommerce_preproduction_qa_green",
        "woocommerce_production_readonly_identity_green",
        "woocommerce_production_readonly_connectivity_green",
        "komoju_test_mode_validated",
        "komoju_live_dashboard_green",
        "komoju_production_payment_subset_finalized",
        "komoju_production_checkout_configuration_verified",
        "komoju_live_konbini_expiry_verified",
        "production_payment_methods_verified",
        "production_shipping_configuration_verified",
        "japan_2026_tax_decision_green",
    ):
        require(verified.get(key) is True, f"verified readiness regressed: {key}")
    require(verified["komoju_live_konbini_expiry_days"] == 3, "KOMOJU Live Konbini expiry drift")
    require(verified["japan_2026_tax_status"] == "exempt", "Japan tax status drift")
    require(verified["qualified_invoice_status"] == "not_registered", "Qualified Invoice status drift")
    require(verified["woocommerce_tax_enabled"] is False, "WooCommerce tax unexpectedly enabled")

    scope = data["scope_approvals"]
    for key in ("woocommerce_production_activation_scope_approved", "komoju_live_mode_scope_approved", "production_sms_sending_scope_approved", "public_domain_dns_cutover_scope_approved", "final_launch_signoff_process_scope_approved"):
        require(scope.get(key) is True, f"scope approval drift: {key}")
    require(scope["scope_approval_overrides_readiness"] is False, "scope approval incorrectly overrides readiness")

    remaining = data["remaining_launch_gates"]
    for key, value in remaining.items():
        require(value is False, f"launch gate changed without explicit reconciliation: {key}")

    sfront = staging["storefront"]
    expected_front = {
        "parallel_preproduction_environment_created": True,
        "preproduction_url": "https://darkgreen-wallaby-680439.hostingersite.com/",
        "hosting_plan": "Business Web Hosting",
        "wordpress_ready": True,
        "woocommerce_ready": True,
        "ssl_verified": True,
        "checkout_qa_green": True,
        "production_cutover_authorized": False,
    }
    for key, value in expected_front.items():
        require(sfront.get(key) == value, f"preproduction environment state drift: {key}")

    fulfillment = staging["fulfillment"]
    require(fulfillment.get("production_shipping_configuration_verified") is True, "pre-production shipping configuration verification drift")
    require(fulfillment.get("production_shipping_rates_verified") is True, "pre-production shipping-rate verification drift")

    komoju = staging["komoju"]
    approved = ["visa_mastercard", "jcb_amex_diners_discover", "konbini", "merpay", "paidy"]
    require(komoju.get("current_connection_state") == "live_dashboard_selected", "KOMOJU Live-dashboard state evidence drift")
    require(komoju.get("test_mode_connected") is True and komoju.get("test_capture_refund_validated") is True, "KOMOJU Test Mode validation drift")
    require(komoju.get("merchant_live_dashboard_access_verified") is True, "KOMOJU merchant Live dashboard evidence missing")
    require(komoju.get("merchant_available_payment_methods_verified") is True, "KOMOJU merchant payment-method evidence missing")
    require(komoju.get("production_enabled_payment_methods_finalized") is True, "KOMOJU production payment subset should be finalized")
    require(komoju.get("production_enabled_payment_methods") == approved, "KOMOJU approved production payment subset drift")
    require(komoju.get("production_checkout_configuration_verified") is True, "KOMOJU checkout configuration verification regressed")
    require(komoju.get("production_checkout_verification_run_id") == 33776964709 and komoju.get("production_checkout_verification_attempt") == 2, "KOMOJU checkout verification evidence drift")
    require(komoju.get("konbini_live_expiry_setting_verified") is True and komoju.get("konbini_live_expiry_days") == 3, "KOMOJU Live Konbini expiry evidence drift")
    require(komoju.get("live_mode_authorized") is False and komoju.get("payment_execution_authorized") is False, "KOMOJU live/payment authority must remain false")
    require(staging.get("production_publish_authorized") is False, "preproduction readiness gained publication authority")

    baseline = data["authority_baseline"]
    expected_baseline = {
        "autonomy": "A0",
        "task_class_allowlist": ["general"],
        "assigned_agent": "hermes",
        "specialists_enabled": False,
        "mission_control_mutation_authorized": False,
        "automatic_production_execution_authorized": False,
        "live_launch_authorized_by_readiness": False,
    }
    for key, value in expected_baseline.items():
        require(baseline.get(key) == value, f"authority baseline drift: {key}")

    for rel in data.get("evidence", []):
        require((ROOT / rel).is_file(), f"missing launch-acceptance evidence file: {rel}")

    runbook = CUTOVER_RUNBOOK.read_text(encoding="utf-8")
    for phrase in (
        "Ruby is treated as consumption-tax exempt",
        "WooCommerce tax remains disabled",
        "branch-protection rule or repository ruleset",
        "## Stop / rollback decision matrix",
        "Perform public-domain/DNS cutover last",
        "Do not retain raw credentials, payment secrets, personal tax-return files",
        "PHIL_AI_OS_SPRINT_7_FINAL_CUTOVER_RUNBOOK_PREPARED_FAIL_CLOSED",
    ):
        require(phrase in runbook, f"cutover runbook control missing: {phrase}")

    require(data["decision"] == "ENGINEERING_PREPARED_LIVE_LAUNCH_PENDING_FAIL_CLOSED", "launch acceptance decision drift")

    print("PHIL_AI_OS_SPRINT_7_OPERATOR_AND_ACCEPTANCE_GREEN engineering_package=true live_launch=false profile_complete=true")
    print("PHIL_AI_OS_SPRINT_7_KOMOJU_SUBSET_GREEN finalized=true checkout_config_verified=true konbini_expiry_days=3 payment_execution=false")
    print("PHIL_AI_OS_SPRINT_7_SIGNOFF_BOUNDARY_GREEN recovery_fresh=false ceo_go_no_go=false cto=false cutover=false")
    print("PHIL_AI_OS_SPRINT_7_CUTOVER_RUNBOOK_CONTROL_GREEN tax_disabled=true branch_protection_gate=true rollback_matrix=true")


if __name__ == "__main__":
    main()
