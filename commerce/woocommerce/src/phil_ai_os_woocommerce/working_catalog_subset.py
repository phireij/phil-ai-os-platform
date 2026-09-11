from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .catalog_field_evidence import evaluate_field_evidence
from .sku_policy import parse_ruby_sku, SkuPolicyError


@dataclass(frozen=True)
class WorkingCatalogSubsetResult:
    valid_for_preparation: bool
    blockers: tuple[str, ...]


def _iter_skus(products: Iterable[dict[str, Any]]) -> Iterable[str]:
    for product in products:
        sku = product.get("sku")
        if sku:
            yield str(sku)
        for variant in product.get("variants") or ():
            variant_sku = variant.get("sku")
            if variant_sku:
                yield str(variant_sku)


def evaluate_working_catalog_subset(payload: dict[str, Any]) -> WorkingCatalogSubsetResult:
    blockers: list[str] = []

    if payload.get("catalog_approved") is not False:
        blockers.append("working subset must keep catalog_approved=false")
    if payload.get("mutation_authorized") is not False:
        blockers.append("working subset must keep mutation_authorized=false")
    if payload.get("production_publish_authorized") is not False:
        blockers.append("working subset must keep production_publish_authorized=false")

    scope = payload.get("catalog_scope") or {}
    if scope.get("scope_complete_for_intended_initial_launch") is not False:
        blockers.append("working subset must remain incomplete until owner confirmation")

    source_snapshot = payload.get("source_snapshot") or {}
    if not source_snapshot.get("drive_file_id"):
        blockers.append("working subset source snapshot is missing Drive file id")
    if not source_snapshot.get("observed_modified_at"):
        blockers.append("working subset source snapshot is missing modified timestamp")
    if source_snapshot.get("owner_declared_subset_complete") is not False:
        blockers.append("owner_declared_subset_complete must remain false")

    evidence_result = evaluate_field_evidence(payload)
    blockers.extend(f"field evidence: {blocker}" for blocker in evidence_result.blockers)

    products = payload.get("working_products") or []
    if not products:
        blockers.append("working subset contains no products")

    seen: set[str] = set()
    for sku in _iter_skus(products):
        try:
            parse_ruby_sku(sku)
        except SkuPolicyError:
            blockers.append(f"invalid Ruby SKU: {sku}")
            continue
        if sku in seen:
            blockers.append(f"duplicate Ruby SKU: {sku}")
        seen.add(sku)

    moist = next(
        (p for p in products if p.get("parent_reference") == "RCD-MCH-RD"),
        None,
    )
    if moist is None:
        blockers.append("Moist Chocolate Round Cake working product is missing")
    else:
        variants = {v.get("sku"): v for v in moist.get("variants") or []}
        v21 = variants.get("RCD-MCH-RD-21")
        if v21 is None:
            blockers.append("confirmed RCD-MCH-RD-21 variation is missing")
        elif not (
            v21.get("source_typo") == "RCS-MCH-RD-21"
            and v21.get("owner_correction_confirmed") is True
        ):
            blockers.append("21 cm SKU correction lacks explicit owner confirmation evidence")

    known_blockers = set(payload.get("known_blockers") or ())
    required_blockers = {
        "initial launch subset is not owner-confirmed complete",
        "Japanese product names/descriptions are missing",
        "verified media ingestion references are unresolved",
        "explicit Initial Launch Catalog V1 approval reference is missing",
    }
    for missing in sorted(required_blockers - known_blockers):
        blockers.append(f"working subset no longer records blocker: {missing}")

    return WorkingCatalogSubsetResult(
        valid_for_preparation=not blockers,
        blockers=tuple(dict.fromkeys(blockers)),
    )
