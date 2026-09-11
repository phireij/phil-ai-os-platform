from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProductGap:
    key: str
    missing: tuple[str, ...]


@dataclass(frozen=True)
class WorkingCatalogGapReport:
    global_gaps: tuple[str, ...]
    product_gaps: tuple[ProductGap, ...]

    @property
    def production_ready(self) -> bool:
        return not self.global_gaps and all(not item.missing for item in self.product_gaps)


def _product_key(product: dict[str, Any]) -> str:
    return str(product.get("sku") or product.get("parent_reference") or product.get("english_name") or "unknown")


def build_working_catalog_gap_report(payload: dict[str, Any]) -> WorkingCatalogGapReport:
    global_gaps: list[str] = []

    if payload.get("catalog_approved") is not True:
        global_gaps.append("catalog approval is missing")
    scope = payload.get("catalog_scope") or {}
    if scope.get("scope_complete_for_intended_initial_launch") is not True:
        global_gaps.append("initial launch subset is not owner-confirmed complete")
    if not payload.get("catalog_approval_ref"):
        global_gaps.append("catalog approval reference is missing")
    if payload.get("mutation_authorized") is not True:
        global_gaps.append("production mutation authority is not granted")
    if payload.get("production_publish_authorized") is not True:
        global_gaps.append("production publication authority is not granted")

    product_gaps: list[ProductGap] = []
    for product in payload.get("working_products") or []:
        missing: list[str] = []
        if not product.get("english_name"):
            missing.append("English product name")
        if not product.get("japanese_name"):
            missing.append("Japanese product name")
        if not product.get("english_description"):
            missing.append("English description")
        if not product.get("japanese_description"):
            missing.append("Japanese description")

        if product.get("product_type") == "simple" and product.get("price_jpy") is None:
            missing.append("JPY price")
        if product.get("product_type") == "variable":
            variants = product.get("variants") or []
            if not variants:
                missing.append("product variations")
            elif any(v.get("price_jpy") is None for v in variants):
                missing.append("variation JPY price")

        if product.get("delivery_allowed") is True:
            if not product.get("source_temperature_marks"):
                missing.append("temperature mode")
            package_rule = product.get("source_package_rule")
            if package_rule in (None, "depends_on_total_pieces", "depends_on_total_items"):
                missing.append("final shipping/package class")

        if not product.get("photo_source_state") and product.get("product_type") != "variable":
            missing.append("verified media source")

        product_gaps.append(ProductGap(_product_key(product), tuple(missing)))

    return WorkingCatalogGapReport(tuple(global_gaps), tuple(product_gaps))
