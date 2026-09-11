from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .catalog_readiness import evaluate_catalog_tax_readiness
from .models import ContractValidationError, ProductRecord
from .reconciliation import comparable_remote_product, fingerprint, idempotency_key


@dataclass(frozen=True)
class ProductDryRunPlan:
    action: str
    sku: str
    remote_id: int | None
    before_fingerprint: str | None
    after_fingerprint: str
    idempotency_key: str
    network_call: bool = False
    mutation_authorized: bool = False
    production_publish_authorized: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "sku": self.sku,
            "remote_id": self.remote_id,
            "before_fingerprint": self.before_fingerprint,
            "after_fingerprint": self.after_fingerprint,
            "idempotency_key": self.idempotency_key,
            "network_call": self.network_call,
            "mutation_authorized": self.mutation_authorized,
            "production_publish_authorized": self.production_publish_authorized,
        }


@dataclass(frozen=True)
class VariationDryRunPlan:
    action: str
    parent_sku: str
    sku: str
    remote_id: int | None
    before_fingerprint: str | None
    after_fingerprint: str
    idempotency_key: str
    network_call: bool = False
    mutation_authorized: bool = False
    production_publish_authorized: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "parent_sku": self.parent_sku,
            "sku": self.sku,
            "remote_id": self.remote_id,
            "before_fingerprint": self.before_fingerprint,
            "after_fingerprint": self.after_fingerprint,
            "idempotency_key": self.idempotency_key,
            "network_call": self.network_call,
            "mutation_authorized": self.mutation_authorized,
            "production_publish_authorized": self.production_publish_authorized,
        }


@dataclass(frozen=True)
class CatalogDryRunPlan:
    catalog_ready: bool
    tax_decision_ready: bool
    products: tuple[ProductDryRunPlan, ...]
    variations: tuple[VariationDryRunPlan, ...] = ()
    network_call: bool = False
    mutation_authorized: bool = False
    production_publish_authorized: bool = False

    def as_dict(self) -> dict[str, Any]:
        counts = {"create": 0, "update": 0, "noop": 0}
        for item in self.products:
            counts[item.action] += 1
        variation_counts = {"create": 0, "update": 0, "noop": 0}
        for item in self.variations:
            variation_counts[item.action] += 1
        return {
            "catalog_ready": self.catalog_ready,
            "tax_decision_ready": self.tax_decision_ready,
            "counts": counts,
            "variation_counts": variation_counts,
            "products": [item.as_dict() for item in self.products],
            "variations": [item.as_dict() for item in self.variations],
            "network_call": self.network_call,
            "mutation_authorized": self.mutation_authorized,
            "production_publish_authorized": self.production_publish_authorized,
        }


