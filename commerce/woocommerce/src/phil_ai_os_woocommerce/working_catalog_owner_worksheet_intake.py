from __future__ import annotations

import csv
from dataclasses import dataclass
import io
from typing import Any, Mapping, Sequence

from .working_catalog_owner_worksheet import (
    WORKSHEET_COLUMNS,
    build_working_catalog_owner_worksheet,
)


STRUCTURAL_FIELDS = (
    "record_type",
    "parent_sku",
    "sku",
    "product_type",
    "variant_attributes",
)

SOURCE_BACKED_FIELDS = (
    "price_jpy",
    "english_name",
    "english_description",
    "family",
    "form",
    "category_source_label",
    "media_source_state",
    "source_temperature_marks",
    "source_package_rule",
    "pickup_allowed",
    "delivery_allowed",
)

OWNER_INPUT_FIELDS = (
    "japanese_name",
    "japanese_description",
    "approved_category_key",
    "primary_media_ref",
    "final_temperature_mode",
    "shipping_class",
)

DERIVED_FIELDS = ("owner_action_requirements",)

_ALLOWED_TEMPERATURE_MODES = {"", "ambient", "frozen", "chilled"}
_ALLOWED_SHIPPING_CLASSES = {
    "",
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


@dataclass(frozen=True)
class WorksheetProposedChange:
    sku: str
    record_type: str
    field: str
    previous_value: str
    proposed_value: str
    classification: str
    evidence_required: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "sku": self.sku,
            "record_type": self.record_type,
            "field": self.field,
            "previous_value": self.previous_value,
            "proposed_value": self.proposed_value,
            "classification": self.classification,
            "evidence_required": self.evidence_required,
        }


@dataclass(frozen=True)
class WorkingCatalogOwnerWorksheetIntakeReview:
    structurally_valid: bool
    ready_for_owner_fact_review: bool
    blockers: tuple[str, ...]
    proposed_changes: tuple[WorksheetProposedChange, ...]
    unchanged_row_count: int
    row_count: int
    network_call_performed: bool = False
    mutation_authorized: bool = False
    production_publish_authorized: bool = False
    automatic_apply_authorized: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "structurally_valid": self.structurally_valid,
            "ready_for_owner_fact_review": self.ready_for_owner_fact_review,
            "blockers": list(self.blockers),
            "proposed_changes": [change.as_dict() for change in self.proposed_changes],
            "unchanged_row_count": self.unchanged_row_count,
            "row_count": self.row_count,
            "network_call_performed": self.network_call_performed,
            "mutation_authorized": self.mutation_authorized,
            "production_publish_authorized": self.production_publish_authorized,
            "automatic_apply_authorized": self.automatic_apply_authorized,
        }


def parse_owner_worksheet_csv(text: str) -> tuple[dict[str, str], ...]:
    """Parse an owner worksheet CSV while preserving the exact worksheet contract."""

    if not isinstance(text, str):
        raise ValueError("worksheet CSV must be text")
    normalized = text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(normalized))
    if reader.fieldnames is None:
        raise ValueError("worksheet CSV header is missing")
    if tuple(reader.fieldnames) != WORKSHEET_COLUMNS:
        raise ValueError("worksheet CSV columns do not match the canonical owner worksheet")

    rows: list[dict[str, str]] = []
    for index, raw in enumerate(reader, start=2):
        if None in raw:
            raise ValueError(f"worksheet CSV row {index} contains extra unnamed columns")
        row = {column: str(raw.get(column) or "").strip() for column in WORKSHEET_COLUMNS}
        if not any(row.values()):
            continue
        rows.append(row)
    return tuple(rows)


def _validate_owner_value(field: str, value: str) -> str | None:
    if field == "final_temperature_mode" and value not in _ALLOWED_TEMPERATURE_MODES:
        return f"unsupported final_temperature_mode: {value}"
    if field == "shipping_class" and value not in _ALLOWED_SHIPPING_CLASSES:
        return f"unsupported shipping_class: {value}"
    return None


