from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Protocol

from .models import ProductRecord
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
        self._next_id = 1
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
    ) -> None:
        self.transport = transport or BlockedNetworkTransport()
        self.allow_mutations = allow_mutations
        self.idempotency_store = idempotency_store or MemoryIdempotencyStore()

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
