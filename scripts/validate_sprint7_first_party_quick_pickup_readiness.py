#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "ops/readiness/ruby-first-party-quick-pickup-readiness.json"
FIXTURE = ROOT / "apps/customer-experience/fixtures/first-party-quick-pickup.json"
ROUTE_HTML = ROOT / "apps/customer-experience/quick-pickup.html"
ROUTE_JS = ROOT / "apps/customer-experience/src/quick-pickup-route.mjs"
ROUTE_COPY = ROOT / "apps/customer-experience/src/quick-pickup-route-copy.mjs"
CHECKOUT_CONTRACT = ROOT / "apps/customer-experience/src/quick-pickup-checkout-contract.mjs"
ROADMAP = ROOT / "docs/MASTER_EXECUTIVE_ROADMAP_SCHEDULE_CONTROL.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHIL_AI_OS_FIRST_PARTY_QUICK_PICKUP_READINESS_FAILED: {message}")


def main() -> None:
    data = json.loads(READINESS.read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    route_html = ROUTE_HTML.read_text(encoding="utf-8")
    route_js = ROUTE_JS.read_text(encoding="utf-8")
    route_copy = ROUTE_COPY.read_text(encoding="utf-8")
    checkout_contract = CHECKOUT_CONTRACT.read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")

    require(data.get("version") == "ruby-first-party-quick-pickup-readiness-v1", "schema drift")
    require(data.get("air_mobile_order_required_for_v1") is False, "Air Mobile remains a V1 dependency")
    inventory = data.get("airregi_inventory")
    require(isinstance(inventory, dict), "AirREGI posture missing")
    require(inventory.get("api_verified") is False, "unverified AirREGI API cannot become a production assumption")
    require(inventory.get("csv_fallback_documented") is True, "CSV fallback record missing")
    require(inventory.get("authority") == "not_assumed", "AirREGI authority drift")

    scope = data.get("ceo_scope_authorization")
    require(isinstance(scope, dict) and scope.get("controlled_production_activation_authorized") is True, "CEO controlled-activation scope missing")
    require(scope.get("overrides_readiness") is False and scope.get("automatic_execution_authorized") is False, "scope authorization expanded")

    preparation = data.get("bounded_engineering_preparation")
    require(isinstance(preparation, dict), "bounded Quick Pickup engineering preparation missing")
    for key in (
        "fixture_inventory_decision_prepared",
        "fixture_capacity_and_cutoff_decision_prepared",
        "fixture_combined_decision_preview_prepared",
        "fixture_operator_disable_control_prepared",
        "isolated_customer_route_foundation_prepared",
        "bilingual_customer_copy_contract_prepared",
        "checkout_and_payment_contract_prepared",
    ):
        require(preparation.get(key) is True, f"bounded Quick Pickup preparation regressed: {key}")
    require(preparation.get("operator_disable_control_production_accepted") is False, "fixture disable control cannot satisfy production acceptance")
    require(preparation.get("bilingual_customer_copy_production_accepted") is False, "copy implementation cannot satisfy production acceptance")
    require(preparation.get("checkout_and_payment_contract_production_accepted") is False, "checkout contract implementation cannot satisfy production acceptance")
    require(preparation.get("production_readiness_effect") == "route_copy_and_checkout_contract_implementation_only", "bounded implementation must not claim broader production readiness")

    readiness = data.get("production_readiness")
    require(isinstance(readiness, dict), "production readiness missing")
    require(readiness.get("first_party_pickup_route_implemented") is True, "isolated Quick Pickup route foundation not recorded")
    for key in (
        "eligible_catalog_confirmed",
        "inventory_freshness_control_green",
        "capacity_and_cutoff_control_green",
        "checkout_and_payment_contract_green",
        "bilingual_customer_copy_green",
        "controlled_handset_and_operator_acceptance_green",
        "rollback_disable_path_green",
        "production_activation_ready",
    ):
        require(readiness.get(key) is False, f"unverified quick-pickup readiness unexpectedly green: {key}")

    require(fixture.get("fixture_only") is True, "Quick Pickup route fixture must remain fixture-only")
    require(fixture.get("route_implemented") is True, "Quick Pickup fixture route implementation drift")
    require(fixture.get("customer_route") == "/quick-pickup.html", "Quick Pickup customer route drift")
    for key in (
        "eligible_catalog_confirmed",
        "inventory_freshness_control_green",
        "capacity_and_cutoff_control_green",
        "checkout_and_payment_contract_green",
        "bilingual_customer_copy_green",
        "controlled_handset_and_operator_acceptance_green",
        "rollback_disable_path_green",
        "activation_authorized",
        "automatic_production_execution_authorized",
    ):
        require(fixture.get(key) is False, f"Quick Pickup fixture expanded readiness or authority: {key}")

    require('meta name="robots" content="noindex,nofollow"' in route_html, "isolated Quick Pickup route must remain noindex")
    require("Ordering disabled" in route_html, "Quick Pickup route missing fail-closed customer status")
    require("No customer order action" in route_html, "Quick Pickup route missing non-ordering footer")
    require('fetch("./fixtures/first-party-quick-pickup.json"' in route_js, "Quick Pickup route must consume fixture-only configuration")
    require("order_creation_authorized: false" in route_js, "Quick Pickup route must keep order creation false")
    require("payment_execution_authorized: false" in route_js, "Quick Pickup route must keep payment execution false")
    require("production_publish_authorized: false" in route_js, "Quick Pickup route must keep publication false")
    require("QUICK_PICKUP_ROUTE_COPY" in route_copy, "Quick Pickup bilingual copy contract missing")
    require("validateQuickPickupRouteCopy" in route_copy, "Quick Pickup bilingual copy validator missing")
    require("Ordering disabled" in route_copy and "注文無効" in route_copy, "Quick Pickup bilingual fail-closed copy missing")
    require("validateQuickPickupCheckoutContract" in checkout_contract, "Quick Pickup checkout contract validator missing")
    require("woocommerce_checkout_handoff" in checkout_contract, "Quick Pickup WooCommerce checkout boundary missing")
    for token in (
        "order_creation_authorized: false",
        "payment_execution_authorized: false",
        "live_mode_authorized: false",
        "inventory_mutation_authorized: false",
        "capacity_mutation_authorized: false",
        "production_publish_authorized: false",
    ):
        require(token in checkout_contract, f"Quick Pickup checkout contract missing fail-closed token: {token}")

    authority = data.get("authority")
    require(isinstance(authority, dict), "authority posture missing")
    for key, value in authority.items():
        require(value is False, f"quick-pickup authority expanded: {key}")

    require("first-party Quick Pickup" in roadmap, "roadmap first-party Quick Pickup reconciliation missing")
    require("Air Mobile Quick Pickup production URL" not in roadmap, "roadmap retains Air Mobile launch dependency")
    print("PHIL_AI_OS_FIRST_PARTY_QUICK_PICKUP_READINESS_GREEN air_mobile_v1=false route_implemented=true bilingual_copy_contract=prepared_not_accepted checkout_payment_contract=prepared_not_accepted production_ready=false ordering=false authority=false")


if __name__ == "__main__":
    main()
