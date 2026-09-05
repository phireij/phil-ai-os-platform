from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable


TEMPERATURE_CLASSES = frozenset({"ambient", "chilled", "frozen"})
YAMATO_METHODS = frozenset({"yamato_ambient", "yamato_chilled", "yamato_frozen"})
RUBY_CAR_ALLOWED_PREFECTURES = frozenset({"Chiba", "Tokyo", "Kanagawa", "Saitama"})
RUBY_SHOP_ORIGIN_REF = "ruby_shop_ichikawa"


class FulfillmentPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class ProductFulfillmentRule:
    """Product-level fulfillment facts used before payment is requested.

    `cool_eligible` means an ambient item may safely travel chilled. It does not
    imply that the item may be frozen. Product-specific transport eligibility is
    explicit so sensitive cakes can disable Yamato while retaining pickup/car.
    """

    sku: str
    temperature_class: str
    cool_eligible: bool = False
    is_cake: bool = False
    yamato_allowed: bool = True
    ruby_car_allowed: bool = False
    pickup_allowed: bool = True

    def __post_init__(self) -> None:
        if not self.sku.strip():
            raise FulfillmentPolicyError("sku is required")
        if self.temperature_class not in TEMPERATURE_CLASSES:
            raise FulfillmentPolicyError("unsupported temperature_class")
        if self.temperature_class != "ambient" and self.cool_eligible:
            raise FulfillmentPolicyError("cool_eligible is only meaningful for ambient products")
        if not (self.yamato_allowed or self.ruby_car_allowed or self.pickup_allowed):
            raise FulfillmentPolicyError("at least one fulfillment method must be allowed")


@dataclass(frozen=True)
class CartLine:
    product: ProductFulfillmentRule
    quantity: int = 1

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise FulfillmentPolicyError("quantity must be positive")


@dataclass(frozen=True)
class CartFulfillmentDecision:
    default_yamato_method: str | None
    allowed_methods: tuple[str, ...]
    chilled_upgrade_available: bool
    yamato_time_window_required: bool
    yamato_no_preference_allowed: bool
    requires_manual_review: bool
    requires_split_or_alternate: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CartPackingFacts:
    """Packing evidence available after cart/box review but before payment.

    Yamato Cool TA-Q-BIN is fail-closed at Size 120 / 15 kg. Values may be
    omitted during initial checkout and supplied later when Ruby/Phil AI OS
    finalizes the parcel. No fee or payment is finalized by this object.
    """

    yamato_size: int | None = None
    weight_kg: float | None = None

    def __post_init__(self) -> None:
        if self.yamato_size is not None and self.yamato_size <= 0:
            raise FulfillmentPolicyError("yamato_size must be positive")
        if self.weight_kg is not None and self.weight_kg <= 0:
            raise FulfillmentPolicyError("weight_kg must be positive")


