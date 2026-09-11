from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .working_catalog_gap_report import build_working_catalog_gap_report


@dataclass(frozen=True)
class CatalogOwnerAction:
    action_key: str
    scope: str
    product_key: str | None
    category: str
    requirement: str
    source_blocker: str
    decision_value: None = None


@dataclass(frozen=True)
class WorkingCatalogOwnerActionPacket:
    actions: tuple[CatalogOwnerAction, ...]
    production_ready: bool
    network_call_performed: bool = False
    mutation_authorized: bool = False
    production_publish_authorized: bool = False


_GLOBAL_CATEGORY = {
    "catalog approval is missing": "owner_approval",
    "initial launch subset is not owner-confirmed complete": "owner_scope_confirmation",
    "catalog approval reference is missing": "owner_approval",
    "production mutation authority is not granted": "authority_gate",
    "production publication authority is not granted": "authority_gate",
    "catalog contains no products": "owner_catalog_input",
}

_PRODUCT_CATEGORY = {
    "English product name": "owner_catalog_input",
    "Japanese product name": "owner_catalog_input",
    "English description": "owner_catalog_input",
    "Japanese description": "owner_catalog_input",
    "JPY price": "owner_catalog_input",
    "product variations": "owner_catalog_input",
    "variation JPY price": "owner_catalog_input",
    "verified media source": "operational_evidence",
}


def _slug(value: str) -> str:
    return "-".join(
        token for token in "".join(ch.lower() if ch.isalnum() else " " for ch in value).split() if token
    )[:80] or "unknown"


def _category_for_global(blocker: str) -> str:
    if blocker in _GLOBAL_CATEGORY:
        return _GLOBAL_CATEGORY[blocker]
    if blocker.startswith("owner evidence:"):
        return "owner_evidence"
    if blocker.startswith("invalid Ruby SKU:") or blocker.startswith("duplicate Ruby SKU:"):
        return "catalog_identity_integrity"
    return "owner_or_operational_review"


def _category_for_product(blocker: str) -> str:
    if blocker in _PRODUCT_CATEGORY:
        return _PRODUCT_CATEGORY[blocker]
    if blocker.startswith("fulfillment:"):
        return "fulfillment_decision_or_evidence"
    return "owner_or_operational_review"


def build_working_catalog_owner_action_packet(payload: dict[str, Any]) -> WorkingCatalogOwnerActionPacket:
    """Translate existing catalog readiness blockers into a deterministic action packet.

    The packet never supplies a decision value, never resolves a blocker, and never grants
    WooCommerce mutation or publication authority. It exists only to make the remaining
    owner/operational inputs explicit without inventing catalog facts.
    """

    report = build_working_catalog_gap_report(payload)
    actions: list[CatalogOwnerAction] = []

    for blocker in report.global_gaps:
        actions.append(
            CatalogOwnerAction(
                action_key=f"global:{_slug(blocker)}",
                scope="global",
                product_key=None,
                category=_category_for_global(blocker),
                requirement=blocker,
                source_blocker=blocker,
            )
        )

    for product in report.product_gaps:
        for blocker in product.missing:
            actions.append(
                CatalogOwnerAction(
                    action_key=f"product:{product.key}:{_slug(blocker)}",
                    scope="product",
                    product_key=product.key,
                    category=_category_for_product(blocker),
                    requirement=blocker,
                    source_blocker=blocker,
                )
            )

    actions.sort(key=lambda item: (item.scope, item.product_key or "", item.category, item.action_key))
    return WorkingCatalogOwnerActionPacket(
        actions=tuple(actions),
        production_ready=report.production_ready,
    )
