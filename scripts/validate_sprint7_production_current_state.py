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

    governance = overlay["governance"]
    require(governance["autonomy"] == "A0", "autonomy drift")
    require(governance["task_class"] == "general", "task-class drift")
    require(governance["specialists_enabled"] is False, "specialists unexpectedly enabled")
    require(governance["mission_control_mutation_authorized"] is False, "Mission Control mutation authority drift")
    require(governance["automatic_production_execution_authorized"] is False, "automatic production execution drift")

    scope = overlay["ceo_activation_scope"]
    for key in (
        "woocommerce_production_activation",
        "komoju_live_mode",
        "production_sms_sending",
        "public_domain_dns_cutover",
        "final_launch_signoff_process",
    ):
        require(scope[key] is True, f"CEO scope approval drift: {key}")
    require(scope["scope_approval_overrides_readiness"] is False, "scope approval incorrectly overrides readiness")

    woo = overlay["woocommerce"]
    require(woo["production_readonly_identity_green"] is True, "Woo read-only identity regressed")
    require(woo["production_readonly_preflight_run_id"] == 33630247231, "Woo read-only evidence run drift")
    require(woo["production_mutation_ready"] is False, "Woo mutation became ready unexpectedly")
    require(woo["catalog_write_ready"] is False, "catalog write became ready unexpectedly")
    require(woo["tax_write_ready"] is False, "tax write became ready unexpectedly")

    inputs = overlay["business_inputs"]
    for key in (
        "final_production_catalog_ready",
        "japan_tax_and_qualified_invoice_evidence_ready",
        "air_mobile_order_quick_pickup_production_url_ready",
    ):
        require(inputs[key] is False, f"pending business input changed without reconciliation: {key}")

    require(komoju["current_mode"] == "test_mode", "KOMOJU not in Test Mode")
    require(komoju["live_acceptance"]["merchant_live_mode_approval_verified"] is False, "KOMOJU merchant Live approval unexpectedly GREEN")
    require(komoju["execution"]["real_payment_execution_ready"] is False, "KOMOJU real payment unexpectedly ready")

    require(sms["provider_selection"]["formally_selected"] is False, "SMS provider unexpectedly selected")
    require(sms["activation_acceptance"]["production_sending_ready"] is False, "SMS production sending unexpectedly ready")
    require(sms["execution"]["live_sms_sent"] is False, "live SMS evidence unexpectedly true")

    require(recovery["current_baseline"]["status"] == "green_current_not_launch_fresh", "recovery baseline status drift")
    require(recovery["execution"]["launch_recovery_gate_green"] is False, "recovery incorrectly marked launch-fresh")
    require(recovery["execution"]["cutover_ready_from_recovery_perspective"] is False, "recovery incorrectly permits cutover")

    require(go["technical_baseline"]["woocommerce_readonly_identity_green"] is True, "Go/No-Go lost Woo read-only GREEN")
    for key, value in go["required_launch_gates"].items():
        require(value is False, f"launch gate requires explicit reconciliation before GREEN: {key}")
    for key, value in go["execution"].items():
        require(value is False, f"live execution readiness unexpectedly true: {key}")
    require(go["decision"] == "NO_GO_PENDING_REQUIRED_INPUTS_AND_LIVE_ACCEPTANCE", "Go/No-Go decision drift")

    require(overlay["launch"]["live_launch_authorized_by_readiness"] is False, "overlay unexpectedly authorizes live launch")
    require(overlay["decision"] == "CONTROL_POSTURE_GREEN_LAUNCH_PENDING_FAIL_CLOSED", "overlay decision drift")

    print("PHIL_AI_OS_SPRINT_7_PRODUCTION_CURRENT_STATE_FAIL_CLOSED_GREEN")
    print("PHIL_AI_OS_SPRINT_7_FINAL_GO_NO_GO_PENDING_FAIL_CLOSED")


if __name__ == "__main__":
    main()
