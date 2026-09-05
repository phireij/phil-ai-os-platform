from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Mapping, Sequence


GOOGLE_ROUTES_COMPUTE_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
GOOGLE_ROUTES_FIELD_MASK = (
    "routes.distanceMeters,routes.duration,routes.travelAdvisory.tollInfo"
)
_DURATION_RE = re.compile(r"^(?P<seconds>[0-9]+(?:\.[0-9]+)?)s$")


class GoogleRoutesContractError(ValueError):
    """Fail-closed validation error for network-inert Google Routes mapping."""


@dataclass(frozen=True)
class GoogleRoutesComputeContract:
    """Build the bounded Compute Routes payload without performing any HTTP call."""

    origin_address: str
    destination_address: str
    language_code: str = "ja"

    def __post_init__(self) -> None:
        if not self.origin_address.strip():
            raise GoogleRoutesContractError("origin_address is required")
        if not self.destination_address.strip():
            raise GoogleRoutesContractError("destination_address is required")
        if not self.language_code.strip():
            raise GoogleRoutesContractError("language_code is required")

    def request_body(self) -> dict[str, object]:
        return {
            "origin": {"address": self.origin_address.strip()},
            "destination": {"address": self.destination_address.strip()},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
            "computeAlternativeRoutes": False,
            "routeModifiers": {
                "avoidTolls": False,
                "avoidHighways": False,
                "avoidFerries": False,
            },
            "languageCode": self.language_code.strip(),
            "units": "METRIC",
            "extraComputations": ["TOLLS"],
        }

    @staticmethod
    def field_mask() -> str:
        return GOOGLE_ROUTES_FIELD_MASK

    @staticmethod
    def endpoint() -> str:
        return GOOGLE_ROUTES_COMPUTE_URL


class GoogleRoutesResponseNormalizer:
    """Normalize one Compute Routes response into Ruby car route-observation fields.

    The output intentionally matches the injected `RubyCarRoutingTransport`
    observation contract. This class performs no HTTP request, stores no address,
    and grants no commerce/dispatch authority.
    """

    @classmethod
    def normalize(cls, payload: Mapping[str, object]) -> dict[str, object]:
        routes = payload.get("routes")
        if not isinstance(routes, Sequence) or isinstance(routes, (str, bytes)):
            raise GoogleRoutesContractError("routes must be an array")
        if len(routes) != 1:
            raise GoogleRoutesContractError("exactly one route is required")

        route = routes[0]
        if not isinstance(route, Mapping):
            raise GoogleRoutesContractError("route must be an object")

        distance = route.get("distanceMeters")
        if isinstance(distance, bool) or not isinstance(distance, int) or distance < 0:
            raise GoogleRoutesContractError("distanceMeters must be a non-negative integer")

        duration_seconds = cls._parse_duration(route.get("duration"))
        tolls_expected, toll_yen = cls._parse_toll_info(route.get("travelAdvisory"))

        return {
            "distance_meters": distance,
            "duration_seconds": duration_seconds,
            "tolls_expected": tolls_expected,
            "toll_yen": toll_yen,
            "exceptional_parking_expected": False,
        }

    @staticmethod
    def _parse_duration(raw: object) -> int:
        if not isinstance(raw, str):
            raise GoogleRoutesContractError("duration must be a protobuf duration string")
        match = _DURATION_RE.fullmatch(raw.strip())
        if not match:
            raise GoogleRoutesContractError("duration must be expressed in seconds")
        try:
            seconds = Decimal(match.group("seconds"))
        except InvalidOperation as exc:
            raise GoogleRoutesContractError("duration is invalid") from exc
        return int(seconds.to_integral_value(rounding=ROUND_CEILING))

    @classmethod
    def _parse_toll_info(cls, travel_advisory: object) -> tuple[bool, int | None]:
        if travel_advisory is None:
            return False, None
        if not isinstance(travel_advisory, Mapping):
            raise GoogleRoutesContractError("travelAdvisory must be an object")

        if "tollInfo" not in travel_advisory:
            return False, None
        toll_info = travel_advisory.get("tollInfo")
        if not isinstance(toll_info, Mapping):
            raise GoogleRoutesContractError("tollInfo must be an object")

        estimated_prices = toll_info.get("estimatedPrice")
        if estimated_prices is None:
            # Presence of tollInfo without a usable price is conservative: the
            # existing Ruby car policy will require manual review for toll price.
            return True, None
        if not isinstance(estimated_prices, Sequence) or isinstance(
            estimated_prices, (str, bytes)
        ):
            raise GoogleRoutesContractError("estimatedPrice must be an array")
        if not estimated_prices:
            return True, None

        jpy_prices = []
        for money in estimated_prices:
            if not isinstance(money, Mapping):
                raise GoogleRoutesContractError("estimatedPrice entries must be objects")
            if money.get("currencyCode") == "JPY":
                jpy_prices.append(cls._money_to_yen(money))

        if len(jpy_prices) != 1:
            return True, None
        return True, jpy_prices[0]

    @staticmethod
    def _money_to_yen(money: Mapping[str, object]) -> int:
        units_raw = money.get("units", "0")
        nanos_raw = money.get("nanos", 0)
        if isinstance(units_raw, bool) or isinstance(nanos_raw, bool):
            raise GoogleRoutesContractError("JPY toll amount is invalid")
        try:
            units = Decimal(str(units_raw))
            nanos = Decimal(str(nanos_raw))
        except InvalidOperation as exc:
            raise GoogleRoutesContractError("JPY toll amount is invalid") from exc
        if units < 0 or nanos < 0 or nanos >= Decimal("1000000000"):
            raise GoogleRoutesContractError("JPY toll amount is invalid")
        amount = units + nanos / Decimal("1000000000")
        return int(amount.to_integral_value(rounding=ROUND_CEILING))
