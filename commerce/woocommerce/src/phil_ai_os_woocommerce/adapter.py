from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Protocol

from .inventory_guard import MemoryInventoryRevisionStore
from .models import CategoryRecord, InventoryRecord, MediaRecord, ProductRecord
from .reconciliation import (
    MemoryIdempotencyStore,
    ReconciliationResult,
    comparable_remote_product,
    fingerprint,
    idempotency_key,
)


class ProductionConnectivityBlocked(RuntimeError):
    pass


class WooCommerceTransport(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> Any: ...


class BlockedNetworkTransport:
    """Fail-closed placeholder used until the CEO authorizes live connectivity."""

    def request(self, method: str, path: str, **_: Any) -> Any:
        raise ProductionConnectivityBlocked(
            "live WooCommerce connectivity is not authorized in Sprint 3 foundation mode"
        )


class MockWooCommerceTransport:
    """Deterministic in-memory WooCommerce-like transport for isolated tests."""

    def __init__(self) -> None:
        self._products: dict[int, dict[str, Any]] = {}
        self._categories: dict[int, dict[str, Any]] = {}
        self._next_id = 1
        self._next_category_id = 1
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> Any:
        method = method.upper()
        self.calls.append({"method": method, "path": path, "params": dict(params or {}), "json": deepcopy(json_body)})

        if method == "GET" and path == "/products":
            sku = (params or {}).get("sku")
            products = list(self._products.values())
            if sku is not None:
                products = [p for p in products if p.get("sku") == sku]
            return deepcopy(products)

        if method == "GET" and path == "/products/categories":
            slug = (params or {}).get("slug")
            categories = list(self._categories.values())
            if slug is not None:
                categories = [c for c in categories if c.get("slug") == slug]
            return deepcopy(categories)

        if method == "POST" and path == "/products/categories":
            payload = dict(json_body or {})
            if any(c.get("slug") == payload.get("slug") for c in self._categories.values()):
                raise ValueError("duplicate category slug in mock WooCommerce")
            category_id = self._next_category_id
            self._next_category_id += 1
            payload["id"] = category_id
            self._categories[category_id] = payload
            return deepcopy(payload)

        if method == "PUT" and path.startswith("/products/categories/"):
            category_id = int(path.rsplit("/", 1)[1])
            if category_id not in self._categories:
                raise KeyError(category_id)
            self._categories[category_id].update(dict(json_body or {}))
            return deepcopy(self._categories[category_id])

        if method == "POST" and path == "/products":
            payload = dict(json_body or {})
            if any(p.get("sku") == payload.get("sku") for p in self._products.values()):
                raise ValueError("duplicate sku in mock WooCommerce")
            product_id = self._next_id
            self._next_id += 1
            payload["id"] = product_id
            self._products[product_id] = payload
            return deepcopy(payload)

        if method == "PUT" and path.startswith("/products/"):
            product_id = int(path.rsplit("/", 1)[1])
            if product_id not in self._products:
                raise KeyError(product_id)
            self._products[product_id].update(dict(json_body or {}))
            return deepcopy(self._products[product_id])

        raise NotImplementedError(f"mock route not implemented: {method} {path}")


class WooCommerceAdapter:
    """Bounded adapter over an injected transport.

    No live transport is provided in this sprint slice. Mutations additionally
    require `allow_mutations=True`, so read-only/mock consumers fail closed by
    default even when a transport is injected.
    """

    def __init__(
        self,
        transport: WooCommerceTransport | None = None,
        *,
        allow_mutations: bool = False,
        idempotency_store: MemoryIdempotencyStore | None = None,
        inventory_revision_store: MemoryInventoryRevisionStore | None = None,
    ) -> None:
        self.transport = transport or BlockedNetworkTransport()
        self.allow_mutations = allow_mutations
        self.idempotency_store = idempotency_store or MemoryIdempotencyStore()
        self.inventory_revision_store = inventory_revision_store or MemoryInventoryRevisionStore()

    def get_product_by_sku(self, sku: str) -> dict[str, Any] | None:
        result = self.transport.request("GET", "/products", params={"sku": sku})
        if not result:
            return None
        if len(result) > 1:
            raise ValueError(f"ambiguous WooCommerce SKU: {sku}")
        return result[0]

    def reconcile_product(self, product: ProductRecord, *, locale: str = "en") -> ReconciliationResult:
        desired = product.to_wc_payload(locale)
        current = self.get_product_by_sku(product.sku)
        key = idempotency_key("sync", "product", product.sku, desired)
        replay = self.idempotency_store.get(key)
        if replay is not None:
            return ReconciliationResult(
                action="replay",
                entity_key=replay.entity_key,
                idempotency_key=replay.idempotency_key,
                remote_id=replay.remote_id,
                before_fingerprint=replay.before_fingerprint,
                after_fingerprint=replay.after_fingerprint,
            )

        if current is not None:
            before = comparable_remote_product(current)
            if before == desired:
                result = ReconciliationResult(
                    action="noop",
                    entity_key=product.sku,
                    idempotency_key=key,
                    remote_id=int(current["id"]),
                    before_fingerprint=fingerprint(before),
                    after_fingerprint=fingerprint(desired),
                )
                self.idempotency_store.put(result)
                return result

        if not self.allow_mutations:
            raise ProductionConnectivityBlocked(
                "WooCommerce mutation is disabled; use isolated mock mode with explicit allow_mutations for tests"
            )

        if current is None:
            response = self.transport.request("POST", "/products", json_body=desired)
            before_fp = None
            action = "create"
        else:
            before_fp = fingerprint(comparable_remote_product(current))
            response = self.transport.request("PUT", f"/products/{int(current['id'])}", json_body=desired)
            action = "update"

        result = ReconciliationResult(
            action=action,
            entity_key=product.sku,
            idempotency_key=key,
            remote_id=int(response["id"]),
            before_fingerprint=before_fp,
            after_fingerprint=fingerprint(desired),
        )
        self.idempotency_store.put(result)
        return result

    def get_category_by_slug(self, slug: str) -> dict[str, Any] | None:
        result = self.transport.request("GET", "/products/categories", params={"slug": slug})
        if not result:
            return None
        if len(result) > 1:
            raise ValueError(f"ambiguous WooCommerce category slug: {slug}")
        return result[0]

    def reconcile_category(self, category: CategoryRecord, *, locale: str = "en") -> ReconciliationResult:
        desired = category.to_wc_payload(locale)
        current = self.get_category_by_slug(desired["slug"])
        key = idempotency_key("sync", "category", category.key, desired)
        replay = self.idempotency_store.get(key)
        if replay is not None:
            return ReconciliationResult("replay", replay.entity_key, replay.idempotency_key, replay.remote_id, replay.before_fingerprint, replay.after_fingerprint)

        if current is not None:
            before = {"name": current.get("name"), "slug": current.get("slug")}
            if before == desired:
                result = ReconciliationResult("noop", category.key, key, int(current["id"]), fingerprint(before), fingerprint(desired))
                self.idempotency_store.put(result)
                return result

        if not self.allow_mutations:
            raise ProductionConnectivityBlocked("WooCommerce category mutation is disabled")
        if current is None:
            response = self.transport.request("POST", "/products/categories", json_body=desired)
            before_fp = None
            action = "create"
        else:
            before = {"name": current.get("name"), "slug": current.get("slug")}
            before_fp = fingerprint(before)
            response = self.transport.request("PUT", f"/products/categories/{int(current['id'])}", json_body=desired)
            action = "update"
        result = ReconciliationResult(action, category.key, key, int(response["id"]), before_fp, fingerprint(desired))
        self.idempotency_store.put(result)
        return result

    def reconcile_inventory(self, inventory: InventoryRecord) -> ReconciliationResult:
        current = self.get_product_by_sku(inventory.sku)
        if current is None:
            raise ValueError(f"inventory product not found for SKU: {inventory.sku}")
        desired = inventory.to_wc_payload()
        key_material = dict(desired)
        key_material["source_of_truth"] = inventory.source_of_truth
        key_material["revision"] = inventory.revision
        revision_payload_fingerprint = fingerprint(key_material)
        self.inventory_revision_store.assert_accept(
            sku=inventory.sku,
            source_of_truth=inventory.source_of_truth,
            revision=inventory.revision,
            payload_fingerprint=revision_payload_fingerprint,
        )
        key = idempotency_key("sync", "inventory", inventory.sku, key_material)
        replay = self.idempotency_store.get(key)
        if replay is not None:
            self.inventory_revision_store.record(
                sku=inventory.sku,
                source_of_truth=inventory.source_of_truth,
                revision=inventory.revision,
                payload_fingerprint=revision_payload_fingerprint,
            )
            return ReconciliationResult("replay", replay.entity_key, replay.idempotency_key, replay.remote_id, replay.before_fingerprint, replay.after_fingerprint)
        before = {field: current.get(field) for field in ("manage_stock", "stock_quantity", "stock_status")}
        if before == desired:
            result = ReconciliationResult("noop", inventory.sku, key, int(current["id"]), fingerprint(before), fingerprint(desired))
            self.idempotency_store.put(result)
            self.inventory_revision_store.record(
                sku=inventory.sku,
                source_of_truth=inventory.source_of_truth,
                revision=inventory.revision,
                payload_fingerprint=revision_payload_fingerprint,
            )
            return result
        if not self.allow_mutations:
            raise ProductionConnectivityBlocked("WooCommerce inventory mutation is disabled")
        response = self.transport.request("PUT", f"/products/{int(current['id'])}", json_body=desired)
        result = ReconciliationResult("update", inventory.sku, key, int(response["id"]), fingerprint(before), fingerprint(desired))
        self.idempotency_store.put(result)
        self.inventory_revision_store.record(
            sku=inventory.sku,
            source_of_truth=inventory.source_of_truth,
            revision=inventory.revision,
            payload_fingerprint=revision_payload_fingerprint,
        )
        return result

    def plan_media(self, media: MediaRecord, *, locale: str = "en") -> dict[str, Any]:
        """Return a deterministic media manifest without performing an upload."""
        return media.upload_manifest(locale)
