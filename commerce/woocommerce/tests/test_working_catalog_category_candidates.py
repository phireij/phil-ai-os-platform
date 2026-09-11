import json
from pathlib import Path
import unittest

from phil_ai_os_woocommerce.working_catalog_category_candidates import (
    build_working_catalog_category_candidate_packet,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"


class WorkingCatalogCategoryCandidatePacketTests(unittest.TestCase):
    def load(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_current_source_labels_are_preserved_without_invented_mapping(self):
        packet = build_working_catalog_category_candidate_packet(self.load())
        by_label = {candidate.source_label: candidate for candidate in packet.candidates}

        self.assertIn("Other", by_label)
        self.assertIn("Bread", by_label)
        self.assertEqual(by_label["Other"].product_keys, ("RCD-BAR-FMB",))
        self.assertEqual(by_label["Bread"].product_keys, ("RCD-BRD-ENS-1",))
        self.assertIsNone(by_label["Other"].english_name)
        self.assertIsNone(by_label["Other"].japanese_name)
        self.assertIsNone(by_label["Other"].english_slug)
        self.assertIsNone(by_label["Other"].japanese_slug)
        self.assertFalse(by_label["Other"].mapping_approved)

    def test_missing_source_label_is_explicit_blocker(self):
        packet = build_working_catalog_category_candidate_packet(self.load())
        self.assertIn(
            "RCD-MCH-RD: category source label is missing",
            packet.blockers,
        )

    def test_packet_never_grants_mapping_or_production_authority(self):
        packet = build_working_catalog_category_candidate_packet(self.load())
        self.assertFalse(packet.ready_for_category_mapping_approval)
        self.assertFalse(packet.network_call_performed)
        self.assertFalse(packet.mutation_authorized)
        self.assertFalse(packet.production_publish_authorized)
        self.assertIn(
            "final category hierarchy, bilingual names, slugs, and mappings require approval",
            packet.blockers,
        )

    def test_duplicate_source_labels_are_grouped_deterministically(self):
        payload = self.load()
        payload["working_products"][0]["category_source_label"] = "Bread"
        packet = build_working_catalog_category_candidate_packet(payload)
        by_label = {candidate.source_label: candidate for candidate in packet.candidates}
        self.assertEqual(
            by_label["Bread"].product_keys,
            ("RCD-BRD-ENS-1", "RCD-MCH-RD"),
        )

    def test_empty_catalog_fails_closed(self):
        payload = self.load()
        payload["working_products"] = []
        packet = build_working_catalog_category_candidate_packet(payload)
        self.assertFalse(packet.ready_for_category_mapping_approval)
        self.assertEqual(packet.candidates, ())
        self.assertIn("no category source labels are available", packet.blockers)


if __name__ == "__main__":
    unittest.main()
