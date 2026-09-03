#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "ops/readiness/ruby-production-current-state-overlay-2026-09-02.json"
GO_NO_GO = ROOT / "ops/readiness/ruby-final-go-no-go-gate-2026-09-02.json"
KOMOJU = ROOT / "ops/readiness/ruby-komoju-live-acceptance-gate-2026-09-02.json"
SMS = ROOT / "ops/readiness/ruby-sms-provider-activation-gate-2026-09-02.json"
RECOVERY = ROOT / "ops/readiness/ruby-launch-recovery-acceptance-gate-2026-09-02.json"
TAX = ROOT / "ops/readiness/ruby-japan-consumption-tax-status-2026-09-03.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_SPRINT_7_PRODUCTION_CURRENT_STATE_FAILED: {message}")


def main() -> None:
    overlay = load(OVERLAY)
    go = load(GO_NO_GO)
    komoju = load(KOMOJU)
    sms = load(SMS)
    recovery = load(RECOVERY)
    tax = load(TAX)

    governance = overlay["governance"]
    require(governance["autonomy"] == "A0", "autonomy drift")
    require(governance["task_class"] == "general", "task-class drift")
    require(governance["specialists_enabled"] is False, "specialists unexpectedly enabled")
    require(governance["mission_control_mutation_authorized"] is False, "Mission Control mutation authority drift")
    require(governance["automatic_production_execution_authorized"] is False, "automatic production execution drift")

    scope = overlay["ceo_activation_scope"]
    for key in ("woocommerce_production_activation", "komoju_live_mode", "production_sms_sending", "public_domain_dns_cutover", "final_launch_signoff_process"):
        require(scope[key] is True, f"CEO scope approval drift: {key}")
    require(scope["scope_approval_overrides_readiness"] is False, "scope approval incorrectly overrides readiness")

    woo = overlay["woocommerce"]
    require(woo["production_readonly_identity_green"] is True, "Woo read-only identity regressed")
    require(woo["production_readonly_preflight_run_id"] == 33630247231, "Woo read-only evidence run drift")
    require(woo["production_mutation_ready"] is False, "Woo mutation became ready unexpectedly")
    require(woo["catalog_write_ready"] is False, "catalog write became ready unexpectedly")
    require(woo["tax_decision_green"] is True and woo["tax_configuration_route"] == "disabled", "Japan tax route drift")
    require(woo["tax_write_ready"] is False, "tax write became ready unexpectedly")

    inputs = overlay["business_inputs"]
    require(inputs["final_production_catalog_ready"] is False, "final catalog changed without reconciliation")
    require(inputs["japan_tax_and_qualified_invoice_evidence_ready"] is True, "Japan tax evidence should remain GREEN")
    require(inputs["air_mobile_order_quick_pickup_production_url_ready"] is False, "Air Mobile URL changed without reconciliation")

    require(tax["decision"]["consumption_tax_status"] == "exempt", "tax status drift")
    require(tax["decision"]["qualified_invoice_status"] == "not_registered", "qualified invoice status drift")
    require(tax["decision"]["tax_decision_ready"] is True, "tax decision evidence not GREEN")
    require(tax["authority"]["tax_write_ready"] is False and tax["authority"]["mutation_authorized"] is False, "tax evidence expanded authority")

    approved = ["visa_mastercard", "jcb_amex_diners_discover", "konbini", "merpay", "paidy"]
    require(komoju["current_mode"] == "live_dashboard_selected", "KOMOJU Live dashboard selection evidence regressed")
    require(komoju["live_dashboard_evidence"]["owner_supplied_dashboard_reviewed"] is True, "KOMOJU owner dashboard evidence missing")
    require(komoju["live_acceptance"]["merchant_live_mode_approval_verified"] is True, "KOMOJU merchant Live evidence regressed")
    require(komoju["live_acceptance"]["merchant_available_payment_methods_verified"] is True, "KOMOJU method availability evidence regressed")
    require(komoju["production_payment_subset"]["ceo_approved"] is True, "KOMOJU production subset lost CEO approval")
    require(komoju["production_payment_subset"]["enabled_for_initial_launch"] == approved, "KOMOJU approved subset drift")
    require(komoju["live_acceptance"]["production_enabled_payment_methods_finalized"] is True, "KOMOJU payment subset should remain finalized")
    require(komoju["live_acceptance"]["production_checkout_configuration_verified"] is True, "KOMOJU checkout verification regressed")
    require(komoju["live_acceptance"]["production_checkout_verification_run_id"] == 33776964709 and komoju["live_acceptance"]["production_checkout_verification_attempt"] == 2, "KOMOJU checkout verification evidence drift")
    require(komoju["live_acceptance"]["japan_tax_and_qualified_invoice_evidence_ready"] is True, "KOMOJU tax prerequisite regressed")
    require(komoju["execution"]["live_mode_authorized_by_readiness"] is False, "KOMOJU live execution authority expanded")
    require(komoju["execution"]["real_payment_execution_ready"] is False and komoju["execution"]["real_payment_executed"] is False, "KOMOJU real payment state expanded")

    ok = overlay["komoju"]
    require(ok["live_dashboard_selected"] is True, "overlay lost KOMOJU Live dashboard evidence")
    require(ok["merchant_live_mode_approval_verified"] is True and ok["merchant_available_payment_methods_verified"] is True, "overlay lost KOMOJU merchant evidence")
    require(ok["production_enabled_payment_methods_finalized"] is True, "overlay lost finalized payment subset")
    require(ok["approved_initial_launch_subset"] == approved, "overlay approved payment subset drift")
    require(ok["production_checkout_configuration_verified"] is True, "overlay checkout config verification regressed")
    require(ok["production_checkout_verification_run_id"] == 33776964709 and ok["production_checkout_verification_attempt"] == 2, "overlay checkout evidence drift")
    require(ok["checkout_legal_timing_sync_complete"] is False, "overlay legal/timing sync unexpectedly complete")
    require(ok["live_acceptance_green"] is False and ok["real_payment_execution_ready"] is False, "overlay KOMOJU acceptance expanded unexpectedly")

    require(sms["provider_selection"]["formally_selected"] is True, "SMS provider selection should be GREEN")
    require(sms["provider_selection"]["selected_provider"] == "twilio", "selected SMS provider must remain Twilio")
    require(sms["activation_acceptance"]["production_sending_ready"] is False, "SMS production sending unexpectedly ready")
    require(sms["execution"]["live_sms_authorized_by_readiness"] is False and sms["execution"]["live_sms_sent"] is False, "SMS authority expanded")
    require(overlay["sms"]["selected_provider"] == "twilio" and overlay["sms"]["formal_provider_selected"] is True, "overlay Twilio selection drift")
    require(overlay["sms"]["production_sending_ready"] is False, "overlay SMS sending unexpectedly ready")

    require(recovery["current_baseline"]["status"] == "green_current_not_launch_fresh", "recovery baseline status drift")
    require(recovery["execution"]["launch_recovery_gate_green"] is False, "recovery incorrectly launch-fresh")
    require(recovery["execution"]["cutover_ready_from_recovery_perspective"] is False, "recovery incorrectly permits cutover")

    require(go["technical_baseline"]["woocommerce_readonly_identity_green"] is True, "Go/No-Go lost Woo read-only GREEN")
    require(go["technical_baseline"]["japan_tax_decision_green"] is True, "Go/No-Go lost Japan tax GREEN")
    require(go["required_launch_gates"]["japan_tax_and_qualified_invoice_evidence_ready"] is True, "Go/No-Go tax gate should be GREEN")
    for key, value in go["required_launch_gates"].items():
        if key == "japan_tax_and_qualified_invoice_evidence_ready":
            continue
        require(value is False, f"launch gate requires explicit reconciliation before GREEN: {key}")
    for key, value in go["execution"].items():
        require(value is False, f"live execution readiness unexpectedly true: {key}")
    require(go["decision"] == "NO_GO_PENDING_REMAINING_REQUIRED_INPUTS_AND_LIVE_ACCEPTANCE", "Go/No-Go decision drift")

    require(overlay["launch"]["live_launch_authorized_by_readiness"] is False, "overlay unexpectedly authorizes live launch")
    require(overlay["decision"] == "CONTROL_POSTURE_GREEN_LAUNCH_PENDING_FAIL_CLOSED", "overlay decision drift")

    print("PHIL_AI_OS_SPRINT_7_PRODUCTION_CURRENT_STATE_FAIL_CLOSED_GREEN tax=green twilio=selected komoju_subset=finalized checkout_config=true")
    print("PHIL_AI_OS_SPRINT_7_FINAL_GO_NO_GO_PENDING_FAIL_CLOSED")


if __name__ == "__main__":
    main()