def _index_rows(rows: Sequence[Mapping[str, str]]) -> tuple[dict[str, Mapping[str, str]], list[str]]:
    by_sku: dict[str, Mapping[str, str]] = {}
    blockers: list[str] = []
    for position, row in enumerate(rows, start=1):
        sku = str(row.get("sku") or "").strip()
        if not sku:
            blockers.append(f"worksheet row {position} is missing sku")
            continue
        if sku in by_sku:
            blockers.append(f"duplicate worksheet SKU: {sku}")
            continue
        by_sku[sku] = row
    return by_sku, blockers


def review_owner_worksheet_intake(
    source_payload: dict[str, Any],
    worksheet_rows: Sequence[Mapping[str, str]],
) -> WorkingCatalogOwnerWorksheetIntakeReview:
    """Review an edited owner worksheet without applying it to the canonical catalog.

    Structural identity must remain identical to the source-backed worksheet. Owner-input
    cells are collected as proposals. Changes to source-backed facts are also collected, but
    explicitly marked as requiring fresh owner/source evidence. Nothing is automatically
    applied and no production authority is granted.
    """

    expected = build_working_catalog_owner_worksheet(source_payload)
    expected_by_sku = {row["sku"]: row for row in expected.rows}
    actual_by_sku, blockers = _index_rows(worksheet_rows)

    missing = sorted(set(expected_by_sku) - set(actual_by_sku))
    extra = sorted(set(actual_by_sku) - set(expected_by_sku))
    blockers.extend(f"worksheet is missing expected SKU: {sku}" for sku in missing)
    blockers.extend(f"worksheet contains unexpected SKU: {sku}" for sku in extra)

    changes: list[WorksheetProposedChange] = []
    unchanged_rows = 0

    for sku in sorted(set(expected_by_sku) & set(actual_by_sku)):
        expected_row = expected_by_sku[sku]
        actual_row = actual_by_sku[sku]
        row_changed = False

        for field in STRUCTURAL_FIELDS:
            previous = expected_row[field]
            proposed = str(actual_row.get(field) or "").strip()
            if proposed != previous:
                blockers.append(
                    f"{sku} structural field {field} must remain {previous!r}; received {proposed!r}"
                )
                row_changed = True

        for field in DERIVED_FIELDS:
            previous = expected_row[field]
            proposed = str(actual_row.get(field) or "").strip()
            if proposed != previous:
                blockers.append(f"{sku} derived field {field} must not be edited")
                row_changed = True

        record_type = expected_row["record_type"]
        for field in OWNER_INPUT_FIELDS:
            previous = expected_row[field]
            proposed = str(actual_row.get(field) or "").strip()
            if proposed == previous:
                continue
            row_changed = True
            if record_type == "variation":
                blockers.append(
                    f"{sku} variation row cannot carry product-level owner field {field}; edit the parent row"
                )
                continue
            validation_error = _validate_owner_value(field, proposed)
            if validation_error:
                blockers.append(f"{sku} {validation_error}")
                continue
            changes.append(
                WorksheetProposedChange(
                    sku=sku,
                    record_type=record_type,
                    field=field,
                    previous_value=previous,
                    proposed_value=proposed,
                    classification="owner_input",
                    evidence_required=False,
                )
            )

        for field in SOURCE_BACKED_FIELDS:
            previous = expected_row[field]
            proposed = str(actual_row.get(field) or "").strip()
            if proposed == previous:
                continue
            row_changed = True
            changes.append(
                WorksheetProposedChange(
                    sku=sku,
                    record_type=record_type,
                    field=field,
                    previous_value=previous,
                    proposed_value=proposed,
                    classification="source_backed_change_requires_evidence",
                    evidence_required=True,
                )
            )

        if not row_changed:
            unchanged_rows += 1

    blockers = list(dict.fromkeys(blockers))
    structurally_valid = not blockers
    return WorkingCatalogOwnerWorksheetIntakeReview(
        structurally_valid=structurally_valid,
        ready_for_owner_fact_review=structurally_valid,
        blockers=tuple(blockers),
        proposed_changes=tuple(changes),
        unchanged_row_count=unchanged_rows,
        row_count=len(worksheet_rows),
    )
