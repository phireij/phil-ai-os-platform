from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


class ContractValidationError(ValueError):
    pass


def _validate_price(value: str, field_name: str) -> None:
    try:
        price = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be a decimal string") from exc
    if price < 0:
        raise ContractValidationError(f"{field_name} must be non-negative")


@dataclass(frozen=True)
class LocalizedText:
    en: str
    ja: str

    def __post_init__(self) -> None:
        if not self.en.strip() or not self.ja.strip():
            raise ContractValidationError("both English and Japanese values are required")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LocalizedText":
        return cls(en=str(value.get("en", "")), ja=str(value.get("ja", "")))

    def as_dict(self) -> dict[str, str]:
        return {"en": self.en, "ja": self.ja}


@dataclass(frozen=True)
class CategoryRecord:
    key: str
    name: LocalizedText
    slug: LocalizedText
    parent_key: str | None = None

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ContractValidationError("category key is required")
        if self.parent_key == self.key:
            raise ContractValidationError("category cannot be its own parent")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CategoryRecord":
        return cls(
            key=str(value.get("key", "")),
            name=LocalizedText.from_mapping(value.get("name", {})),
            slug=LocalizedText.from_mapping(value.get("slug", {})),
            parent_key=value.get("parent_key"),
        )

    def to_wc_payload(self, locale: str = "en") -> dict[str, Any]:
        if locale not in {"en", "ja"}:
            raise ContractValidationError(f"unsupported locale: {locale}")
        return {
            "name": self.name.en if locale == "en" else self.name.ja,
            "slug": self.slug.en if locale == "en" else self.slug.ja,
        }


@dataclass(frozen=True)
class MediaRecord:
    key: str
    source_ref: str
    alt: LocalizedText
    role: str = "gallery"
    position: int = 0

    def __post_init__(self) -> None:
        if self.role not in {"primary", "gallery"}:
            raise ContractValidationError("media role must be primary or gallery")
        if self.position < 0:
            raise ContractValidationError("media position must be non-negative")
        if not self.key.strip() or not self.source_ref.strip():
            raise ContractValidationError("media key and source_ref are required")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MediaRecord":
        return cls(
            key=str(value.get("key", "")),
            source_ref=str(value.get("source_ref", "")),
            alt=LocalizedText.from_mapping(value.get("alt", {})),
            role=str(value.get("role", "gallery")),
            position=int(value.get("position", 0)),
        )

    def upload_manifest(self, locale: str = "en") -> dict[str, Any]:
        if locale not in {"en", "ja"}:
            raise ContractValidationError(f"unsupported locale: {locale}")
        return {
            "key": self.key,
            "source_ref": self.source_ref,
            "alt": self.alt.en if locale == "en" else self.alt.ja,
            "role": self.role,
            "position": self.position,
        }


@dataclass(frozen=True)
class InventoryRecord:
    sku: str
    quantity: int
    stock_status: str
    source_of_truth: str
    revision: int

    def __post_init__(self) -> None:
        if not self.sku.strip():
            raise ContractValidationError("inventory sku is required")
        if self.quantity < 0:
            raise ContractValidationError("inventory quantity must be non-negative")
        if self.stock_status not in {"instock", "outofstock", "onbackorder"}:
            raise ContractValidationError("unsupported stock_status")
        if not self.source_of_truth.strip():
            raise ContractValidationError("inventory source_of_truth must be explicit")
        if self.revision < 0:
            raise ContractValidationError("inventory revision must be non-negative")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "InventoryRecord":
        return cls(
            sku=str(value.get("sku", "")),
            quantity=int(value.get("quantity", -1)),
            stock_status=str(value.get("stock_status", "")),
            source_of_truth=str(value.get("source_of_truth", "")),
            revision=int(value.get("revision", -1)),
        )

    def to_wc_payload(self) -> dict[str, Any]:
        return {
            "manage_stock": True,
            "stock_quantity": self.quantity,
            "stock_status": self.stock_status,
        }


