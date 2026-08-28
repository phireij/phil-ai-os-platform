from __future__ import annotations

from collections import Counter
from typing import Any

from .normalizer import InMemoryDeduplicator, NormalizationError


class OperationsQueue:
    def __init__(self) -> None:
        self._dedupe = InMemoryDeduplicator()
        self._events: list[dict[str, Any]] = []
        self._duplicate_count = 0

    def ingest(self, event: dict[str, Any]) -> dict[str, Any]:
        if event.get("mutation_authorized") is not False:
            raise NormalizationError("operations queue accepts non-authorizing events only")
        decision = self._dedupe.accept(event)
        if decision.duplicate:
            self._duplicate_count += 1
            return {"accepted": False, "duplicate": True, "idempotency_key": decision.idempotency_key}
        self._events.append(dict(event))
        return {"accepted": True, "duplicate": False, "idempotency_key": decision.idempotency_key}

    def read_model(self) -> dict[str, Any]:
        source_counts = Counter(event["source"] for event in self._events)
        intent_counts = Counter(event["normalized_intent"] for event in self._events)
        review_events = [event for event in self._events if event.get("review_required") is True]
        queue_items = [
            {
                "event_ref": event["idempotency_key"],
                "source": event["source"],
                "kind": event["kind"],
                "normalized_intent": event["normalized_intent"],
                "confidence": event["confidence"],
                "review_required": event["review_required"],
                "review_reason": event.get("review_reason"),
                "approval_state": event["approval_state"],
                "occurred_at": event["occurred_at"],
                "lifecycle_correlation_id": event["lifecycle_correlation_id"],
                "mutation_authorized": False,
            }
            for event in sorted(self._events, key=lambda item: (item["occurred_at"], item["idempotency_key"]))
        ]
        return {
            "status": "read_only",
            "total_events": len(self._events),
            "duplicate_events": self._duplicate_count,
            "review_required": len(review_events),
            "standard_queue": len(self._events) - len(review_events),
            "source_counts": dict(sorted(source_counts.items())),
            "intent_counts": dict(sorted(intent_counts.items())),
            "items": queue_items,
            "mutation_authorized": False,
        }
