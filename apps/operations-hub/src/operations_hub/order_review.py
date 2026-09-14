from __future__ import annotations

import copy
from typing import Any

from .order_intake import OrderIntakeHandoffError, normalize_order_intake_handoff


class OrderReviewQueue:
    """Read-only, in-memory staff-review queue for validated order-intake handoffs."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self._duplicates = 0

    def ingest_handoff(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_order_intake_handoff(payload)
        authority = normalized.get("authority", {})
        if authority.get("mutation_authorized") is not False:
            raise OrderIntakeHandoffError("order review queue accepts non-authorizing records only")
        if normalized.get("review_required") is not True or normalized.get("review_state") != "pending_staff_review":
            raise OrderIntakeHandoffError("order review queue requires pending staff review")

        key = normalized["raw_handoff_fingerprint"]
        if key in self._items:
            self._duplicates += 1
            return {
                "accepted": False,
                "duplicate": True,
                "lifecycle_correlation_id": normalized["lifecycle_correlation_id"],
                "mutation_authorized": False,
            }

        self._items[key] = normalized
        return {
            "accepted": True,
            "duplicate": False,
            "lifecycle_correlation_id": normalized["lifecycle_correlation_id"],
            "mutation_authorized": False,
        }

    def read_model(self) -> dict[str, Any]:
        items = []
        for record in sorted(self._items.values(), key=lambda item: item["lifecycle_correlation_id"]):
            fulfillment = record["entities"]["fulfillment"]
            customization = record["entities"]["customization"]
            items.append({
                "event_ref": record["raw_handoff_fingerprint"],
                "lifecycle_correlation_id": record["lifecycle_correlation_id"],
                "source": record["source"],
                "kind": record["kind"],
                "review_state": record["review_state"],
                "review_reason": record["review_reason"],
                "fulfillment_method": fulfillment["method"],
                "requested_date": fulfillment["requested_date"],
                "cake_type": customization["cake_type"],
                "reference_image_count": customization["reference_image_count"],
                "has_custom_notes": bool(customization["custom_notes"]),
                "mutation_authorized": False,
            })
        return {
            "status": "read_only",
            "queue": "order_intake_staff_review",
            "pending_review": len(items),
            "duplicate_handoffs": self._duplicates,
            "items": items,
            "mutation_authorized": False,
        }

    def review_detail(self, lifecycle_correlation_id: str) -> dict[str, Any] | None:
        for record in self._items.values():
            if record["lifecycle_correlation_id"] == lifecycle_correlation_id:
                return {
                    "lifecycle_correlation_id": lifecycle_correlation_id,
                    "review_state": record["review_state"],
                    "review_reason": record["review_reason"],
                    "entities": copy.deepcopy(record["entities"]),
                    "authority": copy.deepcopy(record["authority"]),
                }
        return None
