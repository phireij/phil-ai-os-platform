from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .adapter import ProductionConnectivityBlocked


@dataclass(frozen=True)
class ShippingMethodSummary:
    zone_id: int
    instance_id: int
    method_id: str
    title: str
    enabled: bool
    order: int
    method_title: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "instance_id": self.instance_id,
            "method_id": self.method_id,
            "title": self.title,
            "enabled": self.enabled,
            "order": self.order,
            "method_title": self.method_title,
        }


@dataclass(frozen=True)
class ShippingZoneSummary:
    zone_id: int
    name: str
    order: int
    methods: tuple[ShippingMethodSummary, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.zone_id,
            "name": self.name,
            "order": self.order,
            "methods": [method.as_dict() for method in self.methods],
        }


@dataclass(frozen=True)
class ReadOnlyShippingSnapshot:
    captured_at: str
    zones: tuple[ShippingZoneSummary, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope": "woocommerce_shipping_zone_method_metadata_read_only",
            "captured_at": self.captured_at,
            "network_read_only": True,
            "mutation_authorized": False,
            "payment_execution_authorized": False,
            "production_publish_authorized": False,
            "zones": [zone.as_dict() for zone in self.zones],
        }


def _safe_int(value: Any, *, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ProductionConnectivityBlocked(f"WooCommerce shipping {field} is invalid") from exc


def _safe_method(raw: Any, *, zone_id: int) -> ShippingMethodSummary:
    if not isinstance(raw, dict):
        raise ProductionConnectivityBlocked("WooCommerce shipping method payload must contain objects")

    method_id = str(raw.get("method_id") or "").strip()
    if not method_id:
        raise ProductionConnectivityBlocked("WooCommerce shipping method_id is missing")

    return ShippingMethodSummary(
        zone_id=zone_id,
        instance_id=_safe_int(raw.get("instance_id"), field="method instance_id"),
        method_id=method_id,
        title=str(raw.get("title") or ""),
        enabled=raw.get("enabled") is True,
        order=_safe_int(raw.get("order") or 0, field="method order"),
        method_title=str(raw.get("method_title") or ""),
    )


def _safe_zone(raw: Any, methods: tuple[ShippingMethodSummary, ...]) -> ShippingZoneSummary:
    if not isinstance(raw, dict):
        raise ProductionConnectivityBlocked("WooCommerce shipping zone payload must contain objects")

    zone_id = _safe_int(raw.get("id"), field="zone id")
    if zone_id < 0:
        raise ProductionConnectivityBlocked("WooCommerce shipping zone id must be non-negative")

    return ShippingZoneSummary(
        zone_id=zone_id,
        name=str(raw.get("name") or ""),
        order=_safe_int(raw.get("order") or 0, field="zone order"),
        methods=methods,
    )


def collect_shipping_snapshot(
    transport: Any,
    *,
    captured_at: str | None = None,
) -> ReadOnlyShippingSnapshot:
    """Collect sanitized WooCommerce shipping-zone/method metadata using GET only.

    Method `settings` are intentionally excluded because they can contain
    operational pricing/configuration values that are unnecessary for a basic
    connectivity/readiness snapshot. This collector never writes or enables a
    shipping method.
    """

    zones_payload = transport.request("GET", "/shipping/zones")
    if not isinstance(zones_payload, list):
        raise ProductionConnectivityBlocked("WooCommerce shipping zones response must be a list")

    zones: list[ShippingZoneSummary] = []
    for raw_zone in zones_payload:
        if not isinstance(raw_zone, dict):
            raise ProductionConnectivityBlocked("WooCommerce shipping zone payload must contain objects")
        zone_id = _safe_int(raw_zone.get("id"), field="zone id")
        methods_payload = transport.request("GET", f"/shipping/zones/{zone_id}/methods")
        if not isinstance(methods_payload, list):
            raise ProductionConnectivityBlocked("WooCommerce shipping methods response must be a list")
        methods = tuple(
            sorted(
                (_safe_method(item, zone_id=zone_id) for item in methods_payload),
                key=lambda item: (item.order, item.instance_id),
            )
        )
        zones.append(_safe_zone(raw_zone, methods))

    timestamp = captured_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return ReadOnlyShippingSnapshot(
        captured_at=timestamp,
        zones=tuple(sorted(zones, key=lambda item: (item.order, item.zone_id))),
    )
