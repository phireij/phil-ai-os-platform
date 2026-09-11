import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub.normalizer import SUPPORTED_SOURCES  # noqa: E402
from operations_hub.synthetic_lifecycle import (  # noqa: E402
    SyntheticLifecycleError,
    run_synthetic_multichannel_lifecycle,
)


def load_fixtures():
    return {
        source: json.loads((ROOT / "fixtures" / f"{source}.json").read_text(encoding="utf-8"))
        for source in SUPPORTED_SOURCES
    }


class SyntheticMultichannelLifecycleTests(unittest.TestCase):
    def test_all_supported_channels_compose_into_one_read_only_lifecycle(self):
        evidence = run_synthetic_multichannel_lifecycle(load_fixtures())

        self.assertEqual("sprint5_operations_multichannel_lifecycle_synthetic", evidence["smoke"])
        self.assertTrue(evidence["fixture_only"])
        self.assertEqual(list(SUPPORTED_SOURCES), evidence["sources"])
        self.assertEqual(5, evidence["queue"]["total_events"])
        self.assertEqual(5, evidence["queue"]["duplicate_events"])
        self.assertEqual(2, evidence["queue"]["review_required"])
        self.assertEqual(3, evidence["queue"]["standard_queue"])
        self.assertEqual(5, len(evidence["channels"]))
        self.assertTrue(all(item["first_ingest_accepted"] for item in evidence["channels"]))
        self.assertTrue(all(item["duplicate_rejected"] for item in evidence["channels"]))
        self.assertTrue(all(item["authority_effect"] == "none" for item in evidence["channels"]))

    def test_lifecycle_never_grants_or_performs_external_authority(self):
        evidence = run_synthetic_multichannel_lifecycle(load_fixtures())

        for field in (
            "network_call_performed",
            "external_dispatch_performed",
            "order_mutation_performed",
            "payment_performed",
            "inventory_mutation_performed",
            "production_authority_changed",
        ):
            self.assertFalse(evidence[field], field)
        self.assertFalse(evidence["queue"]["mutation_authorized"])
        for item in evidence["channels"]:
            self.assertFalse(item["execution_authorized"])
            self.assertFalse(item["channel_reply_authorized"])
            self.assertFalse(item["mutation_authorized"])

    def test_sensitive_and_public_review_channels_remain_review_gated(self):
        evidence = run_synthetic_multichannel_lifecycle(load_fixtures())
        by_source = {item["source"]: item for item in evidence["channels"]}

        self.assertTrue(by_source["whatsapp"]["review_required"])
        self.assertTrue(by_source["whatsapp"]["approval_required"])
        self.assertEqual("high", by_source["whatsapp"]["risk_level"])
        self.assertTrue(by_source["google_business"]["review_required"])
        self.assertTrue(by_source["google_business"]["approval_required"])

    def test_exact_supported_fixture_set_is_required(self):
        fixtures = load_fixtures()
        fixtures.pop("telegram")
        with self.assertRaisesRegex(SyntheticLifecycleError, "exact supported source set"):
            run_synthetic_multichannel_lifecycle(fixtures)

        fixtures = load_fixtures()
        fixtures["unknown"] = copy.deepcopy(fixtures["facebook"])
        with self.assertRaisesRegex(SyntheticLifecycleError, "exact supported source set"):
            run_synthetic_multichannel_lifecycle(fixtures)

    def test_fixture_boundary_and_source_identity_fail_closed(self):
        fixtures = load_fixtures()
        fixtures["facebook"]["fixture_only"] = False
        with self.assertRaisesRegex(SyntheticLifecycleError, "fixture_only"):
            run_synthetic_multichannel_lifecycle(fixtures)

        fixtures = load_fixtures()
        fixtures["facebook"]["source"] = "instagram"
        with self.assertRaisesRegex(SyntheticLifecycleError, "source mismatch"):
            run_synthetic_multichannel_lifecycle(fixtures)

    def test_input_fixtures_are_not_mutated(self):
        fixtures = load_fixtures()
        before = copy.deepcopy(fixtures)
        run_synthetic_multichannel_lifecycle(fixtures)
        self.assertEqual(before, fixtures)


if __name__ == "__main__":
    unittest.main()
