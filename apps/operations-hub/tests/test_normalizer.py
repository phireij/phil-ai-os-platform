import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub import (  # noqa: E402
    InMemoryDeduplicator,
    NormalizationError,
    SUPPORTED_SOURCES,
    classify_intent,
    normalize_channel_event,
)

FIXTURES = ROOT / "fixtures"


def load_fixture(source: str):
    return json.loads((FIXTURES / f"{source}.json").read_text(encoding="utf-8"))


class OperationsNormalizationTests(unittest.TestCase):
    def test_all_five_sources_normalize(self):
        for source in SUPPORTED_SOURCES:
            with self.subTest(source=source):
                event = normalize_channel_event(load_fixture(source))
                self.assertEqual(source, event["source"])
                self.assertFalse(event["mutation_authorized"])
                self.assertTrue(event["idempotency_key"].startswith(f"channel:{source}:"))

    def test_facebook_order_inquiry(self):
        event = normalize_channel_event(load_fixture("facebook"))
        self.assertEqual("order_inquiry", event["normalized_intent"])
        self.assertFalse(event["review_required"])

    def test_instagram_product_inquiry(self):
        event = normalize_channel_event(load_fixture("instagram"))
        self.assertEqual("product_inquiry", event["normalized_intent"])

    def test_telegram_pickup_inquiry(self):
        event = normalize_channel_event(load_fixture("telegram"))
        self.assertEqual("pickup_inquiry", event["normalized_intent"])

    def test_whatsapp_complaint_requires_review(self):
        event = normalize_channel_event(load_fixture("whatsapp"))
        self.assertEqual("complaint", event["normalized_intent"])
        self.assertTrue(event["review_required"])
        self.assertEqual("required", event["approval_state"])
        self.assertEqual("sensitive_customer_issue", event["review_reason"])

    def test_google_business_review_requires_review(self):
        event = normalize_channel_event(load_fixture("google_business"))
        self.assertEqual("review_feedback", event["normalized_intent"])
        self.assertTrue(event["review_required"])
        self.assertEqual("public_review_response", event["review_reason"])

    def test_low_confidence_general_inquiry_requires_review(self):
        intent, confidence = classify_intent("Hello there", "message")
        self.assertEqual("general_inquiry", intent)
        self.assertLess(confidence, 0.80)
        payload = load_fixture("telegram")
        payload["text"] = "Hello there"
        event = normalize_channel_event(payload)
        self.assertTrue(event["review_required"])
        self.assertEqual("low_confidence_classification", event["review_reason"])

    def test_duplicate_is_rejected_deterministically(self):
        event = normalize_channel_event(load_fixture("facebook"))
        dedupe = InMemoryDeduplicator()
        first = dedupe.accept(event)
        second = dedupe.accept(event)
        self.assertTrue(first.accepted)
        self.assertFalse(first.duplicate)
        self.assertFalse(second.accepted)
        self.assertTrue(second.duplicate)
        self.assertEqual(first.idempotency_key, second.idempotency_key)

    def test_same_event_normalizes_to_same_fingerprint(self):
        payload = load_fixture("instagram")
        first = normalize_channel_event(payload)
        second = normalize_channel_event(copy.deepcopy(payload))
        self.assertEqual(first["raw_event_fingerprint"], second["raw_event_fingerprint"])
        self.assertEqual(first["lifecycle_correlation_id"], second["lifecycle_correlation_id"])

    def test_non_fixture_event_fails_closed(self):
        payload = load_fixture("facebook")
        payload["fixture_only"] = False
        with self.assertRaises(NormalizationError):
            normalize_channel_event(payload)

    def test_unsupported_source_fails_closed(self):
        payload = load_fixture("facebook")
        payload["source"] = "unknown-channel"
        with self.assertRaises(NormalizationError):
            normalize_channel_event(payload)

    def test_unsupported_kind_fails_closed(self):
        payload = load_fixture("facebook")
        payload["kind"] = "reaction"
        with self.assertRaises(NormalizationError):
            normalize_channel_event(payload)

    def test_unsupported_locale_fails_closed(self):
        payload = load_fixture("facebook")
        payload["locale"] = "fr"
        with self.assertRaises(NormalizationError):
            normalize_channel_event(payload)

    def test_blank_text_fails_closed(self):
        payload = load_fixture("facebook")
        payload["text"] = "   "
        with self.assertRaises(NormalizationError):
            normalize_channel_event(payload)


if __name__ == "__main__":
    unittest.main()
