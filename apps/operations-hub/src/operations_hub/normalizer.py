from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

SUPPORTED_SOURCES = ("facebook", "instagram", "telegram", "whatsapp", "google_business")
SUPPORTED_KINDS = ("message", "comment", "review")
SUPPORTED_LOCALES = ("en", "ja", "unknown")


class NormalizationError(ValueError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _require_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise NormalizationError(f"{field} is required")
    return value.strip()


def classify_intent(text: str, kind: str) -> tuple[str, float]:
    lowered = text.casefold()
    rules = (
        ("complaint", ("complaint", "wrong", "late", "problem", "issue", "問題", "遅", "間違"), 0.97),
        ("pickup_inquiry", ("pickup", "pick up", "collect", "受取", "受け取"), 0.95),
        ("order_inquiry", ("order", "reserve", "buy", "注文", "予約", "購入"), 0.94),
        ("product_inquiry", ("price", "menu", "product", "available", "価格", "メニュー", "商品", "ありますか"), 0.92),
    )
    for intent, tokens, confidence in rules:
        if any(token in lowered for token in tokens):
            return intent, confidence
    if kind == "review":
        return "review_feedback", 0.90
    return "general_inquiry", 0.68


def _review_decision(intent: str, confidence: float, kind: str) -> tuple[bool, str | None, str]:
    if intent == "complaint":
        return True, "sensitive_customer_issue", "required"
    if confidence < 0.80:
        return True, "low_confidence_classification", "required"
    if kind == "review":
        return True, "public_review_response", "required"
    return False, None, "not_evaluated"


def normalize_channel_event(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("fixture_only") is not True:
        raise NormalizationError("bounded Sprint 5 accepts fixture_only channel events")

    source = _require_text(payload, "source")
    if source not in SUPPORTED_SOURCES:
        raise NormalizationError(f"unsupported source: {source}")

    kind = _require_text(payload, "kind")
    if kind not in SUPPORTED_KINDS:
        raise NormalizationError(f"unsupported kind: {kind}")

    external_event_id = _require_text(payload, "external_event_id")
    occurred_at = _require_text(payload, "occurred_at")
    text = _require_text(payload, "text")
    locale = payload.get("locale", "unknown")
    if locale not in SUPPORTED_LOCALES:
        raise NormalizationError(f"unsupported locale: {locale}")

    sender_ref = payload.get("sender_ref")
    if sender_ref is not None and (not isinstance(sender_ref, str) or not sender_ref.strip()):
        raise NormalizationError("sender_ref must be a non-empty string or null")

    intent, confidence = classify_intent(text, kind)
    review_required, review_reason, approval_state = _review_decision(intent, confidence, kind)
    idempotency_key = f"channel:{source}:{external_event_id}"
    fingerprint = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    correlation_id = f"ops:{hashlib.sha256(idempotency_key.encode('utf-8')).hexdigest()[:24]}"

    return {
        "fixture_only": True,
        "source": source,
        "kind": kind,
        "external_event_id": external_event_id,
        "occurred_at": occurred_at,
        "sender_ref": sender_ref.strip() if isinstance(sender_ref, str) else None,
        "normalized_intent": intent,
        "entities": {"locale": locale, "text": text},
        "confidence": confidence,
        "idempotency_key": idempotency_key,
        "raw_event_fingerprint": fingerprint,
        "review_required": review_required,
        "review_reason": review_reason,
        "approval_state": approval_state,
        "lifecycle_correlation_id": correlation_id,
        "mutation_authorized": False,
    }


@dataclass(frozen=True)
class DeduplicationResult:
    accepted: bool
    duplicate: bool
    idempotency_key: str


class InMemoryDeduplicator:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def accept(self, event: dict[str, Any]) -> DeduplicationResult:
        key = _require_text(event, "idempotency_key")
        if key in self._seen:
            return DeduplicationResult(False, True, key)
        self._seen.add(key)
        return DeduplicationResult(True, False, key)
