from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from .models import CategoryRecord, ContractValidationError, MediaRecord, ProductRecord


PENDING = "pending"
TAXABLE_STATUSES = {PENDING, "taxable", "exempt"}
INVOICE_STATUSES = {PENDING, "registered", "not_registered"}
YES_NO_PENDING = {PENDING, "yes", "no"}
COD_TREATMENTS = {PENDING, "not_offered", "standard_rate", "reduced_rate", "other_confirmed"}
IMPLEMENTATION_ROUTES = {PENDING, "tax_tables_candidate", "tax_disabled_candidate"}
PRODUCT_TAX_CLASSES = {PENDING, "reduced_rate_food", "standard_rate", "exempt"}
UNAPPROVED_SOURCE_MARKERS = ("fixture", "legacy", "historical", "test", "builder")
APPROVED_CATALOG_PLACEHOLDERS = {"tbd", "pending", "to be determined", "未定", "確認中"}


@dataclass(frozen=True)
class CatalogTaxReadiness:
    catalog_ready: bool
    tax_decision_ready: bool
    ready_for_preproduction_configuration: bool
    blockers: tuple[str, ...]
    mutation_authorized: bool = False
    production_publish_authorized: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "catalog_ready": self.catalog_ready,
            "tax_decision_ready": self.tax_decision_ready,
            "ready_for_preproduction_configuration": self.ready_for_preproduction_configuration,
            "blockers": list(self.blockers),
            "mutation_authorized": self.mutation_authorized,
            "production_publish_authorized": self.production_publish_authorized,
        }


def _require_enum(value: Any, allowed: set[str], field: str) -> str:
    normalized = str(value or "")
    if normalized not in allowed:
        raise ContractValidationError(f"unsupported {field}: {normalized}")
    return normalized


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _source_is_unapproved(value: str) -> bool:
    normalized = value.strip().lower()
    return not normalized or any(marker in normalized for marker in UNAPPROVED_SOURCE_MARKERS)


