from __future__ import annotations

from typing import Any

from .order_quote_approval import OrderQuoteApprovalRequestError


class OrderQuoteApprovalRequestRegister:
    """Read-only, in-memory register for pending quote approval requests."""

    def __init__(self) -> None:
        self._requests: dict[str, dict[str, Any]] = {}
        self._duplicates = 0

    def register(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise OrderQuoteApprovalRequestError("approval request must be an object")
        if request.get("schema") != "rubys-order-quote-approval-request" or request.get("version") != 1:
            raise OrderQuoteApprovalRequestError("unsupported quote approval request schema")
        if request.get("state") != "approval_requested":
            raise OrderQuoteApprovalRequestError("approval request must remain approval_requested")

        approval = request.get("approval")
        if not isinstance(approval, dict):
            raise OrderQuoteApprovalRequestError("approval request approval must be an object")
        if approval.get("required") is not True:
            raise OrderQuoteApprovalRequestError("approval request must remain approval-gated")
        if approval.get("decision") is not None:
            raise OrderQuoteApprovalRequestError("approval decision must remain unset")
        if approval.get("approved_by") is not None or approval.get("approved_at") is not None:
            raise OrderQuoteApprovalRequestError("approval metadata must remain unset")

        authority = request.get("authority")
        if not isinstance(authority, dict):
            raise OrderQuoteApprovalRequestError("approval request authority must be an object")
        for field, value in authority.items():
            if field == "approval_request_only":
                if value is not True:
                    raise OrderQuoteApprovalRequestError("approval request must remain approval_request_only")
            elif value is not False:
                raise OrderQuoteApprovalRequestError(f"approval request authority {field} must remain false")

        pricing = request.get("pricing")
        if not isinstance(pricing, dict):
            raise OrderQuoteApprovalRequestError("approval request pricing must be an object")
        quote_amount = pricing.get("quote_amount")
        shipping_amount = pricing.get("shipping_amount")
        total_amount = pricing.get("total_amount")
        for field, value in (
            ("quote_amount", quote_amount),
            ("shipping_amount", shipping_amount),
            ("total_amount", total_amount),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise OrderQuoteApprovalRequestError(
                    f"approval request {field} must be a non-negative integer"
                )
        if total_amount != quote_amount + shipping_amount:
            raise OrderQuoteApprovalRequestError("approval request total_amount must reconcile")
        if pricing.get("currency") != "JPY":
            raise OrderQuoteApprovalRequestError("approval request currency must remain JPY")
        if pricing.get("customer_accepted") is not False:
            raise OrderQuoteApprovalRequestError("approval request customer_accepted must remain false")

        request_id = request.get("approval_request_id")
        correlation_id = request.get("lifecycle_correlation_id")
        source_draft_id = request.get("source_draft_id")
        if not isinstance(request_id, str) or not request_id.startswith("quote-approval:"):
            raise OrderQuoteApprovalRequestError("invalid approval_request_id")
        if not isinstance(correlation_id, str) or not correlation_id:
            raise OrderQuoteApprovalRequestError("approval request is missing lifecycle_correlation_id")
        if not isinstance(source_draft_id, str) or not source_draft_id.startswith("quote-draft:"):
            raise OrderQuoteApprovalRequestError("invalid source_draft_id")

        if request_id in self._requests:
            self._duplicates += 1
            return {
                "accepted": False,
                "duplicate": True,
                "approval_request_id": request_id,
                "lifecycle_correlation_id": correlation_id,
                "mutation_authorized": False,
            }

        self._requests[request_id] = dict(request)
        return {
            "accepted": True,
            "duplicate": False,
            "approval_request_id": request_id,
            "lifecycle_correlation_id": correlation_id,
            "mutation_authorized": False,
        }

    def read_model(self) -> dict[str, Any]:
        items = []
        for request in sorted(self._requests.values(), key=lambda item: item["approval_request_id"]):
            pricing = request["pricing"]
            items.append({
                "approval_request_id": request["approval_request_id"],
                "lifecycle_correlation_id": request["lifecycle_correlation_id"],
                "source_draft_id": request["source_draft_id"],
                "state": request["state"],
                "quote_amount": pricing["quote_amount"],
                "shipping_amount": pricing["shipping_amount"],
                "total_amount": pricing["total_amount"],
                "currency": pricing["currency"],
                "has_reason": bool(request.get("reason")),
                "decision": None,
                "quote_authorized": False,
                "customer_notification_authorized": False,
                "mutation_authorized": False,
            })
        return {
            "status": "read_only",
            "register": "order_quote_approval_requests",
            "pending_approval_count": len(items),
            "duplicate_requests": self._duplicates,
            "items": items,
            "quote_authorized": False,
            "customer_notification_authorized": False,
            "order_creation_authorized": False,
            "payment_execution_authorized": False,
            "mutation_authorized": False,
        }

    def request_detail(self, approval_request_id: str) -> dict[str, Any] | None:
        request = self._requests.get(approval_request_id)
        if request is None:
            return None
        return {
            "approval_request_id": request["approval_request_id"],
            "lifecycle_correlation_id": request["lifecycle_correlation_id"],
            "source_draft_id": request["source_draft_id"],
            "state": request["state"],
            "requested_by": request.get("requested_by"),
            "reason": request.get("reason", ""),
            "pricing": dict(request["pricing"]),
            "approval": dict(request["approval"]),
            "authority": dict(request["authority"]),
        }
