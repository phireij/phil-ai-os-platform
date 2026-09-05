from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from .fulfillment_policy import (
    RUBY_CAR_ALLOWED_PREFECTURES,
    RUBY_SHOP_ORIGIN_REF,
    RubyCarRouteFacts,
)


class RubyCarRoutingError(RuntimeError):
    """Fail-closed error raised by the non-mutating Ruby car routing boundary."""


class RubyCarRoutingTransport(Protocol):
    """Read-only route-computation boundary.

    A future Google Routes implementation may satisfy this protocol. No concrete
    network transport is provided here, so this module cannot make a live route
    request by itself.
    """

    def compute_route(
        self,
        *,
        destination_address: str,
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        ...


@dataclass(frozen=True)
class RubyCarRoutingConfig:
    provider: str = "unconfigured"
    enabled: bool = False
    timeout_seconds: float = 8.0

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider is required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class RubyCarRouteRequest:
    destination_address: str
    destination_prefecture: str
    origin_ref: str = RUBY_SHOP_ORIGIN_REF

    def __post_init__(self) -> None:
        if self.origin_ref != RUBY_SHOP_ORIGIN_REF:
            raise ValueError("Ruby car routing origin must remain the Ichikawa shop")
        if not self.destination_address.strip():
            raise ValueError("destination_address is required")
        if not self.destination_prefecture.strip():
            raise ValueError("destination_prefecture is required")


@dataclass(frozen=True)
class RubyCarRoutingResult:
    status: str
    provider: str
    route_facts: RubyCarRouteFacts | None
    route_request_attempted: bool
    requires_manual_review: bool
    reasons: tuple[str, ...]
    order_mutation_authorized: bool = False
    payment_authorized: bool = False
    dispatch_authorized: bool = False

    def safe_audit_dict(self) -> dict[str, object]:
        """Return a projection that deliberately excludes the customer address."""

        return {
            "status": self.status,
            "provider": self.provider,
            "route_request_attempted": self.route_request_attempted,
            "requires_manual_review": self.requires_manual_review,
            "reasons": list(self.reasons),
            "origin_ref": self.route_facts.origin_ref if self.route_facts else RUBY_SHOP_ORIGIN_REF,
            "destination_prefecture": (
                self.route_facts.destination_prefecture if self.route_facts else None
            ),
            "order_mutation_authorized": False,
            "payment_authorized": False,
            "dispatch_authorized": False,
        }


class RubyCarRoutingAdapter:
    """Bounded one-way route adapter for Ruby car delivery.

    The adapter is disabled by default, has no built-in network transport, makes
    at most one injected route-computation call, and never creates/changes an
    order, authorizes payment, or dispatches a vehicle. Route facts remain input
    to `RubyCarDeliveryPolicy`; they do not constitute a delivery confirmation.
    """

    def __init__(
        self,
        config: RubyCarRoutingConfig | None = None,
        transport: RubyCarRoutingTransport | None = None,
    ) -> None:
        self.config = config or RubyCarRoutingConfig()
        self.transport = transport

    def compute(self, route_request: RubyCarRouteRequest) -> RubyCarRoutingResult:
        if not self.config.enabled:
            return RubyCarRoutingResult(
                status="disabled",
                provider=self.config.provider,
                route_facts=None,
                route_request_attempted=False,
                requires_manual_review=True,
                reasons=("routing_provider_not_enabled",),
            )

        if route_request.destination_prefecture not in RUBY_CAR_ALLOWED_PREFECTURES:
            return RubyCarRoutingResult(
                status="not_routable",
                provider=self.config.provider,
                route_facts=None,
                route_request_attempted=False,
                requires_manual_review=False,
                reasons=("destination_prefecture_outside_service_area",),
            )

        if self.transport is None:
            raise RubyCarRoutingError("routing transport is not configured")

        try:
            payload = self.transport.compute_route(
                destination_address=route_request.destination_address.strip(),
                timeout_seconds=self.config.timeout_seconds,
            )
        except Exception as exc:
            raise RubyCarRoutingError("route computation failed safely") from exc

        facts = self._parse_route_facts(route_request, payload)
        return RubyCarRoutingResult(
            status="route_facts_ready",
            provider=self.config.provider,
            route_facts=facts,
            route_request_attempted=True,
            requires_manual_review=False,
            reasons=(),
        )

    @staticmethod
    def _parse_route_facts(
        route_request: RubyCarRouteRequest,
        payload: Mapping[str, object],
    ) -> RubyCarRouteFacts:
        try:
            distance_meters = int(payload["distance_meters"])
            duration_seconds = int(payload["duration_seconds"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RubyCarRoutingError("route response is missing valid distance/duration facts") from exc

        tolls_expected = payload.get("tolls_expected", False)
        if not isinstance(tolls_expected, bool):
            raise RubyCarRoutingError("tolls_expected must be boolean")

        toll_yen_raw = payload.get("toll_yen")
        if toll_yen_raw is None:
            toll_yen = None
        else:
            if isinstance(toll_yen_raw, bool):
                raise RubyCarRoutingError("toll_yen must be an integer")
            try:
                toll_yen = int(toll_yen_raw)
            except (TypeError, ValueError) as exc:
                raise RubyCarRoutingError("toll_yen must be an integer") from exc

        exceptional_parking_expected = payload.get("exceptional_parking_expected", False)
        if not isinstance(exceptional_parking_expected, bool):
            raise RubyCarRoutingError("exceptional_parking_expected must be boolean")

        try:
            return RubyCarRouteFacts(
                destination_prefecture=route_request.destination_prefecture,
                distance_meters=distance_meters,
                duration_seconds=duration_seconds,
                tolls_expected=tolls_expected,
                toll_yen=toll_yen,
                exceptional_parking_expected=exceptional_parking_expected,
                origin_ref=route_request.origin_ref,
            )
        except ValueError as exc:
            raise RubyCarRoutingError("route response violated Ruby car policy facts") from exc
