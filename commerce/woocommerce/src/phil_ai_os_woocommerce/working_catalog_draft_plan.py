from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .working_catalog_fulfillment_readiness import (
    evaluate_working_catalog_fulfillment_readiness,
)
from .working_catalog_subset import evaluate_working_catalog_subset


@dataclass(frozen=True)
class DraftVariation:
    sku: str
    price_jpy: int | None
    size_cm: int | None


@dataclass(frozen=True)
class DraftProductPlan:
    key: str
    product_type: str
    status: str
    catalog_visibility: str
    english_name: str | None
    japanese_name: str | None
    price_jpy: int | None
    variations: tuple[DraftVariation, ...]
    unresolved_fields: tuple[str, ...]


@dataclass(frozen=True)
class WorkingCatalogDraftPlan:
    products: tuple[DraftProductPlan, ...]
    network_call_performed: bool = False
    mutation_authorized: bool = False
    production_publish_authorized: bool = False


def _key(product: dict[str, Any]) -> str:
    return str(
        product.get("sku")
        or product.get("parent_reference")
        or product.get("english_name")
        or "unknown"
    )


def build_working_catalog_draft_plan(payload: dict[str, Any]) -> WorkingCatalogDraftPlan:
    """Build a non-authorizing WooCommerce draft skeleton from confirmed working facts.

    The plan intentionally preserves only confirmed fields. Missing bilingual copy,
    media, category, fulfillment, or package facts remain explicit unresolved fields.
    It never creates a schema-complete production payload and performs no network call.
    Structured owner evidence and the working-subset guard must remain valid before any
    owner-confirmed field is carried into the draft plan.
    """

    subset = evaluate_working_catalog_subset(payload)
    if not subset.valid_for_preparation:
        joined = "; ".join(subset.blockers)
        raise ValueError(f"working catalog subset is not valid for preparation: {joined}")

    fulfillment = evaluate_working_catalog_fulfillment_readiness(payload)
    fulfillment_by_key = {item.key: item for item in fulfillment.product_results}
    planned: list[DraftProductPlan] = []

    for product in payload.get("working_products") or []:
        key = _key(product)
        product_type = str(product.get("product_type") or "unknown")
        unresolved: list[str] = []

        english_name = product.get("english_name")
        japanese_name = product.get("japanese_name")
        if not english_name:
            unresolved.append("english_name")
        if not japanese_name:
            unresolved.append("japanese_name")
        if not product.get("japanese_description"):
            unresolved.append("japanese_description")
        if not product.get("category_source_label") and not product.get("family"):
            unresolved.append("category_mapping")

        fulfillment_result = fulfillment_by_key.get(key)
        if fulfillment_result is not None:
            unresolved.extend(f"fulfillment:{value}" for value in fulfillment_result.blockers)

        if product.get("photo_source_state") in {None, "attached_in_owner_source"}:
            unresolved.append("verified_media_ingestion_reference")

        variations: tuple[DraftVariation, ...] = ()
        price_jpy: int | None = None
        if product_type == "variable":
            raw_variations = product.get("variants") or []
            variations = tuple(
                DraftVariation(
                    sku=str(item.get("sku") or ""),
                    price_jpy=item.get("price_jpy"),
                    size_cm=item.get("size_cm"),
                )
                for item in raw_variations
            )
            if not variations:
                unresolved.append("variations")
            for item in variations:
                if not item.sku:
                    unresolved.append("variation_sku")
                if item.price_jpy is None:
                    unresolved.append(f"variation_price:{item.sku or 'unknown'}")
        else:
            price_jpy = product.get("price_jpy")
            if price_jpy is None:
                unresolved.append("price_jpy")

        planned.append(
            DraftProductPlan(
                key=key,
                product_type=product_type,
                status="draft",
                catalog_visibility="hidden",
                english_name=english_name,
                japanese_name=japanese_name,
                price_jpy=price_jpy,
                variations=variations,
                unresolved_fields=tuple(dict.fromkeys(unresolved)),
            )
        )

    return WorkingCatalogDraftPlan(products=tuple(planned))
