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

    expected_subset = [
        "visa_mastercard",
        "jcb_amex_diners_discover",
        "konbini",
        "merpay",
        "paidy",
    ]
    subset = sync["production_payment_subset"]
    require(subset["ceo_approved"] is True, "payment subset approval drift")
    require(subset["selected"] == expected_subset, "payment subset drift")
    require(subset["disabled_initial_launch"] == ["bank_transfer", "pay_easy"], "initial launch disabled-set drift")
    require(subset["pending_provider_review"] == ["paypay"], "PayPay review state drift")
    require(subset["excluded"] == ["rakuten_pay"], "Rakuten Pay exclusion drift")
    require(komoju["production_payment_subset"]["enabled_for_initial_launch"] == expected_subset, "KOMOJU gate subset mismatch")

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
    require(timing["legacy_card_timing_source_captured"] is True, "legacy card timing source missing")
    require(timing["paidy_merchant_transaction_completion_documented"] is True, "Paidy timing evidence missing")
    require(timing["konbini_is_deferred_customer_payment"] is True, "Konbini timing model drift")
    require(timing["konbini_live_expiry_setting_verified"] is False, "Konbini Live expiry changed without evidence")
    require(timing["all_selected_methods_customer_facing_timing_finalized"] is False, "payment timing unexpectedly finalized")

    checkout = sync["woocommerce_checkout_verification"]
    require(checkout["get_only_payment_gateway_snapshot_capability_ready"] is True, "GET-only checkout snapshot capability missing")
    require(checkout["payment_gateway_snapshot_endpoint"] == "/wp-json/wc/v3/payment_gateways", "checkout snapshot endpoint drift")
    for key in (
        "sanitized_snapshot_run_green",
        "approved_subset_matches_enabled_checkout_methods",
        "disabled_methods_absent_from_checkout",
        "customer_facing_gateway_titles_reviewed",
    ):
        require(checkout[key] is False, f"checkout verification changed without live read-only evidence: {key}")
    require(checkout["no_real_payment_required_for_verification"] is True, "checkout verification must remain non-charging")

    legal = sync["legal_checkout_sync"]
    require(legal["tokushoho_payment_method_subset_reconciled_in_readiness_record"] is True, "payment subset legal reconciliation missing")
    require(legal["tokushoho_shipping_fees_match_checkout"] is True, "verified shipping/legal sync regressed")
    require(legal["tax_display_route_reconciled"] is True, "tax display reconciliation regressed")
    for key in (
        "tokushoho_publication_text_finalized",
        "tokushoho_payment_methods_match_checkout",
        "tokushoho_payment_timing_match_checkout",
        "final_confirmation_screen_reviewed",
        "checkout_legal_sync_complete",
    ):
        require(legal[key] is False, f"legal/checkout gate changed without evidence: {key}")

    authority = sync["authority"]
    for key, value in authority.items():
        require(value is False, f"authority expanded unexpectedly: {key}")

    require(staging["komoju"]["production_enabled_payment_methods_finalized"] is True, "staging subset finalization regressed")
    require(staging["komoju"]["production_checkout_configuration_verified"] is False, "checkout configuration unexpectedly verified")
    require(staging["komoju"]["payment_execution_authorized"] is False, "payment execution authority drift")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    for phrase in (
        "workflow_dispatch:",
        "confirm_read_only",
        "payment_execution_authorized",
        "commerce/woocommerce/tools_production_readonly_checkout_snapshot.py",
        "retention-days: 1",
    ):
        require(phrase in workflow, f"read-only checkout workflow control missing: {phrase}")
    require('request\\([[:space:]]*\"(POST|PUT|DELETE|PATCH)\"' in workflow, "workflow mutation assertion missing")

    doc = DOC.read_text(encoding="utf-8")
    for phrase in (
        "PAYMENT SUBSET / TAX / SHIPPING RECONCILED",
        "Konbini is a deferred customer payment",
        "cannot submit a payment",
        "PHIL_AI_OS_RUBY_CHECKOUT_LEGAL_PAYMENT_SYNC_PREPARED_FAIL_CLOSED",
    ):
        require(phrase in doc, f"checkout/legal synchronization documentation missing: {phrase}")

    require(sync["decision"] == "PAYMENT_SUBSET_SHIPPING_AND_TAX_RECONCILED_CHECKOUT_CONFIGURATION_PENDING_FAIL_CLOSED", "decision drift")

    print("PHIL_AI_OS_RUBY_CHECKOUT_LEGAL_SYNC_PREPARED_GREEN payment_subset=true shipping=true tax_exempt=true checkout_snapshot_ready=true")
    print("PHIL_AI_OS_RUBY_CHECKOUT_CONFIGURATION_PENDING_FAIL_CLOSED payment_execution=false production_publish=false")


if __name__ == "__main__":
    main()
