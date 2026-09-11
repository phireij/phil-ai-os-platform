from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SUPPORTED_TEMPERATURES = frozenset({"ambient", "chilled", "frozen"})
DEPENDENT_PACKAGE_RULES = frozenset({"depends_on_total_pieces", "depends_on_total_items"})


@dataclass(frozen=True)
class ProductFulfillmentGap:
    key: str
    temperature_status: str
    package_status: str
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class WorkingCatalogFulfillmentReadiness:
    ready_for_final_classification: bool
    product_results: tuple[ProductFulfillmentGap, ...]
    production_mutation_authorized: bool = False


def _product_key(product: dict[str, Any]) -> str:
    return str(product.get("sku") or product.get("parent_reference") or product.get("english_name") or "unknown")


def evaluate_working_catalog_fulfillment_readiness(
    payload: dict[str, Any],
) -> WorkingCatalogFulfillmentReadiness:
    """Assess whether working-catalog fulfillment facts are ready for final SKU classification.

    This evaluator is intentionally pre-production only. It does not infer a final
    temperature mode or package class when the owner source is ambiguous or explicitly
    quantity-dependent, and it never grants WooCommerce mutation authority.
    """

    results: list[ProductFulfillmentGap] = []

    for product in payload.get("working_products") or []:
        blockers: list[str] = []
        key = _product_key(product)

        marks = tuple(dict.fromkeys(str(value) for value in (product.get("source_temperature_marks") or ())))
        unsupported = tuple(value for value in marks if value not in SUPPORTED_TEMPERATURES)
        if unsupported:
            blockers.append("unsupported temperature mark(s): " + ", ".join(unsupported))
            temperature_status = "invalid"
        elif not marks:
            blockers.append("temperature mode is missing")
            temperature_status = "missing"
        elif len(marks) > 1:
            blockers.append("multiple temperature modes require owner classification")
            temperature_status = "ambiguous"
        else:
            temperature_status = f"resolved:{marks[0]}"

        package_rule = product.get("source_package_rule")
        if product.get("delivery_allowed") is not True:
            package_status = "not_required"
        elif package_rule in DEPENDENT_PACKAGE_RULES:
            blockers.append("quantity-dependent package rule requires final package policy")
            package_status = "quantity_dependent"
        elif package_rule is None:
            blockers.append("final shipping/package class is missing")
            package_status = "missing"
        else:
            package_status = f"resolved:{package_rule}"

        # A candidate is planning evidence only. It cannot resolve the package gate
        # until physical fit/cushioning evidence is explicitly confirmed.
        if product.get("ambient_package_candidate") and product.get("ambient_package_candidate_confirmed") is not True:
            blockers.append("ambient package candidate lacks physical-fit confirmation")
            if package_status.startswith("resolved:"):
                package_status = "candidate_unconfirmed"

        results.append(
            ProductFulfillmentGap(
                key=key,
                temperature_status=temperature_status,
                package_status=package_status,
                blockers=tuple(blockers),
            )
        )

    return WorkingCatalogFulfillmentReadiness(
        ready_for_final_classification=bool(results) and all(not item.blockers for item in results),
        product_results=tuple(results),
    )