def _remote_products_by_sku(remote_products: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    if isinstance(remote_products, (str, bytes, bytearray)):
        raise ContractValidationError("remote product snapshot must be a sequence of objects")

    by_sku: dict[str, Mapping[str, Any]] = {}
    for index, remote in enumerate(remote_products, start=1):
        if not isinstance(remote, Mapping):
            raise ContractValidationError(
                f"remote product snapshot entry {index} must be an object"
            )
        sku = str(remote.get("sku") or "").strip()
        if not sku:
            raise ContractValidationError("remote product snapshot requires explicit SKU")
        if sku in by_sku:
            raise ContractValidationError(f"remote product snapshot contains duplicate SKU: {sku}")
        remote_id = remote.get("id")
        if not isinstance(remote_id, int) or isinstance(remote_id, bool) or remote_id < 1:
            raise ContractValidationError(f"remote product {sku} requires positive integer id")
        by_sku[sku] = remote
    return by_sku


def _remote_variations_by_sku(
    remote_parent: Mapping[str, Any] | None,
    parent_sku: str,
) -> dict[str, Mapping[str, Any]]:
    if remote_parent is None:
        return {}
    raw_variations = remote_parent.get("variations", [])
    if not isinstance(raw_variations, list):
        raise ContractValidationError(
            f"remote variable product {parent_sku} variations must be an expanded array"
        )
    by_sku: dict[str, Mapping[str, Any]] = {}
    for index, remote in enumerate(raw_variations, start=1):
        if not isinstance(remote, Mapping):
            raise ContractValidationError(
                f"remote variable product {parent_sku} variation {index} must be an expanded object"
            )
        sku = str(remote.get("sku") or "").strip()
        if not sku:
            raise ContractValidationError(
                f"remote variable product {parent_sku} variation {index} requires explicit SKU"
            )
        if sku in by_sku:
            raise ContractValidationError(
                f"remote variable product {parent_sku} contains duplicate variation SKU: {sku}"
            )
        remote_id = remote.get("id")
        if not isinstance(remote_id, int) or isinstance(remote_id, bool) or remote_id < 1:
            raise ContractValidationError(
                f"remote variation {sku} under {parent_sku} requires positive integer id"
            )
        by_sku[sku] = remote
    return by_sku


def _comparable_remote_variation(remote: Mapping[str, Any]) -> dict[str, Any]:
    attributes: list[dict[str, str]] = []
    for item in remote.get("attributes", []):
        if not isinstance(item, Mapping):
            continue
        attributes.append(
            {
                "name": str(item.get("name") or ""),
                "option": str(item.get("option") or ""),
            }
        )
    return {
        "sku": remote.get("sku"),
        "regular_price": remote.get("regular_price"),
        "attributes": sorted(attributes, key=lambda item: (item["name"], item["option"])),
    }


def plan_catalog_product_reconciliation(
    intake_payload: Mapping[str, Any],
    remote_products: Sequence[Mapping[str, Any]],
    *,
    locale: str = "en",
) -> CatalogDryRunPlan:
    """Build a deterministic product/variation reconciliation plan without side effects.

    The intake must be catalog-ready. Tax readiness is reported but deliberately
    does not authorize or execute tax/product changes. ``remote_products`` must be
    a caller-supplied read-only snapshot; variable parents may include an expanded
    ``variations`` array. This function performs no network calls or mutations.
    """

    readiness = evaluate_catalog_tax_readiness(intake_payload)
    if not readiness.catalog_ready:
        raise ContractValidationError(
            "catalog dry-run requires catalog_ready=true; resolve catalog blockers first"
        )

    products_raw = intake_payload.get("products", [])
    products = [ProductRecord.from_mapping(value) for value in products_raw]
    remote_by_sku = _remote_products_by_sku(remote_products)

    plans: list[ProductDryRunPlan] = []
    variation_plans: list[VariationDryRunPlan] = []
    for product in sorted(products, key=lambda value: value.sku):
        desired = product.to_wc_payload(locale)
        current = remote_by_sku.get(product.sku)
        key = idempotency_key("plan", "product", product.sku, desired)
        after_fp = fingerprint(desired)

        if current is None:
            plans.append(
                ProductDryRunPlan(
                    action="create",
                    sku=product.sku,
                    remote_id=None,
                    before_fingerprint=None,
                    after_fingerprint=after_fp,
                    idempotency_key=key,
                )
            )
        else:
            before = comparable_remote_product(
                current,
                variable=product.product_type == "variable",
            )
            before_fp = fingerprint(before)
            plans.append(
                ProductDryRunPlan(
                    action="noop" if before == desired else "update",
                    sku=product.sku,
                    remote_id=int(current["id"]),
                    before_fingerprint=before_fp,
                    after_fingerprint=after_fp,
                    idempotency_key=key,
                )
            )

        if product.product_type != "variable":
            continue

        remote_variations = _remote_variations_by_sku(current, product.sku)
        for variation, desired_variation in zip(product.variations, product.variation_payloads()):
            remote_variation = remote_variations.get(variation.sku)
            variation_key = idempotency_key(
                "plan",
                "variation",
                f"{product.sku}/{variation.sku}",
                desired_variation,
            )
            variation_after_fp = fingerprint(desired_variation)
            if remote_variation is None:
                variation_plans.append(
                    VariationDryRunPlan(
                        action="create",
                        parent_sku=product.sku,
                        sku=variation.sku,
                        remote_id=None,
                        before_fingerprint=None,
                        after_fingerprint=variation_after_fp,
                        idempotency_key=variation_key,
                    )
                )
                continue

            variation_before = _comparable_remote_variation(remote_variation)
            variation_before_fp = fingerprint(variation_before)
            variation_plans.append(
                VariationDryRunPlan(
                    action="noop" if variation_before == desired_variation else "update",
                    parent_sku=product.sku,
                    sku=variation.sku,
                    remote_id=int(remote_variation["id"]),
                    before_fingerprint=variation_before_fp,
                    after_fingerprint=variation_after_fp,
                    idempotency_key=variation_key,
                )
            )

    return CatalogDryRunPlan(
        catalog_ready=readiness.catalog_ready,
        tax_decision_ready=readiness.tax_decision_ready,
        products=tuple(plans),
        variations=tuple(variation_plans),
    )