class RubyCartFulfillmentPolicy:
    """Evaluate mixed-cart shipping without authorizing production mutation."""

    COOL_MAX_SIZE = 120
    COOL_MAX_WEIGHT_KG = 15.0

    @classmethod
    def evaluate(
        cls,
        lines: Iterable[CartLine],
        *,
        packing: CartPackingFacts | None = None,
    ) -> CartFulfillmentDecision:
        lines = tuple(lines)
        if not lines:
            raise FulfillmentPolicyError("cart must contain at least one line")

        products = tuple(line.product for line in lines)
        reasons: list[str] = []
        requires_manual_review = False
        requires_split_or_alternate = False

        all_pickup = all(p.pickup_allowed for p in products)
        all_car = all(p.ruby_car_allowed for p in products)
        all_yamato = all(p.yamato_allowed for p in products)
        has_cake = any(p.is_cake for p in products)
        temperatures = {p.temperature_class for p in products}

        default_yamato_method: str | None = None
        chilled_upgrade_available = False
        yamato_compatible = all_yamato

        if "frozen" in temperatures:
            # No generic frozen-upgrade compatibility is inferred. A frozen cart
            # mixed with any non-frozen product must be split/reviewed.
            if temperatures == {"frozen"}:
                default_yamato_method = "yamato_frozen"
            else:
                yamato_compatible = False
                requires_manual_review = True
                requires_split_or_alternate = True
                reasons.append("mixed_frozen_nonfrozen_requires_split_or_alternate")
        elif "chilled" in temperatures:
            ambient_products = tuple(p for p in products if p.temperature_class == "ambient")
            incompatible_ambient = tuple(p for p in ambient_products if not p.cool_eligible)
            if incompatible_ambient:
                yamato_compatible = False
                requires_manual_review = True
                requires_split_or_alternate = True
                reasons.append("ambient_item_not_chilled_compatible")
            else:
                default_yamato_method = "yamato_chilled"
        else:
            default_yamato_method = "yamato_ambient"
            chilled_upgrade_available = all(p.cool_eligible for p in products)

        if not all_yamato:
            yamato_compatible = False
            reasons.append("one_or_more_products_disallow_yamato")

        if packing is not None and default_yamato_method in {"yamato_chilled", "yamato_frozen"}:
            if packing.yamato_size is not None and packing.yamato_size > cls.COOL_MAX_SIZE:
                yamato_compatible = False
                requires_manual_review = True
                requires_split_or_alternate = True
                reasons.append("yamato_cool_size_exceeds_120")
            if packing.weight_kg is not None and packing.weight_kg > cls.COOL_MAX_WEIGHT_KG:
                yamato_compatible = False
                requires_manual_review = True
                requires_split_or_alternate = True
                reasons.append("yamato_cool_weight_exceeds_15kg")

        allowed: list[str] = []
        if all_pickup:
            allowed.append("shop_pickup")
        if all_car:
            allowed.append("ruby_car")
        if yamato_compatible and default_yamato_method:
            allowed.append(default_yamato_method)
            if default_yamato_method == "yamato_ambient" and chilled_upgrade_available:
                allowed.append("yamato_chilled")

        if not allowed:
            requires_manual_review = True
            reasons.append("no_single_fulfillment_method_covers_entire_cart")

        return CartFulfillmentDecision(
            default_yamato_method=default_yamato_method if yamato_compatible else None,
            allowed_methods=tuple(allowed),
            chilled_upgrade_available=bool(yamato_compatible and chilled_upgrade_available),
            yamato_time_window_required=bool(yamato_compatible and has_cake),
            yamato_no_preference_allowed=bool(yamato_compatible and not has_cake),
            requires_manual_review=requires_manual_review,
            requires_split_or_alternate=requires_split_or_alternate,
            reasons=tuple(reasons),
        )


@dataclass(frozen=True)
class RubyCarRouteFacts:
    """Route-provider output for a one-way trip from Ruby's shop to customer."""

    destination_prefecture: str
    distance_meters: int
    duration_seconds: int
    tolls_expected: bool = False
    toll_yen: int | None = None
    exceptional_parking_expected: bool = False
    origin_ref: str = RUBY_SHOP_ORIGIN_REF

    def __post_init__(self) -> None:
        if self.origin_ref != RUBY_SHOP_ORIGIN_REF:
            raise FulfillmentPolicyError("Ruby car delivery origin must be the Ichikawa shop")
        if self.distance_meters < 0:
            raise FulfillmentPolicyError("distance_meters must be non-negative")
        if self.duration_seconds < 0:
            raise FulfillmentPolicyError("duration_seconds must be non-negative")
        if self.toll_yen is not None and self.toll_yen < 0:
            raise FulfillmentPolicyError("toll_yen must be non-negative")
        if self.toll_yen is not None and not self.tolls_expected:
            raise FulfillmentPolicyError("toll_yen requires tolls_expected=true")


