from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from phil_ai_os_woocommerce.catalog_readiness import evaluate_catalog_tax_readiness
from phil_ai_os_woocommerce.models import ContractValidationError

TAX_EVIDENCE = REPO_ROOT / "ops/readiness/ruby-japan-consumption-tax-status-2026-09-03.json"
CHECKOUT_EVIDENCE = REPO_ROOT / "ops/readiness/ruby-checkout-legal-payment-shipping-sync-2026-09-04.json"
EXPECTED_TAX_REF = "ops/readiness/ruby-japan-consumption-tax-status-2026-09-03.json"
EXPECTED_SCOPE_TYPE = "initial_launch_subset"
OWNER_CATALOG_OBJECT_FIELDS = {
    "categories": ("name", "slug"),
    "media": ("alt",),
    "products": ("name", "description", "slug", "fulfillment"),
}


def _validate_owner_catalog_object_shapes(payload: dict[str, Any]) -> None:
    """Reject malformed JSON object shapes before model parsing can raise AttributeError."""

    for collection, nested_fields in OWNER_CATALOG_OBJECT_FIELDS.items():
        values = payload.get(collection, [])
        if not isinstance(values, list):
            continue
        for index, item in enumerate(values):
            if not isinstance(item, Mapping):
                raise ContractValidationError(f"{collection}[{index}] must be an object")
            for field in nested_fields:
                if not isinstance(item.get(field), Mapping):
                    raise ContractValidationError(
                        f"{collection}[{index}].{field} must be an object"
                    )


def _localized_slug_blockers(
    values: Any,
    *,
    entity_label: str,
) -> list[str]:
    blockers: list[str] = []
    if not isinstance(values, list):
        return blockers

    for locale, locale_label in (("en", "English"), ("ja", "Japanese")):
        seen: set[str] = set()
        for item in values:
            if not isinstance(item, Mapping):
                continue
            slug = item.get("slug")
            if not isinstance(slug, Mapping):
                continue
            value = slug.get(locale)
            if not isinstance(value, str) or not value.strip():
                continue
            normalized = value.strip()
            if normalized in seen:
                blockers.append(
                    f"duplicate WooCommerce {entity_label} {locale_label} slug: {normalized}"
                )
            seen.add(normalized)
    return blockers


def _owner_catalog_identity_blockers(payload: dict[str, Any]) -> list[str]:
    """Reject identities that would make either locale dry-run plan ambiguous."""

    blockers: list[str] = []
    categories = payload.get("categories", [])
    products = payload.get("products", [])

    blockers.extend(_localized_slug_blockers(categories, entity_label="category"))
    blockers.extend(_localized_slug_blockers(products, entity_label="product"))

    if isinstance(products, list):
        for index, product in enumerate(products, start=1):
            if not isinstance(product, Mapping):
                continue
            sku_value = product.get("sku")
            sku = sku_value.strip() if isinstance(sku_value, str) and sku_value.strip() else f"product[{index}]"
            for field, label in (
                ("category_keys", "category key"),
                ("media_keys", "media key"),
            ):
                values = product.get(field, [])
                if not isinstance(values, list):
                    continue
                seen: set[str] = set()
                for value in values:
                    if not isinstance(value, str):
                        continue
                    normalized = value.strip()
                    if normalized in seen:
                        blockers.append(f"{sku} contains duplicate {label}: {normalized}")
                    seen.add(normalized)

    return blockers


