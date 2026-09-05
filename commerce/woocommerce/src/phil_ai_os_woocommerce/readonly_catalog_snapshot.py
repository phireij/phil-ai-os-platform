from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from .adapter import ProductionConnectivityBlocked


class ReadOnlyWooCommerceTransport(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> Any: ...


@dataclass(frozen=True)
class CatalogSnapshot:
    captured_at: str
    products: tuple[dict[str, Any], ...]
    categories: tuple[dict[str, Any], ...]
    network_read_only: bool = True
    mutation_authorized: bool = False
    production_publish_authorized: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "captured_at": self.captured_at,
            "scope": "woocommerce_catalog_metadata_read_only",
            "network_read_only": self.network_read_only,
            "mutation_authorized": self.mutation_authorized,
            "production_publish_authorized": self.production_publish_authorized,
            "products": list(self.products),
            "categories": list(self.categories),
        }


def _validated_capture_timestamp(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("captured_at must be a timezone-aware ISO timestamp")
    normalized = value.strip()
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("captured_at must be a timezone-aware ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("captured_at must be a timezone-aware ISO timestamp")
    return normalized


def _bounded_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _validated_nested_mappings(value: Mapping[str, Any], field: str) -> list[Mapping[str, Any]]:
    nested = value.get(field, [])
    if not isinstance(nested, list):
        raise ProductionConnectivityBlocked(
            f"WooCommerce read-only snapshot product {field} must be a list"
        )
    if not all(isinstance(item, Mapping) for item in nested):
        raise ProductionConnectivityBlocked(
            f"WooCommerce read-only snapshot product {field} contains invalid item"
        )
    return nested


def _product_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    categories = []
    for category in _validated_nested_mappings(value, "categories"):
        categories.append(
            {
                "id": _bounded_int(category.get("id")),
                "name": str(category.get("name") or ""),
                "slug": str(category.get("slug") or ""),
            }
        )

    images = []
    for image in _validated_nested_mappings(value, "images"):
        images.append(
            {
                "id": _bounded_int(image.get("id")),
                "name": str(image.get("name") or ""),
                "alt": str(image.get("alt") or ""),
            }
        )

    return {
        "id": _bounded_int(value.get("id")),
        "sku": str(value.get("sku") or ""),
        "name": str(value.get("name") or ""),
        "slug": str(value.get("slug") or ""),
        "type": str(value.get("type") or ""),
        "status": str(value.get("status") or ""),
        "catalog_visibility": str(value.get("catalog_visibility") or ""),
        "regular_price": str(value.get("regular_price") or ""),
        "manage_stock": bool(value.get("manage_stock", False)),
        "stock_quantity": _bounded_int(value.get("stock_quantity")),
        "stock_status": str(value.get("stock_status") or ""),
        "shipping_class": str(value.get("shipping_class") or ""),
        "date_modified_gmt": str(value.get("date_modified_gmt") or ""),
        "categories": categories,
        "images": images,
    }


def _category_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": _bounded_int(value.get("id")),
        "name": str(value.get("name") or ""),
        "slug": str(value.get("slug") or ""),
        "parent": _bounded_int(value.get("parent")),
        "count": _bounded_int(value.get("count")),
    }


def _collect_pages(
    transport: ReadOnlyWooCommerceTransport,
    path: str,
    *,
    per_page: int,
    max_pages: int,
) -> list[Mapping[str, Any]]:
    if per_page < 1 or per_page > 100:
        raise ValueError("per_page must be between 1 and 100")
    if max_pages < 1 or max_pages > 20:
        raise ValueError("max_pages must be between 1 and 20")

    collected: list[Mapping[str, Any]] = []
    for page in range(1, max_pages + 1):
        payload = transport.request(
            "GET",
            path,
            params={"per_page": str(per_page), "page": str(page)},
        )
        if not isinstance(payload, list):
            raise ProductionConnectivityBlocked("WooCommerce read-only snapshot returned unexpected payload")
        if not all(isinstance(item, Mapping) for item in payload):
            raise ProductionConnectivityBlocked("WooCommerce read-only snapshot returned invalid item")
        collected.extend(payload)
        if len(payload) < per_page:
            break
    else:
        raise ProductionConnectivityBlocked("WooCommerce read-only snapshot exceeded bounded pagination")
    return collected


def collect_catalog_snapshot(
    transport: ReadOnlyWooCommerceTransport,
    *,
    captured_at: str | None = None,
    per_page: int = 100,
    max_pages: int = 10,
) -> CatalogSnapshot:
    """Collect bounded WooCommerce catalog metadata using GET requests only."""

    timestamp = _validated_capture_timestamp(captured_at)
    products_raw = _collect_pages(transport, "/products", per_page=per_page, max_pages=max_pages)
    categories_raw = _collect_pages(
        transport,
        "/products/categories",
        per_page=per_page,
        max_pages=max_pages,
    )

    products = tuple(sorted((_product_projection(item) for item in products_raw), key=lambda item: (item["sku"], item["id"] or -1)))
    categories = tuple(sorted((_category_projection(item) for item in categories_raw), key=lambda item: (item["slug"], item["id"] or -1)))

    return CatalogSnapshot(
        captured_at=timestamp,
        products=products,
        categories=categories,
    )
