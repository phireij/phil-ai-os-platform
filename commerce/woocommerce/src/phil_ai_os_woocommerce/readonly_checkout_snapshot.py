from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .adapter import ProductionConnectivityBlocked


@dataclass(frozen=True)
class PaymentGatewaySummary:
    gateway_id: str
    title: str
    enabled: bool
    order: int
    method_title: str
    method_supports: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.gateway_id,
            "title": self.title,
            "enabled": self.enabled,
            "order": self.order,
            "method_title": self.method_title,
            "method_supports": list(self.method_supports),
        }


@dataclass(frozen=True)
class ReadOnlyCheckoutSnapshot:
    captured_at: str
    gateways: tuple[PaymentGatewaySummary, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope": "woocommerce_payment_gateway_metadata_read_only",
            "captured_at": self.captured_at,
            "network_read_only": True,
            "mutation_authorized": False,
            "payment_execution_authorized": False,
            "production_publish_authorized": False,
            "gateways": [gateway.as_dict() for gateway in self.gateways],
        }


def _safe_gateway(raw: Any) -> PaymentGatewaySummary:
    if not isinstance(raw, dict):
        raise ProductionConnectivityBlocked("WooCommerce payment gateway payload must contain objects")

    gateway_id = str(raw.get("id") or "").strip()
    if not gateway_id:
        raise ProductionConnectivityBlocked("WooCommerce payment gateway id is missing")

    supports = raw.get("method_supports") or []
    if not isinstance(supports, list):
        raise ProductionConnectivityBlocked("WooCommerce payment gateway supports field must be a list")

    try:
        order = int(raw.get("order") or 0)
    except (TypeError, ValueError) as exc:
        raise ProductionConnectivityBlocked("WooCommerce payment gateway order is invalid") from exc

    return PaymentGatewaySummary(
        gateway_id=gateway_id,
        title=str(raw.get("title") or ""),
        enabled=raw.get("enabled") is True,
        order=order,
        method_title=str(raw.get("method_title") or ""),
        method_supports=tuple(str(item) for item in supports),
    )


def collect_checkout_snapshot(
    transport: Any,
    *,
    captured_at: str | None = None,
) -> ReadOnlyCheckoutSnapshot:
    """Collect safe WooCommerce checkout gateway metadata using GET only.

    Deliberately excludes the WooCommerce `settings` object because gateway
    settings may contain API credentials, webhook secrets, account identifiers,
    instructions, or other values that do not belong in a readiness artifact.
    """

    payload = transport.request("GET", "/payment_gateways")
    if not isinstance(payload, list):
        raise ProductionConnectivityBlocked("WooCommerce payment gateway response must be a list")

    gateways = tuple(sorted((_safe_gateway(item) for item in payload), key=lambda item: (item.order, item.gateway_id)))
    timestamp = captured_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return ReadOnlyCheckoutSnapshot(captured_at=timestamp, gateways=gateways)