@dataclass(frozen=True)
class FulfillmentProfile:
    shipping_class: str | None
    temperature_modes: tuple[str, ...]
    pickup_allowed: bool
    delivery_allowed: bool
    requires_order_approval: bool = True

    def __post_init__(self) -> None:
        allowed_classes = {
            "ambient-compact",
            "ambient-60",
            "ambient-80",
            "ambient-100",
            "ambient-120",
            "cool-60",
            "cool-80",
            "cool-100",
            "cool-120",
        }
        allowed_temperatures = {"ambient", "frozen", "chilled"}
        if self.shipping_class is not None and self.shipping_class not in allowed_classes:
            raise ContractValidationError("unsupported WooCommerce shipping class")
        if len(set(self.temperature_modes)) != len(self.temperature_modes):
            raise ContractValidationError("temperature_modes must be unique")
        if not set(self.temperature_modes).issubset(allowed_temperatures):
            raise ContractValidationError("unsupported fulfillment temperature mode")
        if not self.pickup_allowed and not self.delivery_allowed:
            raise ContractValidationError("at least one fulfillment channel must be allowed")
        if self.delivery_allowed and self.shipping_class is None:
            raise ContractValidationError("delivery products require an explicit shipping class")
        if self.delivery_allowed and not self.temperature_modes:
            raise ContractValidationError("delivery products require at least one temperature mode")
        if not self.delivery_allowed and (self.shipping_class is not None or self.temperature_modes):
            raise ContractValidationError(
                "pickup-only products cannot declare delivery shipping or temperature settings"
            )
        if not self.requires_order_approval:
            raise ContractValidationError(
                "WooCommerce pre-production products must retain approval-before-payment"
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FulfillmentProfile":
        return cls(
            shipping_class=value.get("shipping_class"),
            temperature_modes=tuple(str(v) for v in value.get("temperature_modes", [])),
            pickup_allowed=bool(value.get("pickup_allowed", False)),
            delivery_allowed=bool(value.get("delivery_allowed", False)),
            requires_order_approval=bool(value.get("requires_order_approval", False)),
        )

    def to_wc_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "meta_data": [
                {"key": "_philaios_temperature_modes", "value": list(self.temperature_modes)},
                {"key": "_philaios_pickup_allowed", "value": self.pickup_allowed},
                {"key": "_philaios_delivery_allowed", "value": self.delivery_allowed},
                {"key": "_philaios_requires_order_approval", "value": self.requires_order_approval},
            ]
        }
        if self.shipping_class is not None:
            payload["shipping_class"] = self.shipping_class
        return payload


@dataclass(frozen=True)
class ProductVariationRecord:
    sku: str
    regular_price: str
    attributes: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not self.sku.strip():
            raise ContractValidationError("variation sku is required")
        _validate_price(self.regular_price, "variation regular_price")
        if not self.attributes:
            raise ContractValidationError("variable product variations require at least one attribute")
        names: list[str] = []
        for name, option in self.attributes:
            if not name.strip() or not option.strip():
                raise ContractValidationError("variation attribute names and options are required")
            names.append(name)
        if len(set(names)) != len(names):
            raise ContractValidationError("variation attribute names must be unique")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProductVariationRecord":
        raw_attributes = value.get("attributes", {})
        if not isinstance(raw_attributes, Mapping):
            raise ContractValidationError("variation attributes must be an object")
        attributes = tuple(
            sorted((str(name).strip(), str(option).strip()) for name, option in raw_attributes.items())
        )
        return cls(
            sku=str(value.get("sku", "")),
            regular_price=str(value.get("regular_price", "")),
            attributes=attributes,
        )

    def to_wc_payload(self) -> dict[str, Any]:
        return {
            "sku": self.sku,
            "regular_price": self.regular_price,
            "attributes": [
                {"name": name, "option": option}
                for name, option in self.attributes
            ],
        }