@dataclass(frozen=True)
class RubyCarDeliveryQuote:
    status: str
    base_delivery_fee_yen: int | None
    toll_yen: int | None
    provisional_total_yen: int | None
    billable_one_way_km: int
    requires_manual_review: bool
    reasons: tuple[str, ...]
    payment_authorized: bool = False


class RubyCarDeliveryPolicy:
    """CEO-approved provisional Ruby car delivery pricing foundation.

    Customer-facing distance is one-way from Ruby's Ichikawa shop. The business
    may account for the return trip internally. This policy only prepares a
    provisional quote; it never authorizes payment, fulfillment, or dispatch.
    """

    MINIMUM_FEE_YEN = 2500
    INCLUDED_KM = 10
    MID_BAND_MAX_KM = 30
    AUTO_MAX_KM = 50
    MANUAL_MAX_KM = 80
    MID_BAND_YEN_PER_KM = 150
    HIGH_BAND_YEN_PER_KM = 200
    MANUAL_DURATION_SECONDS = 75 * 60

    @classmethod
    def quote(cls, route: RubyCarRouteFacts) -> RubyCarDeliveryQuote:
        reasons: list[str] = []
        requires_manual_review = False
        distance_km = route.distance_meters / 1000.0
        billable_km = ceil(distance_km)

        if route.destination_prefecture not in RUBY_CAR_ALLOWED_PREFECTURES:
            return RubyCarDeliveryQuote(
                status="unavailable",
                base_delivery_fee_yen=None,
                toll_yen=route.toll_yen,
                provisional_total_yen=None,
                billable_one_way_km=billable_km,
                requires_manual_review=False,
                reasons=("destination_prefecture_outside_service_area",),
            )

        if distance_km > cls.MANUAL_MAX_KM:
            return RubyCarDeliveryQuote(
                status="unavailable",
                base_delivery_fee_yen=None,
                toll_yen=route.toll_yen,
                provisional_total_yen=None,
                billable_one_way_km=billable_km,
                requires_manual_review=False,
                reasons=("distance_exceeds_80km",),
            )

        if distance_km > cls.AUTO_MAX_KM:
            requires_manual_review = True
            reasons.append("distance_over_50km_requires_manual_quote")

        if route.duration_seconds > cls.MANUAL_DURATION_SECONDS:
            requires_manual_review = True
            reasons.append("one_way_duration_over_75_minutes")

        if route.tolls_expected and route.toll_yen is None:
            requires_manual_review = True
            reasons.append("toll_price_unavailable")

        if route.exceptional_parking_expected:
            requires_manual_review = True
            reasons.append("exceptional_parking_requires_manual_review")

        base_fee: int | None
        if distance_km <= cls.AUTO_MAX_KM:
            if billable_km <= cls.INCLUDED_KM:
                base_fee = cls.MINIMUM_FEE_YEN
            elif billable_km <= cls.MID_BAND_MAX_KM:
                base_fee = cls.MINIMUM_FEE_YEN + (
                    billable_km - cls.INCLUDED_KM
                ) * cls.MID_BAND_YEN_PER_KM
            else:
                fee_at_30 = cls.MINIMUM_FEE_YEN + (
                    cls.MID_BAND_MAX_KM - cls.INCLUDED_KM
                ) * cls.MID_BAND_YEN_PER_KM
                base_fee = fee_at_30 + (
                    billable_km - cls.MID_BAND_MAX_KM
                ) * cls.HIGH_BAND_YEN_PER_KM
        else:
            base_fee = None

        provisional_total = None
        if base_fee is not None and (not route.tolls_expected or route.toll_yen is not None):
            provisional_total = base_fee + int(route.toll_yen or 0)

        status = "manual_review" if requires_manual_review else "provisional_quote"
        return RubyCarDeliveryQuote(
            status=status,
            base_delivery_fee_yen=base_fee,
            toll_yen=route.toll_yen,
            provisional_total_yen=provisional_total,
            billable_one_way_km=billable_km,
            requires_manual_review=requires_manual_review,
            reasons=tuple(reasons),
        )
