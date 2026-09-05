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


def _optional_int(value: Any, *, context: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProductionConnectivityBlocked(
            f"WooCommerce read-only snapshot {context} must be an integer or null"
        )
    return value


def _string_field(value: Mapping[str, Any], field: str, *, context: str) -> str:
    raw = value.get(field)
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise ProductionConnectivityBlocked(
            f"WooCommerce read-only snapshot {context}.{field} must be a string or null"
        )
    return raw


def _bool_field(value: Mapping[str, Any], field: str, *, context: str, default: bool = False) -> bool:
    raw = value.get(field, default)
    if not isinstance(raw, bool):
        raise ProductionConnectivityBlocked(
            f"WooCommerce read-only snapshot {context}.{field} must be a boolean"
        )
    return raw


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
                "id": _optional_int(category.get("id"), context="product category id"),
                "name": _string_field(category, "name", context="product category"),
                "slug": _string_field(category, "slug", context="product category"),
            }
        )

    images = []
    for image in _validated_nested_mappings(value, "images"):
        images.append(
            {
                "id": _optional_int(image.get("id"), context="product image id"),
                "name": _string_field(image, "name", context="product image"),
                "alt": _string_field(image, "alt", context="product image"),
            }
        )

    return {
        "id": _optional_int(value.get("id"), context="product id"),
        "sku": _string_field(value, "sku", context="product"),
        "name": _string_field(value, "name", context="product"),
        "slug": _string_field(value, "slug", context="product"),
        "type": _string_field(value, "type", context="product"),
        "status": _string_field(value, "status", context="product"),
        "catalog_visibility": _string_field(value, "catalog_visibility", context="product"),
        "regular_price": _string_field(value, "regular_price", context="product"),
        "manage_stock": _bool_field(value, "manage_stock", context="product"),
        "stock_quantity": _optional_int(value.get("stock_quantity"), context="product stock_quantity"),
        "stock_status": _string_field(value, "stock_status", context="product"),
        "shipping_class": _string_field(value, "shipping_class", context="product"),
        "date_modified_gmt": _string_field(value, "date_modified_gmt", context="product"),
        "categories": categories,
        "images": images,
    }


def _category_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": _optional_int(value.get("id"), context="category id"),
        "name": _string_field(value, "name", context="category"),
        "slug": _string_field(value, "slug", context="category"),
        "parent": _optional_int(value.get("parent"), context="category parent"),
        "count": _optional_int(value.get("count"), context="category count"),
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
