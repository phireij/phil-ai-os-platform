from __future__ import annotations

from typing import Any

from .order_quote_approval_register import OrderQuoteApprovalRequestRegister
from .order_quote_register import OrderQuoteDraftRegister


class OrderQuoteApprovalWorkspaceError(ValueError):
    pass


def _require_read_only(model: Any, name: str) -> dict[str, Any]:
    if not isinstance(model, dict):
        raise OrderQuoteApprovalWorkspaceError(f"{name} read model must be an object")
    if model.get("status") != "read_only" or model.get("mutation_authorized") is not False:
        raise OrderQuoteApprovalWorkspaceError(
            f"{name} read model must remain read_only and non-authorizing"
        )
    return model


def build_order_quote_approval_workspace(
    draft_register: OrderQuoteDraftRegister,
    approval_register: OrderQuoteApprovalRequestRegister,
) -> dict[str, Any]:
    """Correlate staff quote drafts with pending approval requests without executing decisions."""
    if not isinstance(draft_register, OrderQuoteDraftRegister):
        raise OrderQuoteApprovalWorkspaceError(
            "draft_register must be an OrderQuoteDraftRegister"
        )
    if not isinstance(approval_register, OrderQuoteApprovalRequestRegister):
        raise OrderQuoteApprovalWorkspaceError(
            "approval_register must be an OrderQuoteApprovalRequestRegister"
        )

    draft_model = _require_read_only(draft_register.read_model(), "draft_register")
    approval_model = _require_read_only(approval_register.read_model(), "approval_register")

    drafts_by_id: dict[str, dict[str, Any]] = {}
    for draft in draft_model.get("items", []):
        draft_id = draft.get("draft_id")
        if not isinstance(draft_id, str) or not draft_id:
            raise OrderQuoteApprovalWorkspaceError("quote draft is missing draft_id")
        drafts_by_id[draft_id] = draft

    approvals_by_draft: dict[str, list[dict[str, Any]]] = {}
    for request in approval_model.get("items", []):
        source_draft_id = request.get("source_draft_id")
        if not isinstance(source_draft_id, str) or not source_draft_id:
            raise OrderQuoteApprovalWorkspaceError(
                "approval request is missing source_draft_id"
            )
        approvals_by_draft.setdefault(source_draft_id, []).append(request)

    orphan_requests = sorted(
        source_draft_id
        for source_draft_id in approvals_by_draft
        if source_draft_id not in drafts_by_id
    )
    if orphan_requests:
        raise OrderQuoteApprovalWorkspaceError(
            "approval register contains requests whose source drafts are absent"
        )

    rows: list[dict[str, Any]] = []
    for draft_id, draft in drafts_by_id.items():
        requests = approvals_by_draft.get(draft_id, [])
        correlation_id = draft.get("lifecycle_correlation_id")
        for request in requests:
            if request.get("lifecycle_correlation_id") != correlation_id:
                raise OrderQuoteApprovalWorkspaceError(
                    "approval request correlation does not match source draft"
                )
            if request.get("quote_amount") != draft.get("quote_amount"):
                raise OrderQuoteApprovalWorkspaceError(
                    "approval request quote_amount does not match source draft"
                )
            if request.get("shipping_amount") != draft.get("shipping_amount"):
                raise OrderQuoteApprovalWorkspaceError(
                    "approval request shipping_amount does not match source draft"
                )
            if request.get("total_amount") != draft.get("total_amount"):
                raise OrderQuoteApprovalWorkspaceError(
                    "approval request total_amount does not match source draft"
                )
            if request.get("currency") != draft.get("currency"):
                raise OrderQuoteApprovalWorkspaceError(
                    "approval request currency does not match source draft"
                )

        request_ids = sorted(
            request["approval_request_id"] for request in requests
        )
        rows.append({
            "draft_id": draft_id,
            "lifecycle_correlation_id": correlation_id,
            "draft_state": draft.get("state"),
            "fulfillment_method": draft.get("fulfillment_method"),
            "requested_date": draft.get("requested_date"),
            "quote_amount": draft.get("quote_amount"),
            "shipping_amount": draft.get("shipping_amount"),
            "total_amount": draft.get("total_amount"),
            "currency": draft.get("currency"),
            "approval_request_count": len(requests),
            "approval_request_ids": request_ids,
            "approval_status": "approval_requested" if requests else "approval_not_requested",
            "decision": None,
            "quote_authorized": False,
            "customer_notification_authorized": False,
            "mutation_authorized": False,
        })

    pending_approval_count = sum(
        1 for row in rows if row["approval_status"] == "approval_requested"
    )
    awaiting_request_count = sum(
        1 for row in rows if row["approval_status"] == "approval_not_requested"
    )
    return {
        "status": "read_only",
        "workspace": "order_quote_approval_review",
        "draft_count": len(rows),
        "pending_approval_count": pending_approval_count,
        "awaiting_approval_request_count": awaiting_request_count,
        "items": sorted(rows, key=lambda item: item["draft_id"]),
        "quote_authorized": False,
        "customer_notification_authorized": False,
        "fulfillment_confirmed": False,
        "woo_commerce_mutation_authorized": False,
        "order_creation_authorized": False,
        "payment_execution_authorized": False,
        "sms_send_authorized": False,
        "inventory_mutation_authorized": False,
        "production_publish_authorized": False,
        "mutation_authorized": False,
    }
