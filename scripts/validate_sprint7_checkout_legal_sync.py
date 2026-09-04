#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "ops/readiness/ruby-checkout-legal-payment-shipping-sync-2026-09-04.json"
KOMOJU = ROOT / "ops/readiness/ruby-komoju-live-acceptance-gate-2026-09-02.json"
STAGING = ROOT / "ops/readiness/ruby-woocommerce-komoju-staging-readiness.json"
CANDIDATE_RECORD = ROOT / "ops/readiness/ruby-tokushoho-publication-candidate-2026-09-04.json"
APPROVAL_RECORD = ROOT / "ops/readiness/ruby-tokushoho-owner-approval-2026-09-04.json"
PAYPAY_RECORD = ROOT / "ops/readiness/ruby-komoju-paypay-provider-capability-2026-09-04.json"
DOC = ROOT / "docs/RUBY_CHECKOUT_LEGAL_PAYMENT_SHIPPING_SYNC_2026-09-04.md"
TIMING_DOC = ROOT / "docs/RUBY_PAYMENT_TIMING_TOKUSHOHO_RECONCILIATION_2026-09-04.md"
CANDIDATE_DOC = ROOT / "docs/RUBY_TOKUSHOHO_FINAL_PUBLICATION_CANDIDATE_2026-09-04.md"
SCREEN_CHECKLIST = ROOT / "docs/RUBY_FINAL_CONFIRMATION_SCREEN_REVIEW_CHECKLIST_2026-09-04.md"
WORKFLOW = ROOT / ".github/workflows/commerce-woocommerce-production-readonly-checkout-snapshot.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_RUBY_CHECKOUT_LEGAL_SYNC_FAILED: {message}")