@dataclass(frozen=True)
class ProductRecord:
    sku: str
    name: LocalizedText
    description: LocalizedText
    slug: LocalizedText
    regular_price: str | None
    currency: str
    fulfillment: FulfillmentProfile
    product_type: str = "simple"
    variations: tuple[ProductVariationRecord, ...] = field(default_factory=tuple)
    status: str = "draft"
    visibility: str = "visible"
    category_keys: tuple[str, ...] = field(default_factory=tuple)
    media_keys: tuple[str, ...] = field(default_factory=tuple)
    source: str = "fixture"
    source_updated_at: str | None = None

    def __post_init__(self) -> None:
        if not self.sku.strip():
            raise ContractValidationError("product sku is required")
        if self.product_type not in {"simple", "variable"}:
            raise ContractValidationError("product_type must be simple or variable")
        if self.product_type == "simple":
            if self.regular_price is None or not self.regular_price.strip():
                raise ContractValidationError("simple products require regular_price")
            _validate_price(self.regular_price, "regular_price")
            if self.variations:
                raise ContractValidationError("simple products cannot declare variations")
        else:
            if self.regular_price not in {None, ""}:
                raise ContractValidationError(
                    "variable product parent regular_price must be null; variation prices are authoritative"
                )
            if not self.variations:
                raise ContractValidationError("variable products require at least one variation")
            variation_skus = [variation.sku for variation in self.variations]
            if len(set(variation_skus)) != len(variation_skus):
                raise ContractValidationError("variation SKUs must be unique within a product")
            if self.sku in variation_skus:
                raise ContractValidationError("parent SKU cannot be reused by a variation")
            combinations = [variation.attributes for variation in self.variations]
            if len(set(combinations)) != len(combinations):
                raise ContractValidationError("variation attribute combinations must be unique")
        if self.status not in {"draft", "publish", "private"}:
            raise ContractValidationError("unsupported product status")
        if self.visibility not in {"visible", "catalog", "search", "hidden"}:
            raise ContractValidationError("unsupported product visibility")
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ContractValidationError("currency must be a 3-letter code")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProductRecord":
        raw_variations = value.get("variations", [])
        if not isinstance(raw_variations, list):
            raise ContractValidationError("product variations must be an array")
        raw_price = value.get("regular_price")
        return cls(
            sku=str(value.get("sku", "")),
            name=LocalizedText.from_mapping(value.get("name", {})),
            description=LocalizedText.from_mapping(value.get("description", {})),
            slug=LocalizedText.from_mapping(value.get("slug", {})),
            regular_price=None if raw_price is None else str(raw_price),
            currency=str(value.get("currency", "")),
            fulfillment=FulfillmentProfile.from_mapping(value.get("fulfillment", {})),
            product_type=str(value.get("product_type", "simple")),
            variations=tuple(ProductVariationRecord.from_mapping(v) for v in raw_variations),
            status=str(value.get("status", "draft")),
            visibility=str(value.get("visibility", "visible")),
            category_keys=tuple(str(v) for v in value.get("category_keys", [])),
            media_keys=tuple(str(v) for v in value.get("media_keys", [])),
            source=str(value.get("source", "fixture")),
            source_updated_at=value.get("source_updated_at"),
        )

    def localized_name(self, locale: str) -> str:
        if locale == "ja":
            return self.name.ja
        if locale == "en":
            return self.name.en
        raise ContractValidationError(f"unsupported locale: {locale}")

    def all_skus(self) -> tuple[str, ...]:
        return (self.sku, *(variation.sku for variation in self.variations))

    def _variable_attribute_payload(self) -> list[dict[str, Any]]:
        options_by_name: dict[str, set[str]] = {}
        for variation in self.variations:
            for name, option in variation.attributes:
                options_by_name.setdefault(name, set()).add(option)
        return [
            {
                "name": name,
                "visible": True,
                "variation": True,
                "options": sorted(options),
            }
            for name, options in sorted(options_by_name.items())
        ]

    def variation_payloads(self) -> tuple[dict[str, Any], ...]:
        return tuple(variation.to_wc_payload() for variation in self.variations)

    def to_wc_payload(self, locale: str = "en") -> dict[str, Any]:
        """Return the bounded WooCommerce parent-product projection.

        WooCommerce itself does not define Phil AI OS bilingual storage. Sprint 3
        therefore keeps the bilingual canonical contract outside WooCommerce and
        produces a deterministic locale-specific projection for an eventual
        activated transport. Variable-product variations are projected separately
        through ``variation_payloads`` and remain non-authorizing until a dedicated
        variation reconciliation path is approved.
        """
        if locale not in {"en", "ja"}:
            raise ContractValidationError(f"unsupported locale: {locale}")
        name = self.name.en if locale == "en" else self.name.ja
        description = self.description.en if locale == "en" else self.description.ja
        slug = self.slug.en if locale == "en" else self.slug.ja
        payload: dict[str, Any] = {
            "sku": self.sku,
            "name": name,
            "description": description,
            "slug": slug,
            "status": self.status,
            "catalog_visibility": self.visibility,
        }
        if self.product_type == "simple":
            payload["regular_price"] = self.regular_price
        else:
            payload["type"] = "variable"
            payload["attributes"] = self._variable_attribute_payload()
        payload.update(self.fulfillment.to_wc_payload())
        return payload
