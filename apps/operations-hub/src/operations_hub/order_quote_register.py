from __future__ import annotations

import copy
from typing import Any

from .order_quote_draft import OrderQuoteDraftError


class OrderQuoteDraftRegister:
    """Read-only, in-memory register for bounded staff quote drafts."""

    def __init__(self) -> None:
        self._drafts: dict[str, dict[str, Any]] = {}
        self._duplicates = 0

    def register(self, draft: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(draft, dict):
            raise OrderQuoteDraftError("quote draft must be an object")
        if draft.get("schema") != "rubys-order-quote-draft" or draft.get("version") != 1:
            raise OrderQuoteDraftError("unsupported quote draft schema")
        if draft.get("state") != "draft_for_staff_review":
            raise OrderQuoteDraftError("quote draft must remain draft_for_staff_review")

        authority = draft.get("authority")
        if not isinstance(authority, dict):
            raise OrderQuoteDraftError("quote draft authority must be an object")
        for field, value in authority.items():
            if field == "staff_review_only":
                if value is not True:
                    raise OrderQuoteDraftError("quote draft must remain staff_review_only")
            elif value is not False:
                raise OrderQuoteDraftError(f"quote draft authority {field} must remain false")

        correlation_id = draft.get("lifecycle_correlation_id")
        if not isinstance(correlation_id, str) or not correlation_id:
            raise OrderQuoteDraftError("quote draft is missing lifecycle_correlation_id")
        draft_id = draft.get("draft_id")
        if not isinstance(draft_id, str) or not draft_id.startswith("quote-draft:"):
            raise OrderQuoteDraftError("invalid quote draft_id")

        pricing = draft.get("pricing")
        if not isinstance(pricing, dict):
            raise OrderQuoteDraftError("quote draft pricing must be an object")
        quote_amount = pricing.get("quote_amount")
        shipping_amount = pricing.get("shipping_amount")
        total_amount = pricing.get("total_amount")
        for field, value in (
            ("quote_amount", quote_amount),
            ("shipping_amount", shipping_amount),
            ("total_amount", total_amount),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise OrderQuoteDraftError(f"quote draft {field} must be a non-negative integer")
        if total_amount != quote_amount + shipping_amount:
            raise OrderQuoteDraftError("quote draft total_amount must reconcile")
        if pricing.get("currency") != "JPY":
            raise OrderQuoteDraftError("quote draft currency must remain JPY")
        if pricing.get("customer_accepted") is not False:
            raise OrderQuoteDraftError("quote draft customer_accepted must remain false")

        if draft_id in self._drafts:
            if draft != self._drafts[draft_id]:
                raise OrderQuoteDraftError("quote draft_id conflicts with existing draft content")
            self._duplicates += 1
            return {
                "accepted": False,
                "duplicate": True,
                "draft_id": draft_id,
                "lifecycle_correlation_id": correlation_id,
                "mutation_authorized": False,
            }

        self._drafts[draft_id] = copy.deepcopy(draft)
        return {
            "accepted": True,
            "duplicate": False,
            "draft_id": draft_id,
            "lifecycle_correlation_id": correlation_id,
            "mutation_authorized": False,
        }

    def read_model(self) -> dict[str, Any]:
        items = []
        for draft in sorted(self._drafts.values(), key=lambda item: item["draft_id"]):
            pricing = draft["pricing"]
            fulfillment = draft.get("request_context", {}).get("fulfillment", {})
            items.append({
                "draft_id": draft["draft_id"],
                "lifecycle_correlation_id": draft["lifecycle_correlation_id"],
                "state": draft["state"],
                "fulfillment_method": fulfillment.get("method"),
                "requested_date": fulfillment.get("requested_date"),
                "quote_amount": pricing["quote_amount"],
                "shipping_amount": pricing["shipping_amount"],
                "total_amount": pricing["total_amount"],
                "currency": pricing["currency"],
                "has_note": bool(draft.get("note")),
                "customer_accepted": False,
                "quote_authorized": False,
                "mutation_authorized": False,
            })
        return {
            "status": "read_only",
            "register": "order_quote_drafts",
            "draft_count": len(items),
            "duplicate_drafts": self._duplicates,
            "items": items,
            "quote_authorized": False,
            "customer_notification_authorized": False,
            "order_creation_authorized": False,
            "payment_execution_authorized": False,
            "mutation_authorized": False,
        }

    def draft_detail(self, draft_id: str) -> dict[str, Any] | None:
        draft = self._drafts.get(draft_id)
        if draft is None:
            return None
        return {
            "draft_id": draft["draft_id"],
            "lifecycle_correlation_id": draft["lifecycle_correlation_id"],
            "state": draft["state"],
            "source_preparation_id": draft.get("source_preparation_id"),
            "request_context": copy.deepcopy(draft.get("request_context")),
            "pricing": copy.deepcopy(draft["pricing"]),
            "authority": copy.deepcopy(draft["authority"]),
            "note": draft.get("note", ""),
        }
