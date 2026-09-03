#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "ops/readiness/ruby-checkout-legal-payment-shipping-sync-2026-09-04.json"
KOMOJU = ROOT / "ops/readiness/ruby-komoju-live-acceptance-gate-2026-09-02.json"
STAGING = ROOT / "ops/readiness/ruby-woocommerce-komoju-staging-readiness.json"
DOC = ROOT / "docs/RUBY_CHECKOUT_LEGAL_PAYMENT_SHIPPING_SYNC_2026-09-04.md"
WORKFLOW = ROOT / ".github/workflows/commerce-woocommerce-production-readonly-checkout-snapshot.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_RUBY_CHECKOUT_LEGAL_SYNC_FAILED: {message}")


def main() -> None:
    sync = json.loads(SYNC.read_text(encoding="utf-8"))
    komoju = json.loads(KOMOJU.read_text(encoding="utf-8"))
    staging = json.loads(STAGING.read_text(encoding="utf-8"))

    require(sync.get("version") == "ruby-checkout-legal-payment-shipping-sync-v3", "checkout sync schema drift")
    expected_subset = ["visa_mastercard", "jcb_amex_diners_discover", "konbini", "merpay", "paidy"]
    subset = sync["production_payment_subset"]
    require(subset["ceo_approved"] is True, "payment subset approval drift")
    require(subset["selected"] == expected_subset, "payment subset drift")
    require(subset["disabled_initial_launch"] == ["bank_transfer", "pay_easy"], "disabled-set drift")
    require(subset["pending_provider_review"] == ["paypay"], "PayPay review drift")
    require(subset["excluded"] == ["rakuten_pay"], "Rakuten exclusion drift")

    prereq = sync["verified_prerequisites"]
    for key in (
        "komoju_live_dashboard_evidence_green",
        "komoju_merchant_method_availability_green",
        "japan_2026_tax_decision_green",
        "production_shipping_configuration_verified",
        "production_shipping_rates_verified",
        "woocommerce_production_readonly_identity_green",
    ):
        require(prereq[key] is True, f"verified prerequisite regressed: {key}")
    require(prereq["japan_2026_tax_status"] == "exempt", "tax status drift")
    require(prereq["woocommerce_tax_enabled"] is False, "WooCommerce tax unexpectedly enabled")

    timing = sync["payment_timing_reconciliation"]
    require(timing["konbini_live_expiry_setting_verified"] is True, "Konbini Live expiry evidence missing")
    require(timing["konbini_live_expiry_days"] == 3, "Konbini Live expiry must remain exactly 3 days")
    require(
        timing["konbini_live_expiry_evidence_class"] == "owner_confirmed_live_dashboard_configuration",
        "Konbini Live expiry evidence classification drift",
    )
    require(timing["all_selected_methods_customer_facing_timing_finalized"] is False, "payment timing unexpectedly finalized")

    checkout = sync["woocommerce_checkout_verification"]
    require(checkout["sanitized_snapshot_run_green"] is True, "snapshot evidence missing")
    require(checkout["snapshot_run_id"] == 33776964709, "snapshot run id drift")
    require(checkout["snapshot_attempt"] == 2, "snapshot attempt drift")
    require(checkout["snapshot_artifact_id"] == 9902650701, "snapshot artifact drift")
    require(checkout["snapshot_network_read_only"] is True, "snapshot lost read-only boundary")
    require(checkout["snapshot_payment_execution_authorized"] is False, "snapshot gained payment authority")
    require(checkout["enabled_gateway_ids"] == ["komoju_credit_card", "woa_gateway", "komoju_konbini", "komoju_merpay", "komoju_paidy"], "enabled gateway evidence drift")
    require(checkout["approved_subset_matches_enabled_checkout_methods"] is True, "approved subset not verified")
    require(checkout["approved_subset_missing_from_woocommerce"] == [], "approved subset missing methods")
    for key in ("credit_card_gateway_enabled", "konbini_gateway_enabled", "merpay_gateway_enabled", "paidy_gateway_enabled", "order_approval_gateway_enabled", "bank_transfer_not_enabled", "pay_easy_not_exposed", "paypay_not_exposed", "rakuten_pay_not_exposed", "customer_facing_gateway_titles_reviewed", "no_real_payment_required_for_verification"):
        require(checkout[key] is True, f"checkout verification regressed: {key}")

    remediation = sync["woocommerce_komoju_remediation"]
    require(remediation["performed"] is True, "KOMOJU checkout remediation not recorded")
    require(remediation["fresh_readonly_snapshot_green"] is True, "post-change snapshot not green")

    legal = sync["legal_checkout_sync"]
    require(legal["tokushoho_payment_methods_match_checkout"] is True, "payment-method legal sync not green")
    require(legal["tokushoho_shipping_fees_match_checkout"] is True, "shipping/legal sync regressed")
    require(legal["tax_display_route_reconciled"] is True, "tax display reconciliation regressed")
    for key in ("tokushoho_publication_text_finalized", "tokushoho_payment_timing_match_checkout", "final_confirmation_screen_reviewed", "checkout_legal_sync_complete"):
        require(legal[key] is False, f"legal/timing gate changed without evidence: {key}")

    for key, value in sync["authority"].items():
        require(value is False, f"authority expanded unexpectedly: {key}")

    live = komoju["live_acceptance"]
    require(live["production_checkout_configuration_verified"] is True, "KOMOJU checkout config not green")
    require(live["konbini_live_expiry_setting_verified"] is True, "KOMOJU gate missing Konbini expiry evidence")
    require(live["konbini_live_expiry_days"] == 3, "KOMOJU gate Konbini expiry drift")
    require(komoju["live_dashboard_evidence"]["konbini_live_expiry_setting_verified"] is True, "Live dashboard expiry evidence missing")
    require(komoju["live_dashboard_evidence"]["konbini_live_expiry_days"] == 3, "Live dashboard expiry must be 3 days")
    require(komoju["execution"]["real_payment_execution_ready"] is False, "real payment execution unexpectedly ready")
    require(komoju["execution"]["real_payment_executed"] is False, "real payment unexpectedly recorded")
    require(staging["komoju"]["production_checkout_configuration_verified"] is True, "staging checkout config not green")
    require(staging["komoju"]["payment_execution_authorized"] is False, "payment execution authority drift")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    for phrase in ("workflow_dispatch:", "confirm_read_only", "payment_execution_authorized", "commerce/woocommerce/tools_production_readonly_checkout_snapshot.py", "retention-days: 1"):
        require(phrase in workflow, f"read-only workflow control missing: {phrase}")
    require('request\\([[:space:]]*\"(POST|PUT|DELETE|PATCH)\"' in workflow, "workflow mutation assertion missing")

    doc = DOC.read_text(encoding="utf-8")
    for phrase in (
        "APPROVED KOMOJU CHECKOUT SUBSET + LIVE KONBINI 3-DAY EXPIRY VERIFIED GREEN",
        "komoju_konbini",
        "komoju_merpay",
        "komoju_paidy",
        "cannot submit a payment",
        "3 days — VERIFIED GREEN",
        "real payment execution remains blocked",
        "PHIL_AI_OS_RUBY_CHECKOUT_PAYMENT_SUBSET_CONFIGURATION_AND_KONBINI_EXPIRY_GREEN_LEGAL_TIMING_PENDING_FAIL_CLOSED",
    ):
        require(phrase in doc, f"checkout/legal doc missing: {phrase}")

    require(
        sync["decision"] == "CHECKOUT_PAYMENT_SUBSET_CONFIGURATION_AND_KONBINI_EXPIRY_GREEN_LEGAL_TIMING_AND_FINAL_SCREEN_PENDING_FAIL_CLOSED",
        "decision drift",
    )

    print("PHIL_AI_OS_RUBY_CHECKOUT_PAYMENT_SUBSET_AND_KONBINI_EXPIRY_GREEN snapshot_attempt=2 konbini_expiry_days=3 payment_execution=false")
    print("PHIL_AI_OS_RUBY_CHECKOUT_LEGAL_TIMING_PENDING_FAIL_CLOSED final_screen=false production_publish=false")


if __name__ == "__main__":
    main()