def _catalog_scope_blockers(payload: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    scope = payload.get("catalog_scope")
    if not isinstance(scope, dict):
        return ["catalog_scope must be an object"]
    if scope.get("scope_type") != EXPECTED_SCOPE_TYPE:
        blockers.append("catalog scope must be initial_launch_subset")
    if scope.get("full_product_range_required_for_sprint3_closure") is not False:
        blockers.append("Sprint 3 catalog scope must not require Ruby's full product range")
    if scope.get("additional_products_may_be_added_after_sprint3") is not True:
        blockers.append("catalog scope must allow additional products after Sprint 3")
    if scope.get("scope_complete_for_intended_initial_launch") is not True:
        blockers.append("owner must confirm the submitted subset is complete for the intended initial launch")
    return blockers


def _current_state_blockers(payload: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    tax_evidence = json.loads(TAX_EVIDENCE.read_text(encoding="utf-8"))
    checkout = json.loads(CHECKOUT_EVIDENCE.read_text(encoding="utf-8"))
    tax = payload.get("tax_decision") if isinstance(payload.get("tax_decision"), dict) else {}

    current_tax = tax_evidence["decision"]
    if current_tax["consumption_tax_status"] != "exempt":
        blockers.append("current tax readiness no longer supports exempt status")
    if current_tax["qualified_invoice_status"] != "not_registered":
        blockers.append("current tax readiness no longer supports not-registered Qualified Invoice status")
    if current_tax["tax_decision_ready"] is not True:
        blockers.append("current tax decision is not GREEN")

    if tax.get("taxable_business_status") != "exempt":
        blockers.append("owner package taxable_business_status must match current exempt posture")
    if tax.get("qualified_invoice_status") != "not_registered":
        blockers.append("owner package qualified_invoice_status must match current not-registered posture")
    if tax.get("qualified_invoice_registration_number") is not None:
        blockers.append("owner package must not contain a Qualified Invoice registration number")
    if tax.get("implementation_route") != "tax_disabled_candidate":
        blockers.append("owner package implementation_route must match current tax-disabled route")
    if tax.get("yamato_shipping_separately_charged") != "yes":
        blockers.append("owner package must preserve verified separately charged Yamato shipping")
    if tax.get("cod_fee_treatment") != "not_offered":
        blockers.append("owner package COD treatment must remain not_offered")
    if tax.get("decision_evidence_ref") != EXPECTED_TAX_REF:
        blockers.append("owner package tax decision evidence reference is stale or missing")

    prerequisites = checkout["verified_prerequisites"]
    checkout_verification = checkout["woocommerce_checkout_verification"]
    if prerequisites["production_shipping_configuration_verified"] is not True:
        blockers.append("current production shipping configuration is not verified")
    if prerequisites["production_shipping_rates_verified"] is not True:
        blockers.append("current production shipping rates are not verified")
    if "cod" not in checkout_verification["disabled_gateway_ids"]:
        blockers.append("current verified checkout no longer shows COD disabled")

    return blockers


def validate_package(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        _validate_owner_catalog_object_shapes(payload)
        readiness = evaluate_catalog_tax_readiness(payload)
        current_state_blockers = _current_state_blockers(payload)
        scope_blockers = _catalog_scope_blockers(payload)
        identity_blockers = _owner_catalog_identity_blockers(payload)
        blockers = list(readiness.blockers)
        blockers.extend(current_state_blockers)
        blockers.extend(scope_blockers)
        blockers.extend(identity_blockers)
        blockers = sorted(set(blockers))
        ready = readiness.catalog_ready and readiness.tax_decision_ready and not blockers
        scope = payload.get("catalog_scope") if isinstance(payload.get("catalog_scope"), dict) else {}
        return {
            "version": "ruby-owner-catalog-package-validation-v2",
            "valid_contract": True,
            "catalog_scope_type": scope.get("scope_type"),
            "full_product_range_required_for_sprint3_closure": scope.get("full_product_range_required_for_sprint3_closure"),
            "catalog_ready": readiness.catalog_ready and not identity_blockers,
            "tax_decision_ready": readiness.tax_decision_ready,
            "current_state_reconciled": not current_state_blockers,
            "scope_ready": not scope_blockers,
            "ready_for_preproduction_configuration": ready,
            "blockers": blockers,
            "mutation_authorized": False,
            "production_publish_authorized": False,
        }
    except (ContractValidationError, OSError, KeyError, TypeError, ValueError) as exc:
        return {
            "version": "ruby-owner-catalog-package-validation-v2",
            "valid_contract": False,
            "catalog_scope_type": None,
            "full_product_range_required_for_sprint3_closure": None,
            "catalog_ready": False,
            "tax_decision_ready": False,
            "current_state_reconciled": False,
            "scope_ready": False,
            "ready_for_preproduction_configuration": False,
            "blockers": [f"contract validation failed: {exc}"],
            "mutation_authorized": False,
            "production_publish_authorized": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Ruby Initial Launch Catalog V1 owner package without granting WooCommerce write authority."
    )
    parser.add_argument("input_json", type=Path)
    parser.add_argument(
        "--expect-pending",
        action="store_true",
        help="Treat a valid fail-closed pending package as the expected result (for templates/CI).",
    )
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result = {
            "version": "ruby-owner-catalog-package-validation-v2",
            "valid_contract": False,
            "catalog_scope_type": None,
            "full_product_range_required_for_sprint3_closure": None,
            "catalog_ready": False,
            "tax_decision_ready": False,
            "current_state_reconciled": False,
            "scope_ready": False,
            "ready_for_preproduction_configuration": False,
            "blockers": [f"input load failed: {exc}"],
            "mutation_authorized": False,
            "production_publish_authorized": False,
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2

    if not isinstance(payload, dict):
        result = {
            "version": "ruby-owner-catalog-package-validation-v2",
            "valid_contract": False,
            "catalog_scope_type": None,
            "full_product_range_required_for_sprint3_closure": None,
            "catalog_ready": False,
            "tax_decision_ready": False,
            "current_state_reconciled": False,
            "scope_ready": False,
            "ready_for_preproduction_configuration": False,
            "blockers": ["catalog package root must be a JSON object"],
            "mutation_authorized": False,
            "production_publish_authorized": False,
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2

    result = validate_package(payload)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))

    if result["ready_for_preproduction_configuration"]:
        print(
            "PHIL_AI_OS_OWNER_CATALOG_PACKAGE_GREEN "
            "scope=initial_launch_subset full_catalog_required=false "
            "preproduction_configuration_ready=true mutation_authorized=false production_publish_authorized=false"
        )
        return 0

    if args.expect_pending and result["valid_contract"] and not result["ready_for_preproduction_configuration"]:
        print(
            "PHIL_AI_OS_OWNER_CATALOG_PACKAGE_PENDING_FAIL_CLOSED "
            f"blockers={len(result['blockers'])} scope=initial_launch_subset full_catalog_required=false "
            "mutation_authorized=false production_publish_authorized=false"
        )
        return 0

    print(
        "PHIL_AI_OS_OWNER_CATALOG_PACKAGE_BLOCKED "
        f"blockers={len(result['blockers'])} mutation_authorized=false production_publish_authorized=false",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
