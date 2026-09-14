from __future__ import annotations

import copy
from typing import Any

from .order_quote_owner_decision_packet import OrderQuoteOwnerDecisionPacketError


class OrderQuoteOwnerDecisionPacketRegister:
    """Read-only in-memory register for owner quote decision packets."""

    def __init__(self) -> None:
        self._packets: dict[str, dict[str, Any]] = {}
        self._duplicates = 0

    def register(self, packet: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(packet, dict):
            raise OrderQuoteOwnerDecisionPacketError("owner decision packet must be an object")
        if packet.get("schema") != "rubys-order-quote-owner-decision-packet" or packet.get("version") != 1:
            raise OrderQuoteOwnerDecisionPacketError("unsupported owner decision packet schema")
        if packet.get("state") != "awaiting_owner_decision":
            raise OrderQuoteOwnerDecisionPacketError("owner decision packet must remain awaiting_owner_decision")

        request_id = packet.get("approval_request_id")
        correlation_id = packet.get("lifecycle_correlation_id")
        source_draft_id = packet.get("source_draft_id")
        if not isinstance(request_id, str) or not request_id.startswith("quote-approval:"):
            raise OrderQuoteOwnerDecisionPacketError("invalid approval_request_id")
        if not isinstance(correlation_id, str) or not correlation_id:
            raise OrderQuoteOwnerDecisionPacketError("owner decision packet is missing lifecycle_correlation_id")
        if not isinstance(source_draft_id, str) or not source_draft_id.startswith("quote-draft:"):
            raise OrderQuoteOwnerDecisionPacketError("invalid source_draft_id")

        proposal_ids = packet.get("decision_proposal_ids")
        if not isinstance(proposal_ids, list) or not proposal_ids:
            raise OrderQuoteOwnerDecisionPacketError("owner decision packet requires source proposals")
        if any(not isinstance(value, str) or not value.startswith("quote-approval-proposal:") for value in proposal_ids):
            raise OrderQuoteOwnerDecisionPacketError("owner decision packet has invalid source proposal IDs")

        if packet.get("recommendation") not in {"recommend_quote_approval", "request_quote_revision"}:
            raise OrderQuoteOwnerDecisionPacketError("unsupported quote approval recommendation")

        pricing = packet.get("pricing")
        if not isinstance(pricing, dict):
            raise OrderQuoteOwnerDecisionPacketError("owner decision packet pricing must be an object")
        quote_amount = pricing.get("quote_amount")
        shipping_amount = pricing.get("shipping_amount")
        total_amount = pricing.get("total_amount")
        for value in (quote_amount, shipping_amount, total_amount):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise OrderQuoteOwnerDecisionPacketError("owner decision packet pricing must contain non-negative integer JPY amounts")
        if total_amount != quote_amount + shipping_amount:
            raise OrderQuoteOwnerDecisionPacketError("owner decision packet total_amount must reconcile")
        if pricing.get("currency") != "JPY" or pricing.get("customer_accepted") is not False:
            raise OrderQuoteOwnerDecisionPacketError("owner decision packet pricing state is invalid")

        owner_decision = packet.get("owner_decision")
        if not isinstance(owner_decision, dict) or owner_decision.get("required") is not True:
            raise OrderQuoteOwnerDecisionPacketError("owner decision must remain required")
        if owner_decision.get("decision") is not None:
            raise OrderQuoteOwnerDecisionPacketError("owner decision must remain unset")
        if owner_decision.get("decided_by") is not None or owner_decision.get("decided_at") is not None:
            raise OrderQuoteOwnerDecisionPacketError("owner decision metadata must remain unset")

        authority = packet.get("authority")
        if not isinstance(authority, dict):
            raise OrderQuoteOwnerDecisionPacketError("owner decision packet authority must be an object")
        for field, value in authority.items():
            if field == "owner_review_only":
                if value is not True:
                    raise OrderQuoteOwnerDecisionPacketError("owner decision packet must remain owner_review_only")
            elif value is not False:
                raise OrderQuoteOwnerDecisionPacketError(f"owner decision packet authority {field} must remain false")

        existing = self._packets.get(request_id)
        if existing is not None:
            if existing != packet:
                raise OrderQuoteOwnerDecisionPacketError("owner decision packet content changed for existing approval_request_id")
            self._duplicates += 1
            return {
                "accepted": False,
                "duplicate": True,
                "approval_request_id": request_id,
                "mutation_authorized": False,
            }

        self._packets[request_id] = copy.deepcopy(packet)
        return {
            "accepted": True,
            "duplicate": False,
            "approval_request_id": request_id,
            "mutation_authorized": False,
        }

    def read_model(self) -> dict[str, Any]:
        items = []
        for packet in sorted(self._packets.values(), key=lambda item: item["approval_request_id"]):
            pricing = packet["pricing"]
            items.append({
                "approval_request_id": packet["approval_request_id"],
                "lifecycle_correlation_id": packet["lifecycle_correlation_id"],
                "source_draft_id": packet["source_draft_id"],
                "recommendation": packet["recommendation"],
                "total_amount": pricing["total_amount"],
                "currency": pricing["currency"],
                "owner_decision_required": True,
                "owner_decision": None,
                "quote_authorized": False,
                "mutation_authorized": False,
            })
        return {
            "status": "read_only",
            "register": "order_quote_owner_decision_packets",
            "packet_count": len(items),
            "duplicate_packets": self._duplicates,
            "items": items,
            "owner_decision_pending": bool(items),
            "approval_decided": False,
            "quote_authorized": False,
            "customer_notification_authorized": False,
            "order_creation_authorized": False,
            "payment_execution_authorized": False,
            "mutation_authorized": False,
        }

    def packet_detail(self, approval_request_id: str) -> dict[str, Any] | None:
        packet = self._packets.get(approval_request_id)
        if packet is None:
            return None
        return copy.deepcopy(packet)
