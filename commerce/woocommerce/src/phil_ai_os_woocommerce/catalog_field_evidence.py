from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ALLOWED_EVIDENCE_TYPES = {
    "owner_visual_confirmation",
    "owner_direct_confirmation",
}


@dataclass(frozen=True)
class FieldEvidenceResult:
    valid: bool
    blockers: tuple[str, ...]


def evaluate_field_evidence(payload: dict[str, Any]) -> FieldEvidenceResult:
    """Validate supplemental owner evidence without granting catalog readiness.

    Supplemental evidence is allowed only to preserve explicitly owner-confirmed facts
    when document text extraction is incomplete or contains a confirmed typo. It must
    remain field-specific and cannot infer unrelated catalog values.
    """

    blockers: list[str] = []
    snapshot = payload.get("source_snapshot") or {}
    evidence = snapshot.get("field_evidence") or []

    if not isinstance(evidence, list):
        return FieldEvidenceResult(False, ("source_snapshot.field_evidence must be an array",))

    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(evidence, start=1):
        prefix = f"field_evidence[{index}]"
        if not isinstance(item, dict):
            blockers.append(f"{prefix} must be an object")
            continue

        product_key = str(item.get("product_key") or "").strip()
        field = str(item.get("field") or "").strip()
        evidence_type = str(item.get("evidence_type") or "").strip()
        observed_at = str(item.get("observed_at") or "").strip()
        note = str(item.get("note") or "").strip()

        if not product_key:
            blockers.append(f"{prefix} product_key is missing")
        if not field:
            blockers.append(f"{prefix} field is missing")
        if evidence_type not in ALLOWED_EVIDENCE_TYPES:
            blockers.append(f"{prefix} evidence_type is unsupported: {evidence_type}")
        if "value" not in item:
            blockers.append(f"{prefix} value is missing")
        if not observed_at:
            blockers.append(f"{prefix} observed_at is missing")
        if not note:
            blockers.append(f"{prefix} note is missing")

        key = (product_key, field)
        if product_key and field:
            if key in seen:
                blockers.append(f"duplicate supplemental evidence for {product_key}.{field}")
            seen.add(key)

    products = payload.get("working_products") or []
    ens = next((p for p in products if p.get("sku") == "RCD-BRD-ENS-1"), None)
    if ens is not None and ens.get("price_jpy") == 300:
        match = next(
            (
                item
                for item in evidence
                if isinstance(item, dict)
                and item.get("product_key") == "RCD-BRD-ENS-1"
                and item.get("field") == "price_jpy"
                and item.get("value") == 300
                and item.get("evidence_type") == "owner_visual_confirmation"
            ),
            None,
        )
        if match is None:
            blockers.append("Cheezy Ensaymada ¥300 requires structured owner visual evidence")

    moist = next((p for p in products if p.get("parent_reference") == "RCD-MCH-RD"), None)
    if moist is not None:
        v21 = next((v for v in moist.get("variants") or [] if v.get("sku") == "RCD-MCH-RD-21"), None)
        if v21 is not None and v21.get("source_typo") == "RCS-MCH-RD-21":
            match = next(
                (
                    item
                    for item in evidence
                    if isinstance(item, dict)
                    and item.get("product_key") == "RCD-MCH-RD-21"
                    and item.get("field") == "sku"
                    and item.get("value") == "RCD-MCH-RD-21"
                    and item.get("evidence_type") == "owner_direct_confirmation"
                ),
                None,
            )
            if match is None:
                blockers.append("21 cm SKU correction requires structured owner direct evidence")

    return FieldEvidenceResult(not blockers, tuple(blockers))
