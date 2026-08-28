import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub.adapters import ChannelAdapterError, MockChannelAdapter, retry_decision  # noqa: E402
from operations_hub.normalizer import NormalizationError  # noqa: E402


def load_fixture(source: str):
    return json.loads((ROOT / "fixtures" / f"{source}.json").read_text(encoding="utf-8"))


class ChannelAdapterTests(unittest.TestCase):
    def test_all_supported_sources_can_use_mock_adapter(self):
        for source in ("facebook", "instagram", "telegram", "whatsapp", "google_business"):
            adapter = MockChannelAdapter(source, load_fixture(source))
            payload = adapter.pull_fixture()
            self.assertTrue(payload["fixture_only"])
            self.assertEqual(source, payload["source"])

    def test_non_fixture_payload_is_rejected(self):
        payload = load_fixture("facebook")
        payload["fixture_only"] = False
        with self.assertRaises(NormalizationError):
            MockChannelAdapter("facebook", payload)

    def test_source_mismatch_is_rejected(self):
        with self.assertRaises(NormalizationError):
            MockChannelAdapter("telegram", load_fixture("facebook"))

    def test_transient_failure_is_retryable_before_limit(self):
        adapter = MockChannelAdapter("telegram", load_fixture("telegram"), fail_code="synthetic_timeout", retryable_failure=True)
        with self.assertRaises(ChannelAdapterError) as ctx:
            adapter.pull_fixture()
        decision = retry_decision(ctx.exception, attempt=1, max_attempts=3)
        self.assertTrue(decision["retry"])
        self.assertEqual("none", decision["authority_effect"])
        self.assertFalse(decision["mutation_authorized"])

    def test_transient_failure_stops_at_limit(self):
        error = ChannelAdapterError("instagram", "synthetic_429", True, "synthetic adapter failure")
        self.assertFalse(retry_decision(error, attempt=3, max_attempts=3)["retry"])

    def test_permanent_failure_is_not_retried(self):
        error = ChannelAdapterError("google_business", "synthetic_invalid_payload", False, "synthetic adapter failure")
        decision = retry_decision(error, attempt=1)
        self.assertFalse(decision["retry"])

    def test_error_envelope_never_grants_authority(self):
        error = ChannelAdapterError("whatsapp", "synthetic_500", True, "synthetic adapter failure")
        envelope = error.to_envelope()
        self.assertEqual("none", envelope["authority_effect"])
        self.assertFalse(envelope["mutation_authorized"])


if __name__ == "__main__":
    unittest.main()