def load(path: Path) -> dict:
    require(path.is_file(), f"required evidence missing: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def require_false_authority(payload: dict, label: str) -> None:
    for key, value in payload.items():
        require(value is False, f"{label} authority expanded unexpectedly: {key}")


def main() -> None:
    sync = load(SYNC)
    komoju = load(KOMOJU)
    staging = load(STAGING)
    candidate = load(CANDIDATE_RECORD)
    approval_record = load(APPROVAL_RECORD)
    paypay = load(PAYPAY_RECORD)

    require(sync.get("version") == "ruby-checkout-legal-payment-shipping-sync-v4", "checkout sync schema drift")

    expected_subset = ["visa_mastercard", "jcb_amex_diners_discover", "konbini", "merpay", "paidy"]
    subset = sync["production_payment_subset"]
    require(subset["ceo_approved"] is True, "payment subset approval drift")
    require(subset["selected"] == expected_subset, "payment subset drift")
    require(subset["disabled_initial_launch"] == ["bank_transfer", "pay_easy"], "disabled-set drift")
    require(subset["provider_capability_confirmed_not_selected"] == ["paypay"], "PayPay provider-capability classification drift")
    require(subset["pending_merchant_live_availability"] == ["paypay"], "PayPay merchant-specific availability classification drift")
    require(subset["excluded"] == ["rakuten_pay"], "Rakuten exclusion drift")

    require(paypay["scope"] == "provider_capability_only", "PayPay evidence scope expanded")
    require(paypay["official_provider_capability_confirmed"] is True, "PayPay provider capability no longer GREEN")
    require(paypay["ruby_merchant_live_state"]["merchant_specific_paypay_availability_verified"] is False, "PayPay merchant availability changed without new evidence")
    require(paypay["ruby_merchant_live_state"]["initial_launch_selection_approved"] is False, "PayPay unexpectedly entered launch subset")
    require(paypay["interpretation"]["does_not_change_approved_initial_payment_subset"] is True, "PayPay capability changed approved subset")
    require_false_authority(paypay["authority"], "PayPay")

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
    require(timing["konbini_live_expiry_evidence_class"] == "owner_confirmed_live_dashboard_configuration", "Konbini expiry evidence-class drift")
    require(timing["all_selected_methods_customer_facing_timing_finalized"] is True, "payment timing reconciliation regressed")
    require(timing["reconciliation_doc"] == "docs/RUBY_PAYMENT_TIMING_TOKUSHOHO_RECONCILIATION_2026-09-04.md", "payment timing evidence link drift")

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
    for key in (
        "credit_card_gateway_enabled", "konbini_gateway_enabled", "merpay_gateway_enabled", "paidy_gateway_enabled",
        "order_approval_gateway_enabled", "bank_transfer_not_enabled", "pay_easy_not_exposed", "paypay_not_exposed",
        "rakuten_pay_not_exposed", "customer_facing_gateway_titles_reviewed", "no_real_payment_required_for_verification",
    ):
        require(checkout[key] is True, f"checkout verification regressed: {key}")

    remediation = sync["woocommerce_komoju_remediation"]
    require(remediation["performed"] is True, "KOMOJU checkout remediation not recorded")
    require(remediation["fresh_readonly_snapshot_green"] is True, "post-change snapshot not GREEN")

    legal = sync["legal_checkout_sync"]
    require(legal["tokushoho_publication_candidate_ready"] is True, "Tokushoho candidate not ready")
    require(legal["tokushoho_publication_candidate_ref"] == "docs/RUBY_TOKUSHOHO_FINAL_PUBLICATION_CANDIDATE_2026-09-04.md", "Tokushoho candidate ref drift")
    require(legal["tokushoho_candidate_text_approval_recorded"] is True, "CEO candidate-text approval missing")
    require(legal["tokushoho_candidate_text_approved"] is True, "CEO candidate-text approval not GREEN")
    require(legal["tokushoho_candidate_text_approval_ref"] == "ops/readiness/ruby-tokushoho-owner-approval-2026-09-04.json", "approval evidence ref drift")
    require(legal["tokushoho_publication_execution_approved"] is False, "candidate-text approval leaked into publication execution")
    require(legal["tokushoho_published"] is False, "Tokushoho unexpectedly published")
    for key in (
        "tokushoho_payment_methods_match_checkout", "tokushoho_payment_timing_match_checkout",
        "tokushoho_shipping_fees_match_checkout", "tax_display_route_reconciled", "static_confirmation_screen_checklist_ready",
    ):
        require(legal[key] is True, f"legal checkout synchronization regressed: {key}")
    require(legal["static_confirmation_screen_checklist_ref"] == "docs/RUBY_FINAL_CONFIRMATION_SCREEN_REVIEW_CHECKLIST_2026-09-04.md", "screen checklist ref drift")
    require(legal["final_confirmation_screen_reviewed"] is False, "actual final screen changed without evidence")
    require(legal["checkout_legal_sync_complete"] is False, "checkout legal sync closed before actual-screen acceptance")
    require_false_authority(sync["authority"], "checkout sync")

    require(candidate["version"] == "ruby-tokushoho-publication-candidate-v1", "candidate schema drift")
    require(candidate["executive_roadmap"]["current_primary_sprint"] == 3, "candidate changed current sprint")
    require(candidate["executive_roadmap"]["sprint4_parallel_acceleration"] is True, "candidate lost Sprint 4 parallel state")
    require(candidate["executive_roadmap"]["formal_sprint4_entry"] is False, "candidate incorrectly entered Sprint 4")
    cand = candidate["candidate"]
    require(cand["publication_candidate_ready"] is True, "publication candidate not GREEN")
    require(cand["japan_2026_consumption_tax_status"] == "exempt", "candidate tax drift")
    require(cand["qualified_invoice_status"] == "not_registered", "Qualified Invoice drift")
    require(cand["woocommerce_tax_enabled"] is False, "candidate unexpectedly enabled tax")
    require(cand["konbini_live_expiry_days"] == 3, "candidate Konbini expiry drift")

    screen = candidate["confirmation_screen"]
    require(screen["static_compliance_checklist_ready"] is True, "candidate static checklist missing")
    require(screen["actual_final_screen_reviewed"] is False, "actual final screen cannot be GREEN without evidence")
    require(screen["actual_final_screen_evidence_captured"] is False, "actual-screen evidence unexpectedly claimed")
    require(screen["real_order_required_for_review"] is False, "real order incorrectly required")
    require(screen["real_payment_required_for_review"] is False, "real payment incorrectly required")

    approval = candidate["approval_and_publication"]
    require(approval["candidate_text_approval_recorded"] is True, "canonical candidate lost CEO text approval")
    require(approval["candidate_text_approved"] is True, "canonical candidate text not approved")
    require(approval["candidate_text_approval_ref"] == "ops/readiness/ruby-tokushoho-owner-approval-2026-09-04.json", "canonical approval ref drift")
    require(approval["owner_publication_approval_recorded"] is False, "publication execution approval unexpectedly recorded")
    require(approval["tokushoho_publication_approved"] is False, "publication unexpectedly approved")
    require(approval["published"] is False, "candidate unexpectedly published")
    require(approval["checkout_legal_sync_complete"] is False, "checkout sync closed prematurely")
    require_false_authority(candidate["authority"], "canonical candidate")

    require(approval_record["decision_scope"] == "candidate_text_approval_only", "CEO approval scope drift")
    require(approval_record["approval_recorded"] is True, "CEO approval record not recorded")
    require(approval_record["candidate_text_approved"] is True, "CEO approval record not approved")
    require_false_authority(approval_record["authority"], "CEO approval record")

    live = komoju["live_acceptance"]
    require(live["production_checkout_configuration_verified"] is True, "KOMOJU checkout config not GREEN")
    require(live["konbini_live_expiry_setting_verified"] is True and live["konbini_live_expiry_days"] == 3, "KOMOJU gate expiry drift")
    require(komoju["execution"]["real_payment_execution_ready"] is False, "real payment execution unexpectedly ready")
    require(komoju["execution"]["real_payment_executed"] is False, "real payment unexpectedly recorded")
    require(staging["komoju"]["production_checkout_configuration_verified"] is True, "staging checkout config not GREEN")
    require(staging["komoju"]["payment_execution_authorized"] is False, "payment execution authority drift")

    for path in (DOC, TIMING_DOC, CANDIDATE_DOC, SCREEN_CHECKLIST, WORKFLOW):
        require(path.is_file(), f"required supporting file missing: {path.relative_to(ROOT)}")

    candidate_doc = CANDIDATE_DOC.read_text(encoding="utf-8")
    for phrase in (
        "PUBLICATION CANDIDATE READY",
        "その他の地域：配送地域により 1,500円〜1,800円",
        "Other regions: ¥1,500–¥1,800 depending on delivery area",
        "tokushoho_publication_approved: false",
        "actual_final_confirmation_screen_reviewed: false",
        "payment_execution_authorized: false",
    ):
        require(phrase in candidate_doc, f"Tokushoho candidate wording/boundary missing: {phrase}")

    require(sync["decision"] == "CHECKOUT_PAYMENT_TIMING_AND_TOKUSHOHO_TEXT_APPROVED_FINAL_SCREEN_AND_PUBLICATION_EXECUTION_PENDING_FAIL_CLOSED", "decision drift")
    print("PHIL_AI_OS_RUBY_TOKUSHOHO_TEXT_APPROVAL_GREEN candidate_text=true publication_execution=false published=false")
    print("PHIL_AI_OS_RUBY_CONFIRMATION_SCREEN_STATIC_CHECKLIST_GREEN actual_screen=false real_payment=false")
    print("PHIL_AI_OS_RUBY_CHECKOUT_FINAL_SCREEN_AND_PUBLICATION_EXECUTION_PENDING_FAIL_CLOSED production_publish=false")


if __name__ == "__main__":
    main()
