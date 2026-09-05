from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Iterable


class OrderIntakeError(ValueError):
    pass


def _validate_iso_date(value: str, field_name: str) -> None:
    try:
        date.fromisoformat(value)
    except Exception as exc:
        raise OrderIntakeError(f"{field_name} must be an ISO date") from exc


@dataclass(frozen=True)
class DeliveryAlternative:
    delivery_date: str
    time_window_code: str | None = None

    def __post_init__(self) -> None:
        _validate_iso_date(self.delivery_date, "delivery_date")
        if self.time_window_code is not None and not self.time_window_code.strip():
            raise OrderIntakeError("time_window_code cannot be blank")


@dataclass(frozen=True)
class DeliverySchedule:
    """Requested-vs-confirmed delivery lifecycle used before payment.

    Time-window codes are configuration-driven. The contract deliberately does
    not hard-code carrier window values into product data.
    """

    requested_date: str
    requested_time_window_code: str | None = None
    time_window_required: bool = False
    state: str = "requested"
    alternatives: tuple[DeliveryAlternative, ...] = ()
    confirmed_date: str | None = None
    confirmed_time_window_code: str | None = None

    def __post_init__(self) -> None:
        _validate_iso_date(self.requested_date, "requested_date")
        if self.requested_time_window_code is not None and not self.requested_time_window_code.strip():
            raise OrderIntakeError("requested_time_window_code cannot be blank")
        if self.time_window_required and not self.requested_time_window_code:
            raise OrderIntakeError("delivery time window is required for this shipment")
        if self.state not in {"requested", "alternatives_proposed", "confirmed"}:
            raise OrderIntakeError("unsupported delivery schedule state")
        if self.state == "requested":
            if self.alternatives or self.confirmed_date or self.confirmed_time_window_code:
                raise OrderIntakeError("requested schedule cannot contain later-stage evidence")
        elif self.state == "alternatives_proposed":
            if not self.alternatives:
                raise OrderIntakeError("alternatives_proposed requires at least one alternative")
            if self.confirmed_date or self.confirmed_time_window_code:
                raise OrderIntakeError("unaccepted alternatives cannot be marked confirmed")
        else:
            if not self.confirmed_date:
                raise OrderIntakeError("confirmed schedule requires confirmed_date")
            _validate_iso_date(self.confirmed_date, "confirmed_date")
            if self.time_window_required and not self.confirmed_time_window_code:
                raise OrderIntakeError("confirmed time window is required for this shipment")

    @property
    def delivery_confirmed(self) -> bool:
        return self.state == "confirmed"

    @property
    def payment_request_allowed_by_delivery(self) -> bool:
        return self.delivery_confirmed


def propose_delivery_alternatives(
    schedule: DeliverySchedule,
    alternatives: Iterable[DeliveryAlternative],
) -> DeliverySchedule:
    if schedule.state == "confirmed":
        raise OrderIntakeError("confirmed delivery cannot be replaced by alternatives")
    alternatives = tuple(alternatives)
    if not alternatives:
        raise OrderIntakeError("at least one delivery alternative is required")
    if schedule.time_window_required and any(not item.time_window_code for item in alternatives):
        raise OrderIntakeError("every alternative requires a time window for this shipment")
    return replace(
        schedule,
        state="alternatives_proposed",
        alternatives=alternatives,
        confirmed_date=None,
        confirmed_time_window_code=None,
    )


def confirm_delivery(
    schedule: DeliverySchedule,
    *,
    accepted_date: str,
    accepted_time_window_code: str | None,
) -> DeliverySchedule:
    _validate_iso_date(accepted_date, "accepted_date")
    if schedule.time_window_required and not accepted_time_window_code:
        raise OrderIntakeError("accepted time window is required for this shipment")

    allowed_pairs = {(schedule.requested_date, schedule.requested_time_window_code)}
    allowed_pairs.update((item.delivery_date, item.time_window_code) for item in schedule.alternatives)
    candidate = (accepted_date, accepted_time_window_code)
    if candidate not in allowed_pairs:
        raise OrderIntakeError("accepted delivery date/time was not requested or proposed")

    return DeliverySchedule(
        requested_date=schedule.requested_date,
        requested_time_window_code=schedule.requested_time_window_code,
        time_window_required=schedule.time_window_required,
        state="confirmed",
        alternatives=schedule.alternatives,
        confirmed_date=accepted_date,
        confirmed_time_window_code=accepted_time_window_code,
    )


PRIVATE_IMAGE_MEDIA_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


@dataclass(frozen=True)
class PrivateImageUploadRef:
    """Opaque reference to a customer-uploaded private order input."""

    storage_ref: str
    media_type: str
    byte_size: int
    visibility: str = "private_order_input"

    def __post_init__(self) -> None:
        if not self.storage_ref.strip():
            raise OrderIntakeError("storage_ref is required")
        if self.storage_ref.startswith(("http://", "https://")):
            raise OrderIntakeError("private upload must use an opaque storage reference, not a public URL")
        if self.media_type not in PRIVATE_IMAGE_MEDIA_TYPES:
            raise OrderIntakeError("unsupported custom-cake image media type")
        if self.byte_size <= 0:
            raise OrderIntakeError("byte_size must be positive")
        if self.visibility != "private_order_input":
            raise OrderIntakeError("custom-cake uploads must remain private order inputs")


