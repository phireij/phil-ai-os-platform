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
class CatalogDryRunPlan:
    catalog_ready: bool
    tax_decision_ready: bool
    products: tuple[ProductDryRunPlan, ...]
    network_call: bool = False
    mutation_authorized: bool = False
    production_publish_authorized: bool = False

    def as_dict(self) -> dict[str, Any]:
        counts = {"create": 0, "update": 0, "noop": 0}
        for item in self.products:
            counts[item.action] += 1
        return {
            "catalog_ready": self.catalog_ready,
            "tax_decision_ready": self.tax_decision_ready,
            "counts": counts,
            "products": [item.as_dict() for item in self.products],
            "network_call": self.network_call,
            "mutation_authorized": self.mutation_authorized,
            "production_publish_authorized": self.production_publish_authorized,
        }


def _remote_products_by_sku(remote_products: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    by_sku: dict[str, Mapping[str, Any]] = {}
    for remote in remote_products:
        sku = str(remote.get("sku") or "").strip()
        if not sku:
            raise ContractValidationError("remote product snapshot requires explicit SKU")
        if sku in by_sku:
            raise ContractValidationError(f"remote product snapshot contains duplicate SKU: {sku}")
        remote_id = remote.get("id")
        if not isinstance(remote_id, int) or remote_id < 1:
            raise ContractValidationError(f"remote product {sku} requires positive integer id")
        by_sku[sku] = remote
    return by_sku


def plan_catalog_product_reconciliation(
    intake_payload: Mapping[str, Any],
    remote_products: Sequence[Mapping[str, Any]],
    *,
    locale: str = "en",
) -> CatalogDryRunPlan:
    """Build a deterministic product reconciliation plan without any side effect.

    The intake must be catalog-ready. Tax readiness is reported but deliberately
    does not authorize or execute tax/product changes. `remote_products` must be a
    caller-supplied read-only snapshot; this function performs no network calls.
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
            continue

        before = comparable_remote_product(current)
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

    return CatalogDryRunPlan(
        catalog_ready=readiness.catalog_ready,
        tax_decision_ready=readiness.tax_decision_ready,
        products=tuple(plans),
    )