def _is_placeholder(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in APPROVED_CATALOG_PLACEHOLDERS


def _has_timezone_iso_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _category_integrity_blockers(categories: list[CategoryRecord]) -> list[str]:
    blockers: list[str] = []
    by_key = {category.key: category for category in categories}

    for category in categories:
        if category.parent_key and category.parent_key not in by_key:
            blockers.append(
                f"category {category.key} has unknown parent key: {category.parent_key}"
            )

    for category in categories:
        seen: set[str] = set()
        current = category
        while current.parent_key and current.parent_key in by_key:
            if current.key in seen or current.parent_key in seen:
                blockers.append(f"category hierarchy cycle detected at: {category.key}")
                break
            seen.add(current.key)
            current = by_key[current.parent_key]

    return blockers


def _catalog_handoff_contract_blockers(payload: Mapping[str, Any]) -> list[str]:
    """Fail closed when the owner handoff weakens launch scope or source boundaries."""

    blockers: list[str] = []
    scope = payload.get("catalog_scope")
    if not isinstance(scope, Mapping):
        blockers.append("catalog scope contract is missing")
    else:
        if scope.get("scope_type") != "initial_launch_subset":
            blockers.append("catalog scope type must remain initial_launch_subset")
        if scope.get("full_product_range_required_for_sprint3_closure") is not False:
            blockers.append(
                "catalog scope must not require the full product range for Sprint 3 closure"
            )
        if scope.get("additional_products_may_be_added_after_sprint3") is not True:
            blockers.append("catalog scope must allow additional products after Sprint 3")
        if scope.get("scope_complete_for_intended_initial_launch") is not True:
            blockers.append("catalog scope is not complete for the intended initial launch")

    source = payload.get("source_contract")
    if not isinstance(source, Mapping):
        blockers.append("catalog source contract is missing")
        return blockers

    required_true = (
        "owner_source_required",
        "owner_approval_required",
        "source_updated_at_required",
        "bilingual_en_ja_required",
        "verified_media_source_required",
    )
    for field in required_true:
        if source.get(field) is not True:
            blockers.append(f"catalog source contract must keep {field}=true")

    expected_values = {
        "currency": "JPY",
        "intake_product_status": "draft",
        "intake_product_visibility": "hidden",
    }
    for field, expected in expected_values.items():
        if source.get(field) != expected:
            blockers.append(f"catalog source contract must keep {field}={expected}")

    if source.get("production_write_authority_granted_by_handoff") is not False:
        blockers.append(
            "catalog source contract must keep production_write_authority_granted_by_handoff=false"
        )

    return blockers


def evaluate_catalog_tax_readiness(payload: Mapping[str, Any]) -> CatalogTaxReadiness:
    """Evaluate a catalog/tax intake package without granting mutation authority.

    This gate deliberately separates decision readiness from WooCommerce activation.
    Even a GREEN result is evidence for a later pre-production change proposal only.
    """

    if payload.get("schema_version") != "1.0":
        raise ContractValidationError("catalog intake schema_version must be 1.0")
    if payload.get("environment") != "pre-production":
        raise ContractValidationError("catalog intake environment must be pre-production")
    if payload.get("mutation_authorized") is not False:
        raise ContractValidationError("catalog intake must set mutation_authorized=false")
    if payload.get("production_publish_authorized") is not False:
        raise ContractValidationError(
            "catalog intake must set production_publish_authorized=false"
        )

    package_state = _require_enum(
        payload.get("package_state"), {"draft", "approved"}, "package_state"
    )
    catalog_approved = payload.get("catalog_approved")
    if not isinstance(catalog_approved, bool):
        raise ContractValidationError("catalog_approved must be boolean")

    tax = payload.get("tax_decision")
    if not isinstance(tax, Mapping):
        raise ContractValidationError("tax_decision must be an object")

    taxable_status = _require_enum(
        tax.get("taxable_business_status"), TAXABLE_STATUSES, "taxable_business_status"
    )
    invoice_status = _require_enum(
        tax.get("qualified_invoice_status"), INVOICE_STATUSES, "qualified_invoice_status"
    )
    shipping_separate = _require_enum(
        tax.get("yamato_shipping_separately_charged"),
        YES_NO_PENDING,
        "yamato_shipping_separately_charged",
    )
    cod_fee_treatment = _require_enum(
        tax.get("cod_fee_treatment"),
        COD_TREATMENTS,
        "cod_fee_treatment",
    )
    route = _require_enum(
        tax.get("implementation_route"), IMPLEMENTATION_ROUTES, "implementation_route"
    )
    exempt_disabled_route = taxable_status == "exempt" and route == "tax_disabled_candidate"

    categories_raw = payload.get("categories", [])
    media_raw = payload.get("media", [])
    products_raw = payload.get("products", [])
    if not all(isinstance(value, list) for value in (categories_raw, media_raw, products_raw)):
        raise ContractValidationError("categories, media, and products must be arrays")

    categories = [CategoryRecord.from_mapping(value) for value in categories_raw]
    media = [MediaRecord.from_mapping(value) for value in media_raw]
    products = [ProductRecord.from_mapping(value) for value in products_raw]

    blockers: list[str] = []
    blockers.extend(_catalog_handoff_contract_blockers(payload))
    pending_product_tax_classes: list[str] = []
    category_keys = [value.key for value in categories]
    media_keys = [value.key for value in media]
    product_skus = [value.sku for value in products]

    for label, values in (
        ("category key", category_keys),
        ("media key", media_keys),
        ("product SKU", product_skus),
    ):
        for duplicate in sorted(_duplicates(values)):
            blockers.append(f"duplicate {label}: {duplicate}")

    blockers.extend(_category_integrity_blockers(categories))

    category_key_set = set(category_keys)
    media_key_set = set(media_keys)
    media_by_key = {value.key: value for value in media}

    if package_state != "approved":
        blockers.append("catalog package_state is not approved")
    if not catalog_approved:
        blockers.append("catalog approval is pending")
    catalog_approval_ref = str(payload.get("catalog_approval_ref") or "").strip()
    if not catalog_approval_ref:
        blockers.append("catalog approval reference is missing")
    elif _is_placeholder(catalog_approval_ref):
        blockers.append("catalog approval reference contains a placeholder")
    if not products:
        blockers.append("approved catalog contains no products")

    for category in categories:
        for field, value in (
            ("English name", category.name.en),
            ("Japanese name", category.name.ja),
            ("English slug", category.slug.en),
            ("Japanese slug", category.slug.ja),
        ):
            if _is_placeholder(value):
                blockers.append(f"category {category.key} {field} contains a placeholder")

    for index, (raw, product) in enumerate(zip(products_raw, products), start=1):
        prefix = f"product[{index}] {product.sku}"
        if raw.get("approval_state") != "approved":
            blockers.append(f"{prefix} approval is pending")
        if product.status != "draft":
            blockers.append(f"{prefix} must remain draft during intake")
        if product.visibility != "hidden":
            blockers.append(f"{prefix} must remain hidden during intake")
        if product.currency != "JPY":
            blockers.append(f"{prefix} currency must be JPY")
        if raw.get("price_includes_tax") is not True:
            blockers.append(f"{prefix} tax-inclusive price confirmation is pending")

        for field, value in (
            ("English name", product.name.en),
            ("Japanese name", product.name.ja),
            ("English description", product.description.en),
            ("Japanese description", product.description.ja),
            ("English slug", product.slug.en),
            ("Japanese slug", product.slug.ja),
            ("source provenance", product.source),
        ):
            if _is_placeholder(value):
                blockers.append(f"{prefix} {field} contains a placeholder")

        if _source_is_unapproved(product.source):
            blockers.append(f"{prefix} source provenance is not approved")
        if not _has_timezone_iso_timestamp(product.source_updated_at):
            blockers.append(f"{prefix} source_updated_at must be a timezone-aware ISO timestamp")

        tax_class = _require_enum(
            raw.get("tax_class_candidate"), PRODUCT_TAX_CLASSES, "product tax_class_candidate"
        )
        if tax_class == PENDING:
            pending_product_tax_classes.append(prefix)

        missing_categories = sorted(set(product.category_keys) - category_key_set)
        missing_media = sorted(set(product.media_keys) - media_key_set)
        if missing_categories:
            blockers.append(f"{prefix} has unknown category keys: {', '.join(missing_categories)}")
        if missing_media:
            blockers.append(f"{prefix} has unknown media keys: {', '.join(missing_media)}")
        if not product.category_keys:
            blockers.append(f"{prefix} requires at least one approved category")
        if not product.media_keys:
            blockers.append(f"{prefix} requires at least one approved media item")
        else:
            primary_count = sum(
                1
                for key in product.media_keys
                if media_by_key.get(key) is not None and media_by_key[key].role == "primary"
            )
            if primary_count != 1:
                blockers.append(
                    f"{prefix} requires exactly one primary media item; found {primary_count}"
                )

    for value in media:
        for field, content in (
            ("English alt text", value.alt.en),
            ("Japanese alt text", value.alt.ja),
            ("source reference", value.source_ref),
        ):
            if _is_placeholder(content):
                blockers.append(f"media {value.key} {field} contains a placeholder")
        source = value.source_ref.strip().lower()
        if source.startswith("fixture://") or any(
            marker in source for marker in ("legacy://", "historical://", "test://", "builder://")
        ):
            blockers.append(f"media {value.key} uses an unapproved source")

    pending_tax_fields = [
        name
        for name, value in (
            ("taxable business status", taxable_status),
            ("qualified invoice status", invoice_status),
            ("tax implementation route", route),
        )
        if value == PENDING
    ]
    if not exempt_disabled_route:
        pending_tax_fields.extend(
            name
            for name, value in (
                ("Yamato separate-charge treatment", shipping_separate),
                ("COD fee treatment", cod_fee_treatment),
            )
            if value == PENDING
        )
        blockers.extend(f"{prefix} tax class is pending" for prefix in pending_product_tax_classes)
    blockers.extend(f"{name} is pending" for name in pending_tax_fields)

    if not str(tax.get("decision_evidence_ref") or "").strip():
        blockers.append("tax decision evidence reference is missing")
    if taxable_status == "taxable" and route not in {PENDING, "tax_tables_candidate"}:
        blockers.append("taxable status requires the tax_tables_candidate route")
    if taxable_status == "exempt" and route not in {PENDING, "tax_disabled_candidate"}:
        blockers.append("exempt status requires the tax_disabled_candidate route")
    if invoice_status == "registered" and not str(
        tax.get("qualified_invoice_registration_number") or ""
    ).strip():
        blockers.append("qualified invoice registration number is missing")

    catalog_blocker_prefixes = (
        "catalog ",
        "approved catalog",
        "duplicate ",
        "category ",
        "product[",
        "media ",
    )
    catalog_ready = not any(
        blocker.startswith(catalog_blocker_prefixes) for blocker in blockers
    )
    tax_blocker_markers = (
        "taxable business",
        "qualified invoice",
        "Yamato",
        "COD",
        "tax implementation",
        "tax decision",
        "taxable status",
        "exempt status",
    )
    tax_decision_ready = not any(
        blocker.startswith(tax_blocker_markers) for blocker in blockers
    )

    return CatalogTaxReadiness(
        catalog_ready=catalog_ready,
        tax_decision_ready=tax_decision_ready,
        ready_for_preproduction_configuration=catalog_ready and tax_decision_ready,
        blockers=tuple(blockers),
    )
