from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .catalog_field_evidence import evaluate_field_evidence
from .sku_policy import SkuPolicyError, parse_ruby_sku
from .working_catalog_category_candidates import (
    build_working_catalog_category_candidate_packet,
)
from .working_catalog_fulfillment_readiness import (
    evaluate_working_catalog_fulfillment_readiness,
)
from .working_catalog_media_evidence import build_working_catalog_media_evidence_packet


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


def _iter_skus(products: Iterable[dict[str, Any]]) -> Iterable[str]:
    for product in products:
        sku = product.get("sku")
        if sku:
            yield str(sku)
        for variant in product.get("variants") or ():
            variant_sku = variant.get("sku")
            if variant_sku:
                yield str(variant_sku)


def _partition_supplemental_blockers(
    blockers: Iterable[str],
    product_keys: Iterable[str],
    prefix: str,
) -> tuple[list[str], dict[str, list[str]]]:
    keys = tuple(product_keys)
    global_blockers: list[str] = []
    product_blockers: dict[str, list[str]] = {key: [] for key in keys}
    for blocker in blockers:
        matched = False
        for key in keys:
            marker = f"{key}: "
            if blocker.startswith(marker):
                product_blockers[key].append(f"{prefix}: {blocker[len(marker):]}")
                matched = True
                break
        if not matched:
            global_blockers.append(f"{prefix}: {blocker}")
    return global_blockers, product_blockers


def build_working_catalog_gap_report(payload: dict[str, Any]) -> WorkingCatalogGapReport:
    """Report catalog-completeness gaps without conflating live execution authority.

    Mutation/publication authority is intentionally enforced by the production execution
    preflights, not by this owner-facing catalog completeness report. This keeps catalog
    decisions independently closable while preserving fail-closed live side-effect controls.
    """

    global_gaps: list[str] = []

    if payload.get("catalog_approved") is not True:
        global_gaps.append("catalog approval is missing")
    scope = payload.get("catalog_scope") or {}
    if scope.get("scope_complete_for_intended_initial_launch") is not True:
        global_gaps.append("initial launch subset is not owner-confirmed complete")
    if not payload.get("catalog_approval_ref"):
        global_gaps.append("catalog approval reference is missing")

    source_snapshot = payload.get("source_snapshot") or {}
    if not source_snapshot.get("drive_file_id"):
        global_gaps.append("catalog source provenance is missing Drive file id")
    if not source_snapshot.get("observed_modified_at"):
        global_gaps.append("catalog source provenance is missing observed modified timestamp")

    products = payload.get("working_products") or []
    if not products:
        global_gaps.append("catalog contains no products")

    evidence = evaluate_field_evidence(payload)
    global_gaps.extend(f"owner evidence: {blocker}" for blocker in evidence.blockers)

    seen_skus: set[str] = set()
    for sku in _iter_skus(products):
        try:
            parse_ruby_sku(sku)
        except SkuPolicyError:
            global_gaps.append(f"invalid Ruby SKU: {sku}")
            continue
        if sku in seen_skus:
            global_gaps.append(f"duplicate Ruby SKU: {sku}")
        seen_skus.add(sku)

    fulfillment = evaluate_working_catalog_fulfillment_readiness(payload)
    fulfillment_by_position = tuple(fulfillment.product_results)

    product_keys = tuple(_product_key(product) for product in products)
    category_packet = build_working_catalog_category_candidate_packet(payload)
    category_global, category_by_product = _partition_supplemental_blockers(
        category_packet.blockers,
        product_keys,
        "Category",
    )
    media_packet = build_working_catalog_media_evidence_packet(payload)
    media_global, media_by_product = _partition_supplemental_blockers(
        media_packet.blockers,
        product_keys,
        "Media",
    )
    global_gaps.extend(category_global)
    global_gaps.extend(media_global)

    product_gaps: list[ProductGap] = []
    for index, product in enumerate(products):
        key = product_keys[index]
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

        if index < len(fulfillment_by_position):
            missing.extend(
                f"Fulfillment: {blocker}"
                for blocker in fulfillment_by_position[index].blockers
            )
        else:
            missing.append("Fulfillment: readiness result is missing")

        missing.extend(category_by_product.get(key, ()))
        missing.extend(media_by_product.get(key, ()))

        product_gaps.append(ProductGap(key, tuple(dict.fromkeys(missing))))

    return WorkingCatalogGapReport(tuple(dict.fromkeys(global_gaps)), tuple(product_gaps))
