from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


AMBIENT_PACKAGE_COMPACT = "ambient_compact"
AMBIENT_PACKAGE_60 = "ambient_60"
AMBIENT_PACKAGE_80 = "ambient_80"
AMBIENT_PACKAGE_100 = "ambient_100"
AMBIENT_PACKAGE_120 = "ambient_120"

AMBIENT_PACKAGE_CLASSES = (
    AMBIENT_PACKAGE_COMPACT,
    AMBIENT_PACKAGE_60,
    AMBIENT_PACKAGE_80,
    AMBIENT_PACKAGE_100,
    AMBIENT_PACKAGE_120,
)
_PACKAGE_RANK = {name: rank for rank, name in enumerate(AMBIENT_PACKAGE_CLASSES)}


class AmbientPackagingError(ValueError):
    pass


@dataclass(frozen=True)
class AmbientPackageLine:
    """Catalog facts needed to choose a safe ambient Yamato package class.

    `minimum_package_class` is the smallest package class that the SKU may use
    when shipped by itself. `ambient_compact` is reserved for SKUs that have
    been physically verified as suitable for Yamato TA-Q-BIN Compact.

    The selector deliberately does not infer multi-unit Compact fit from a
    single-unit catalog fact. Multi-unit or mixed Compact carts fall back to
    regular Size 60 unless packing evidence explicitly confirms Compact fit.
    """

    sku: str
    quantity: int = 1
    minimum_package_class: str = AMBIENT_PACKAGE_60

    def __post_init__(self) -> None:
        if not self.sku.strip():
            raise AmbientPackagingError("sku is required")
        if self.quantity <= 0:
            raise AmbientPackagingError("quantity must be positive")
        if self.minimum_package_class not in _PACKAGE_RANK:
            raise AmbientPackagingError("unsupported minimum_package_class")


@dataclass(frozen=True)
class AmbientPackingEvidence:
    """Human/packing-system confirmation available before checkout finalization.

    This is intentionally a classification-level contract rather than a full
    dimensional packing engine. Physical fit, cushioning and box closure remain
    operational evidence. Supplying a confirmed class never authorizes a live
    WooCommerce mutation or shipment.
    """

    confirmed_package_class: str

    def __post_init__(self) -> None:
        if self.confirmed_package_class not in _PACKAGE_RANK:
            raise AmbientPackagingError("unsupported confirmed_package_class")


@dataclass(frozen=True)
class AmbientPackageDecision:
    package_class: str | None
    yamato_service: str | None
    requires_manual_review: bool
    reasons: tuple[str, ...]
    production_mutation_authorized: bool = False


class AmbientShippingPackagingPolicy:
    """Select the minimum safe ambient shipping package class, fail-closed.

    Rules:
    - A SKU's declared minimum class is never downgraded.
    - A single quantity-1 Compact-eligible SKU may select TA-Q-BIN Compact.
    - Multiple units or mixed Compact-only lines conservatively fall back to
      regular Size 60 unless explicit packing evidence confirms Compact fit.
    - Explicit packing evidence may upgrade a package class, but can never
      downgrade below a catalog minimum.
    - The result is planning evidence only and never authorizes production.
    """

    @classmethod
    def select(
        cls,
        lines: Iterable[AmbientPackageLine],
        *,
        packing: AmbientPackingEvidence | None = None,
    ) -> AmbientPackageDecision:
        lines = tuple(lines)
        if not lines:
            raise AmbientPackagingError("cart must contain at least one ambient line")

        reasons: list[str] = []
        catalog_minimum = max(
            (line.minimum_package_class for line in lines),
            key=_PACKAGE_RANK.__getitem__,
        )

        selected = catalog_minimum

        if catalog_minimum == AMBIENT_PACKAGE_COMPACT:
            is_single_unit_cart = len(lines) == 1 and lines[0].quantity == 1
            if not is_single_unit_cart and packing is None:
                selected = AMBIENT_PACKAGE_60
                reasons.append("compact_multi_unit_or_mixed_fit_unconfirmed_fallback_60")

        if packing is not None:
            confirmed = packing.confirmed_package_class
            if _PACKAGE_RANK[confirmed] < _PACKAGE_RANK[catalog_minimum]:
                return AmbientPackageDecision(
                    package_class=None,
                    yamato_service=None,
                    requires_manual_review=True,
                    reasons=("confirmed_package_below_catalog_minimum",),
                )
            selected = confirmed
            if _PACKAGE_RANK[confirmed] > _PACKAGE_RANK[catalog_minimum]:
                reasons.append("packing_evidence_upgraded_package_class")
            elif (
                catalog_minimum == AMBIENT_PACKAGE_COMPACT
                and (len(lines) > 1 or lines[0].quantity > 1)
                and confirmed == AMBIENT_PACKAGE_COMPACT
            ):
                reasons.append("compact_multi_unit_or_mixed_fit_confirmed")

        yamato_service = (
            "takkyubin_compact"
            if selected == AMBIENT_PACKAGE_COMPACT
            else "takkyubin"
        )

        return AmbientPackageDecision(
            package_class=selected,
            yamato_service=yamato_service,
            requires_manual_review=False,
            reasons=tuple(reasons),
        )
