from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CatalogMediaEvidenceItem:
    product_key: str
    source_state: str | None
    verified_media_reference: None = None
    primary_media_confirmed: bool = False


@dataclass(frozen=True)
class WorkingCatalogMediaEvidencePacket:
    items: tuple[CatalogMediaEvidenceItem, ...]
    blockers: tuple[str, ...]
    ready_for_media_ingestion_review: bool
    network_call_performed: bool = False
    mutation_authorized: bool = False
    production_publish_authorized: bool = False


def _product_key(product: dict[str, Any]) -> str:
    return str(product.get("sku") or product.get("parent_reference") or product.get("english_name") or "unknown")


def build_working_catalog_media_evidence_packet(
    payload: dict[str, Any],
) -> WorkingCatalogMediaEvidencePacket:
    """Expose media-source evidence without inventing attachment identities or media mappings.

    The working catalog may record that a photo exists in the owner source, but that state is
    not a verified ingestion reference. This packet keeps that distinction explicit and never
    grants network, WooCommerce mutation, or publication authority.
    """

    items: list[CatalogMediaEvidenceItem] = []
    blockers: list[str] = []
    products = payload.get("working_products") or []

    if not products:
        blockers.append("catalog contains no products")

    for product in products:
        key = _product_key(product)
        raw_state = product.get("photo_source_state")
        source_state = raw_state.strip() if isinstance(raw_state, str) and raw_state.strip() else None
        items.append(
            CatalogMediaEvidenceItem(
                product_key=key,
                source_state=source_state,
            )
        )
        if source_state is None:
            blockers.append(f"{key}: media source state is missing")
        else:
            blockers.append(f"{key}: verified media ingestion reference is unresolved")

    if items:
        blockers.append("primary media selection and verified ingestion references require review")

    return WorkingCatalogMediaEvidencePacket(
        items=tuple(sorted(items, key=lambda item: item.product_key)),
        blockers=tuple(dict.fromkeys(blockers)),
        ready_for_media_ingestion_review=False,
    )
