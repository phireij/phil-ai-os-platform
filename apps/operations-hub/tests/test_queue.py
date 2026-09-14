import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub import NormalizationError, normalize_channel_event  # noqa: E402
from operations_hub.queue import OperationsQueue  # noqa: E402


def load_fixture(source: str):
    return json.loads((ROOT / "fixtures" / f"{source}.json").read_text(encoding="utf-8"))


class OperationsQueueTests(unittest.TestCase):
    def test_queue_summarizes_all_sources(self):
        queue = OperationsQueue()
        for source in ("facebook", "instagram", "telegram", "whatsapp", "google_business"):
            queue.ingest(normalize_channel_event(load_fixture(source)))
        view = queue.read_model()
        self.assertEqual(5, view["total_events"])
        self.assertEqual(2, view["review_required"])
        self.assertEqual(3, view["standard_queue"])
        self.assertEqual("read_only", view["status"])
        self.assertFalse(view["mutation_authorized"])
        self.assertEqual(5, len(view["source_counts"]))

    def test_duplicate_does_not_increase_active_queue(self):
        queue = OperationsQueue()
        event = normalize_channel_event(load_fixture("facebook"))
        self.assertTrue(queue.ingest(event)["accepted"])
        self.assertTrue(queue.ingest(event)["duplicate"])
        view = queue.read_model()
        self.assertEqual(1, view["total_events"])
        self.assertEqual(1, view["duplicate_events"])

    def test_conflicting_event_content_under_same_idempotency_key_fails_closed(self):
        queue = OperationsQueue()
        first_payload = load_fixture("facebook")
        first = normalize_channel_event(first_payload)
        queue.ingest(first)

        second_payload = copy.deepcopy(first_payload)
        second_payload["text"] = "Different customer message"
        second = normalize_channel_event(second_payload)
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])
        with self.assertRaisesRegex(NormalizationError, "conflicts with different event content"):
            queue.ingest(second)
        self.assertEqual(0, queue.read_model()["duplicate_events"])

    def test_queue_copies_ingested_event_state(self):
        queue = OperationsQueue()
        event = normalize_channel_event(load_fixture("instagram"))
        original_intent = event["normalized_intent"]
        queue.ingest(event)
        event["normalized_intent"] = "complaint"
        event["review_required"] = True
        event["mutation_authorized"] = True

        view = queue.read_model()
        self.assertEqual(original_intent, view["items"][0]["normalized_intent"])
        self.assertFalse(view["items"][0]["review_required"])
        self.assertFalse(view["items"][0]["mutation_authorized"])

    def test_public_review_appears_in_review_queue_count(self):
        queue = OperationsQueue()
        queue.ingest(normalize_channel_event(load_fixture("google_business")))
        view = queue.read_model()
        self.assertEqual(1, view["review_required"])
        self.assertTrue(view["items"][0]["review_required"])
        self.assertEqual("public_review_response", view["items"][0]["review_reason"])

    def test_complaint_appears_in_review_queue_count(self):
        queue = OperationsQueue()
        queue.ingest(normalize_channel_event(load_fixture("whatsapp")))
        view = queue.read_model()
        self.assertEqual(1, view["review_required"])
        self.assertEqual("complaint", view["items"][0]["normalized_intent"])

    def test_queue_rejects_authorizing_event(self):
        queue = OperationsQueue()
        event = normalize_channel_event(load_fixture("telegram"))
        event["mutation_authorized"] = True
        with self.assertRaises(NormalizationError):
            queue.ingest(event)

    def test_read_model_does_not_expose_raw_customer_text(self):
        queue = OperationsQueue()
        queue.ingest(normalize_channel_event(load_fixture("facebook")))
        view = queue.read_model()
        self.assertNotIn("entities", view["items"][0])
        self.assertNotIn("text", view["items"][0])


if __name__ == "__main__":
    unittest.main()
