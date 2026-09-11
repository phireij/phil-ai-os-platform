from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CatalogCategoryCandidate:
    source_label: str
    product_keys: tuple[str, ...]
    english_name: None = None
    japanese_name: None = None
    english_slug: None = None
    japanese_slug: None = None
    mapping_approved: bool = False


@dataclass(frozen=True)
class WorkingCatalogCategoryCandidatePacket:
    candidates: tuple[CatalogCategoryCandidate, ...]
    blockers: tuple[str, ...]
    ready_for_category_mapping_approval: bool
    network_call_performed: bool = False
    mutation_authorized: bool = False
    production_publish_authorized: bool = False


def _product_key(product: dict[str, Any]) -> str:
    return str(product.get("sku") or product.get("parent_reference") or product.get("english_name") or "unknown")


def build_working_catalog_category_candidate_packet(
    payload: dict[str, Any],
) -> WorkingCatalogCategoryCandidatePacket:
    """Extract only owner-supplied category labels into a non-authorizing mapping packet.

    This function intentionally does not invent hierarchy, localized category names, slugs,
    or WooCommerce mappings. It preserves exact source labels and records missing source
    labels as blockers for owner/operational completion.
    """

    grouped: dict[str, list[str]] = {}
    blockers: list[str] = []

    for product in payload.get("working_products") or []:
        key = _product_key(product)
        label = product.get("category_source_label")
        if not isinstance(label, str) or not label.strip():
            blockers.append(f"{key}: category source label is missing")
            continue
        normalized = label.strip()
        grouped.setdefault(normalized, []).append(key)

    candidates = tuple(
        CatalogCategoryCandidate(
            source_label=label,
            product_keys=tuple(sorted(set(product_keys))),
        )
        for label, product_keys in sorted(grouped.items(), key=lambda item: item[0].casefold())
    )

    if not candidates:
        blockers.append("no category source labels are available")

    if candidates:
        blockers.append("final category hierarchy, bilingual names, slugs, and mappings require approval")

    return WorkingCatalogCategoryCandidatePacket(
        candidates=candidates,
        blockers=tuple(dict.fromkeys(blockers)),
        ready_for_category_mapping_approval=False,
    )
