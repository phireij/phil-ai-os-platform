#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parents[1]
CONTRACT_ROOT = REPO_ROOT / "contracts" / "cx"
FIXTURE_ROOT = CONTRACT_ROOT / "fixtures"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_SPRINT_4_CX_CONTRACT_COMPATIBILITY_FAILED: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def schema_const(schema: dict, property_name: str):
    try:
        return schema["properties"][property_name]["const"]
    except KeyError as exc:
        fail(f"schema missing const for {property_name}: {exc}")


def item_pairs(items: list[dict], quantity_key: str = "quantity") -> list[tuple[str, int]]:
    return [(str(item["sku"]), int(item[quantity_key])) for item in items]


def main() -> None:
    checkout_schema = load(CONTRACT_ROOT / "checkout-intent.schema.json")
    readiness_schema = load(CONTRACT_ROOT / "checkout-readiness.schema.json")
    payment_schema = load(CONTRACT_ROOT / "payment-handoff-intent.schema.json")

    checkout = load(FIXTURE_ROOT / "checkout-intent.multi-item.sample.json")
    readiness = load(FIXTURE_ROOT / "checkout-readiness.multi-item.sample.json")
    payment = load(FIXTURE_ROOT / "payment-handoff.sample.json")
    catalog = load(APP_ROOT / "fixtures" / "catalog.json")

    # Authority invariants must be present in both schema and fixture layers.
    require(schema_const(checkout_schema, "mutation_authorized") is False, "checkout schema must lock mutation authority false")
    require(schema_const(readiness_schema, "mutation_authorized") is False, "readiness schema must lock mutation authority false")
    require(schema_const(payment_schema, "provider") == "komoju", "payment schema must lock provider to KOMOJU")
    require(schema_const(payment_schema, "integration_mode") == "woocommerce_plugin", "payment schema must lock WooCommerce plugin mode")
    require(schema_const(payment_schema, "connection_state") == "not_configured", "payment schema connection must remain not_configured")
    for field in ("order_creation_authorized", "payment_execution_authorized", "live_mode_authorized"):
        require(schema_const(payment_schema, field) is False, f"payment schema must lock {field}=false")
        require(payment.get(field) is False, f"payment fixture must keep {field}=false")

    require(checkout.get("mutation_authorized") is False, "checkout fixture gained mutation authority")
    require(readiness.get("mutation_authorized") is False, "readiness fixture gained mutation authority")
    require(readiness.get("ready") is True and readiness.get("blockers") == [], "GREEN readiness fixture is inconsistent")
    require(payment.get("external_order_reference") is None, "payment fixture must not claim a WooCommerce order exists")

    # Identity / customer-state continuity.
    intent_id = checkout.get("intent_id")
    require(intent_id and readiness.get("intent_id") == intent_id, "checkout/readiness intent identity mismatch")
    require(payment.get("checkout_intent_id") == intent_id, "payment handoff does not reference checkout intent")
    require(payment.get("locale") == checkout.get("locale"), "locale drift between checkout and payment")
    require(payment.get("fulfillment") == checkout.get("fulfillment") == "pickup", "fulfillment drift or non-pickup flow")
    require(payment.get("requested_pickup_at") == checkout.get("requested_pickup_at"), "pickup timestamp drift")

    checkout_pairs = item_pairs(checkout.get("items", []))
    readiness_pairs = item_pairs(readiness.get("items", []), "requested_quantity")
    payment_pairs = item_pairs(payment.get("line_items", []))
    require(checkout_pairs and checkout_pairs == readiness_pairs == payment_pairs, "SKU/quantity drift across checkout/readiness/payment")
    require(len({sku for sku, _ in checkout_pairs}) == len(checkout_pairs), "duplicate SKU in multi-item fixture")

    # Catalog → pricing → payment total continuity.
    require(catalog.get("fixture_only") is True, "catalog must remain fixture-only")
    catalog_by_sku = {product["sku"]: product for product in catalog.get("products", [])}
    expected_total = 0
    for payment_line, (sku, quantity) in zip(payment["line_items"], checkout_pairs, strict=True):
        product = catalog_by_sku.get(sku)
        require(product is not None, f"checkout SKU missing from catalog: {sku}")
        require(product.get("availability") == "in_stock", f"GREEN fixture uses unavailable SKU: {sku}")
        price = product.get("price", {})
        require(price.get("currency") == "JPY", f"pilot fixture currency must be JPY: {sku}")
        unit = int(price.get("amount"))
        line_total = unit * quantity
        expected_total += line_total
        require(payment_line.get("currency") == "JPY", f"payment line currency drift: {sku}")
        require(payment_line.get("unit_amount") == str(unit), f"unit amount drift: {sku}")
        require(payment_line.get("line_amount") == str(line_total), f"line amount drift: {sku}")

    require(payment.get("amount") == {"amount": str(expected_total), "currency": "JPY"}, "payment total does not match catalog pricing")

    # Contract fixtures must not accidentally contain merchant credentials.
    contract_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            FIXTURE_ROOT / "checkout-intent.multi-item.sample.json",
            FIXTURE_ROOT / "checkout-readiness.multi-item.sample.json",
            FIXTURE_ROOT / "payment-handoff.sample.json",
        )
    )
    for label, pattern in {
        "WooCommerce key": r"\b(?:ck|cs)_[A-Za-z0-9]{8,}",
        "KOMOJU secret/publishable key": r"\b(?:sk|pk)_(?:test|live)_[A-Za-z0-9_-]{6,}",
    }.items():
        require(re.search(pattern, contract_text, flags=re.IGNORECASE) is None, f"credential-like {label} found in fixtures")

    print(f"PHIL_AI_OS_SPRINT_4_CX_CONTRACT_COMPATIBILITY_GREEN total_jpy={expected_total} items={len(checkout_pairs)}")


if __name__ == "__main__":
    main()