@dataclass(frozen=True)
class CustomCakeRequest:
    request_id: str
    requested_delivery_date: str
    size_or_servings: str
    flavor: str
    layers: int
    theme_or_colors: str = ""
    inscription: str = ""
    notes: str = ""
    budget_yen: int | None = None
    reference_images: tuple[PrivateImageUploadRef, ...] = ()
    photo_topper_requested: bool = False
    edible_topper_requested: bool = False

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise OrderIntakeError("request_id is required")
        _validate_iso_date(self.requested_delivery_date, "requested_delivery_date")
        if not self.size_or_servings.strip():
            raise OrderIntakeError("size_or_servings is required")
        if not self.flavor.strip():
            raise OrderIntakeError("flavor is required")
        if self.layers <= 0:
            raise OrderIntakeError("layers must be positive")
        if self.budget_yen is not None and self.budget_yen < 0:
            raise OrderIntakeError("budget_yen cannot be negative")
        if len(self.reference_images) > 8:
            raise OrderIntakeError("at most 8 reference images are accepted")

    @property
    def pricing_mode(self) -> str:
        return "quote_required"

    @property
    def standalone_topper_sale(self) -> bool:
        return False


ADDON_KINDS = frozenset(
    {
        "candle",
        "number_candle",
        "message_plaque",
        "photo_topper",
        "edible_topper",
        "cake_extra",
    }
)


@dataclass(frozen=True)
class AddonSkuDefinition:
    sku: str
    kind: str
    unit_price_yen: int | None
    requires_cake_parent: bool = True
    standalone_allowed: bool = False

    def __post_init__(self) -> None:
        if not self.sku.strip():
            raise OrderIntakeError("add-on sku is required")
        if self.kind not in ADDON_KINDS:
            raise OrderIntakeError("unsupported add-on kind")
        if self.unit_price_yen is not None and self.unit_price_yen < 0:
            raise OrderIntakeError("unit_price_yen cannot be negative")
        if self.kind in {"photo_topper", "edible_topper"} and self.standalone_allowed:
            raise OrderIntakeError("photo/edible toppers cannot be standalone products")
        if self.kind in {"photo_topper", "edible_topper"} and not self.requires_cake_parent:
            raise OrderIntakeError("photo/edible toppers require a cake parent")


@dataclass(frozen=True)
class AddonSelection:
    parent_cake_sku: str
    addon_sku: str
    quantity: int = 1

    def __post_init__(self) -> None:
        if not self.parent_cake_sku.strip():
            raise OrderIntakeError("parent_cake_sku is required")
        if not self.addon_sku.strip():
            raise OrderIntakeError("addon_sku is required")
        if self.quantity <= 0:
            raise OrderIntakeError("add-on quantity must be positive")


@dataclass(frozen=True)
class IcingPreference:
    """Non-pricing intake only; Ruby's color surcharge remains pending."""

    icing_requested: bool
    colors: tuple[str, ...] = ()
    pricing_status: str = "pending_business_confirmation"

    def __post_init__(self) -> None:
        normalized = tuple(value.strip().lower() for value in self.colors if value.strip())
        if self.icing_requested and not normalized:
            normalized = ("white",)
        if not self.icing_requested and normalized:
            raise OrderIntakeError("icing colors cannot be selected when icing is not requested")
        if len(set(normalized)) != len(normalized):
            raise OrderIntakeError("icing colors must be unique")
        if self.pricing_status != "pending_business_confirmation":
            raise OrderIntakeError("icing color pricing is not approved for activation")
        object.__setattr__(self, "colors", normalized)

    @property
    def price_delta_yen(self) -> None:
        return None


@dataclass(frozen=True)
class CustomCakeQuote:
    request_id: str
    cake_price_yen: int
    addon_total_yen: int
    delivery_fee_yen: int
    delivery_confirmed: bool
    status: str = "draft"

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise OrderIntakeError("request_id is required")
        for value, name in (
            (self.cake_price_yen, "cake_price_yen"),
            (self.addon_total_yen, "addon_total_yen"),
            (self.delivery_fee_yen, "delivery_fee_yen"),
        ):
            if value < 0:
                raise OrderIntakeError(f"{name} cannot be negative")
        if self.status not in {"draft", "approved"}:
            raise OrderIntakeError("unsupported custom-cake quote status")
        if self.status == "approved" and not self.delivery_confirmed:
            raise OrderIntakeError("quote cannot be approved before delivery is confirmed")

    @property
    def total_yen(self) -> int:
        return self.cake_price_yen + self.addon_total_yen + self.delivery_fee_yen

    @property
    def payment_request_allowed(self) -> bool:
        return self.status == "approved" and self.delivery_confirmed
