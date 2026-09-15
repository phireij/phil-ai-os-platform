from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .working_catalog_category_candidates import build_working_catalog_category_candidate_packet
from .working_catalog_gap_report import build_working_catalog_gap_report
from .working_catalog_media_evidence import build_working_catalog_media_evidence_packet


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

_SUPPLEMENTAL_PREFIXES = ("Category: ", "Media: ")


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
    if blocker.lower().startswith("fulfillment:"):
        return "fulfillment_decision_or_evidence"
    return "owner_or_operational_review"


def _semantic_requirement(requirement: str) -> str:
    for prefix in _SUPPLEMENTAL_PREFIXES:
        if requirement.startswith(prefix):
            return requirement[len(prefix) :]
    return requirement


def _product_keys(payload: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for product in payload.get("working_products") or []:
        key = str(
            product.get("sku")
            or product.get("parent_reference")
            or product.get("english_name")
            or "unknown"
        )
        keys.add(key)
    return keys


def _split_product_blocker(blocker: str, product_keys: set[str]) -> tuple[str | None, str]:
    prefix, separator, remainder = blocker.partition(": ")
    if separator and prefix in product_keys:
        return prefix, remainder
    return None, blocker


def _append_action(
    actions: list[CatalogOwnerAction],
    seen: set[tuple[str, str | None, str]],
    *,
    scope: str,
    product_key: str | None,
    category: str,
    requirement: str,
    source_blocker: str,
) -> None:
    identity = (scope, product_key, _semantic_requirement(requirement))
    if identity in seen:
        return
    seen.add(identity)
    prefix = f"product:{product_key}" if product_key else "global"
    actions.append(
        CatalogOwnerAction(
            action_key=f"{prefix}:{_slug(source_blocker)}",
            scope=scope,
            product_key=product_key,
            category=category,
            requirement=requirement,
            source_blocker=source_blocker,
        )
    )


def build_working_catalog_owner_action_packet(payload: dict[str, Any]) -> WorkingCatalogOwnerActionPacket:
    """Translate current catalog readiness evidence into a deterministic owner action packet.

    The packet combines the canonical readiness report with the category-candidate and media-
    evidence packets so material Sprint 3 blockers cannot disappear merely because they live
    outside the core gap report. Specialized category/media blockers are registered before the
    core report so semantically duplicated wrapper blockers collapse to the richer source while
    preserving every distinct requirement. The packet never supplies a decision value, resolves
    a blocker, or grants WooCommerce mutation or publication authority.
    """

    report = build_working_catalog_gap_report(payload)
    category_packet = build_working_catalog_category_candidate_packet(payload)
    media_packet = build_working_catalog_media_evidence_packet(payload)
    product_keys = _product_keys(payload)
    actions: list[CatalogOwnerAction] = []
    seen: set[tuple[str, str | None, str]] = set()

    # Register specialized evidence first so a semantically equivalent core wrapper such as
    # "Category: ..." or "Media: ..." cannot create a second owner-facing action.
    for blocker in category_packet.blockers:
        product_key, requirement = _split_product_blocker(blocker, product_keys)
        _append_action(
            actions,
            seen,
            scope="product" if product_key else "global",
            product_key=product_key,
            category="category_mapping",
            requirement=requirement,
            source_blocker=blocker,
        )

    for blocker in media_packet.blockers:
        product_key, requirement = _split_product_blocker(blocker, product_keys)
        _append_action(
            actions,
            seen,
            scope="product" if product_key else "global",
            product_key=product_key,
            category="media_ingestion_evidence",
            requirement=requirement,
            source_blocker=blocker,
        )

    for blocker in report.global_gaps:
        _append_action(
            actions,
            seen,
            scope="global",
            product_key=None,
            category=_category_for_global(blocker),
            requirement=blocker,
            source_blocker=blocker,
        )

    for product in report.product_gaps:
        for blocker in product.missing:
            _append_action(
                actions,
                seen,
                scope="product",
                product_key=product.key,
                category=_category_for_product(blocker),
                requirement=blocker,
                source_blocker=blocker,
            )

    actions.sort(key=lambda item: (item.scope, item.product_key or "", item.category, item.action_key))
    supplemental_blockers_present = bool(category_packet.blockers or media_packet.blockers)
    return WorkingCatalogOwnerActionPacket(
        actions=tuple(actions),
        production_ready=report.production_ready and not supplemental_blockers_present,
    )
