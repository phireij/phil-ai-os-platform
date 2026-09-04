#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "ops/readiness/ruby-komoju-paypay-provider-capability-2026-09-04.json"
CHECKOUT = ROOT / "ops/readiness/ruby-checkout-legal-payment-shipping-sync-2026-09-04.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_PAYPAY_PROVIDER_CAPABILITY_FAILED: {message}")


def main() -> None:
    data = json.loads(RECORD.read_text(encoding="utf-8"))
    checkout = json.loads(CHECKOUT.read_text(encoding="utf-8"))

    require(data.get("version") == "ruby-komoju-paypay-provider-capability-v1", "schema drift")
    require(data.get("scope") == "provider_capability_only", "scope drift")
    require(data.get("provider") == "KOMOJU", "provider drift")
    require(data.get("payment_method") == "PayPay", "payment method drift")
    require(data.get("payment_method_slug") == "paypay", "slug drift")
    require(data.get("currency") == "JPY", "currency drift")
    require(data.get("official_provider_capability_confirmed") is True, "provider capability not confirmed")
    require(data.get("official_woocommerce_documentation_lists_paypay") is True, "WooCommerce capability evidence missing")

    evidence = data.get("evidence")
    require(isinstance(evidence, list) and len(evidence) >= 2, "official evidence set incomplete")
    urls = {item.get("url") for item in evidence if isinstance(item, dict)}
    require("https://doc.komoju.com/page/supported-payment-methods" in urls, "supported-methods evidence missing")
    require("https://doc.komoju.com/docs/getting-started-with-woocommerce" in urls, "WooCommerce guide evidence missing")

    merchant = data["ruby_merchant_live_state"]
    for key in (
        "merchant_specific_paypay_availability_verified",
        "merchant_specific_live_dashboard_evidence_captured",
        "woocommerce_paypay_gateway_exposed",
        "woocommerce_paypay_gateway_enabled",
        "initial_launch_selection_approved",
    ):
        require(merchant[key] is False, f"merchant-specific gate expanded without evidence: {key}")
    require(
        merchant["status"] == "merchant_specific_live_availability_pending_readonly_evidence",
        "merchant-specific status drift",
    )

    interpretation = data["interpretation"]
    require(interpretation["provider_support_question_resolved"] is True, "provider support remains unresolved")
    require(interpretation["merchant_enablement_question_resolved"] is False, "merchant enablement incorrectly resolved")
    require(interpretation["does_not_change_approved_initial_payment_subset"] is True, "initial subset boundary lost")
    require(interpretation["does_not_authorize_paypay_activation"] is True, "PayPay activation boundary lost")

    subset = checkout["production_payment_subset"]
    require(subset["pending_provider_review"] == ["paypay"], "canonical checkout record changed before merchant evidence")
    require("paypay" not in subset["selected"], "PayPay entered approved initial subset")
    require(checkout["woocommerce_checkout_verification"]["paypay_not_exposed"] is True, "verified WooCommerce snapshot unexpectedly exposes PayPay")

    for key, value in data["authority"].items():
        require(value is False, f"authority expanded unexpectedly: {key}")

    require(
        data["decision"] == "PAYPAY_PROVIDER_CAPABILITY_GREEN_MERCHANT_LIVE_AVAILABILITY_PENDING_FAIL_CLOSED",
        "decision drift",
    )
    print("PHIL_AI_OS_PAYPAY_PROVIDER_CAPABILITY_GREEN provider_support=true merchant_live_availability=false activation=false")


if __name__ == "__main__":
    main()
