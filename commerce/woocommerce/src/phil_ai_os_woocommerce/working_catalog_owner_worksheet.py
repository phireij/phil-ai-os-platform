from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from .working_catalog_gap_report import build_working_catalog_gap_report


WORKSHEET_COLUMNS = (
    "record_type",
    "parent_sku",
    "sku",
    "product_type",
    "variant_attributes",
    "price_jpy",
    "english_name",
    "japanese_name",
    "english_description",
    "japanese_description",
    "family",
    "form",
    "category_source_label",
    "approved_category_key",
    "media_source_state",
    "primary_media_ref",
    "source_temperature_marks",
    "final_temperature_mode",
    "source_package_rule",
    "shipping_class",
    "pickup_allowed",
    "delivery_allowed",
    "owner_action_requirements",
)


@dataclass(frozen=True)
class WorkingCatalogOwnerWorksheet:
    columns: tuple[str, ...]
    rows: tuple[dict[str, str], ...]
    global_requirements: tuple[str, ...]
    network_call_performed: bool = False
    mutation_authorized: bool = False
    production_publish_authorized: bool = False


def _string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _joined(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    return ";".join(str(value) for value in values if value is not None)


def _product_key(product: Mapping[str, Any]) -> str:
    return str(
        product.get("sku")
        or product.get("parent_reference")
        or product.get("english_name")
        or "unknown"
    )


def _variant_attributes(variant: Mapping[str, Any]) -> str:
    attributes: dict[str, Any] = {}
    supplied = variant.get("attributes")
    if isinstance(supplied, Mapping):
        attributes.update({str(key): value for key, value in supplied.items()})
    if variant.get("size_cm") is not None and "size_cm" not in attributes:
        attributes["size_cm"] = variant.get("size_cm")
    return json.dumps(attributes, ensure_ascii=False, sort_keys=True, separators=(",", ":")) if attributes else ""


def _base_row(product: Mapping[str, Any], requirements: tuple[str, ...]) -> dict[str, str]:
    return {
        "record_type": "",
        "parent_sku": "",
        "sku": "",
        "product_type": _string(product.get("product_type")),
        "variant_attributes": "",
        "price_jpy": "",
        "english_name": _string(product.get("english_name")),
        "japanese_name": _string(product.get("japanese_name")),
        "english_description": _string(product.get("english_description")),
        "japanese_description": _string(product.get("japanese_description")),
        "family": _string(product.get("family")),
        "form": _string(product.get("form")),
        "category_source_label": _string(product.get("category_source_label")),
        "approved_category_key": "",
        "media_source_state": _string(product.get("photo_source_state")),
        "primary_media_ref": "",
        "source_temperature_marks": _joined(product.get("source_temperature_marks")),
        "final_temperature_mode": "",
        "source_package_rule": _string(product.get("source_package_rule")),
        "shipping_class": "",
        "pickup_allowed": _string(product.get("pickup_allowed")),
        "delivery_allowed": _string(product.get("delivery_allowed")),
        "owner_action_requirements": " | ".join(requirements),
    }


def build_working_catalog_owner_worksheet(payload: dict[str, Any]) -> WorkingCatalogOwnerWorksheet:
    """Flatten the source-backed working subset into an owner-editable SKU worksheet.

    The projection preserves parent/variation relationships and source-backed values while
    leaving unresolved owner decisions blank. It is an intake aid only: it performs no
    network calls and cannot grant WooCommerce mutation or publication authority.
    """

    products = payload.get("working_products")
    if not isinstance(products, list):
        raise ValueError("working_products must be an array")

    report = build_working_catalog_gap_report(payload)
    requirements_by_key = {item.key: item.missing for item in report.product_gaps}
    rows: list[dict[str, str]] = []

    for index, raw_product in enumerate(products):
        if not isinstance(raw_product, Mapping):
            raise ValueError(f"working_products[{index}] must be an object")
        product = dict(raw_product)
        product_type = product.get("product_type")
        key = _product_key(product)
        requirements = requirements_by_key.get(key, ())
        base = _base_row(product, requirements)

        if product_type == "simple":
            sku = _string(product.get("sku"))
            if not sku:
                raise ValueError(f"simple product {key} requires sku")
            row = dict(base)
            row.update(
                record_type="simple_product",
                sku=sku,
                price_jpy=_string(product.get("price_jpy")),
            )
            rows.append(row)
            continue

        if product_type == "variable":
            parent_sku = _string(product.get("parent_reference"))
            if not parent_sku:
                raise ValueError(f"variable product {key} requires parent_reference")
            parent_row = dict(base)
            parent_row.update(record_type="variable_parent", sku=parent_sku)
            rows.append(parent_row)

            variants = product.get("variants")
            if not isinstance(variants, list):
                raise ValueError(f"variable product {key} variants must be an array")
            for variant_index, raw_variant in enumerate(variants):
                if not isinstance(raw_variant, Mapping):
                    raise ValueError(
                        f"variable product {key} variants[{variant_index}] must be an object"
                    )
                variant_sku = _string(raw_variant.get("sku"))
                if not variant_sku:
                    raise ValueError(
                        f"variable product {key} variants[{variant_index}] requires sku"
                    )
                variant_row = {column: "" for column in WORKSHEET_COLUMNS}
                variant_row.update(
                    record_type="variation",
                    parent_sku=parent_sku,
                    sku=variant_sku,
                    product_type="variable",
                    variant_attributes=_variant_attributes(raw_variant),
                    price_jpy=_string(raw_variant.get("price_jpy")),
                    owner_action_requirements=" | ".join(requirements),
                )
                rows.append(variant_row)
            continue

        raise ValueError(f"working product {key} has unsupported product_type: {product_type!r}")

    return WorkingCatalogOwnerWorksheet(
        columns=WORKSHEET_COLUMNS,
        rows=tuple(rows),
        global_requirements=report.global_gaps,
    )
