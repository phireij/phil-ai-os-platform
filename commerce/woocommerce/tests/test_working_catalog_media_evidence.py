import json
from pathlib import Path
import unittest

from phil_ai_os_woocommerce.working_catalog_media_evidence import (
    build_working_catalog_media_evidence_packet,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"


class WorkingCatalogMediaEvidencePacketTests(unittest.TestCase):
    def load(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_owner_source_attachment_state_is_preserved_but_not_promoted(self):
        packet = build_working_catalog_media_evidence_packet(self.load())
        by_key = {item.product_key: item for item in packet.items}

        self.assertEqual(by_key["RCD-BAR-FMB"].source_state, "attached_in_owner_source")
        self.assertEqual(by_key["RCD-BRD-ENS-1"].source_state, "attached_in_owner_source")
        self.assertIsNone(by_key["RCD-BAR-FMB"].verified_media_reference)
        self.assertFalse(by_key["RCD-BAR-FMB"].primary_media_confirmed)

    def test_missing_media_source_state_is_explicit(self):
        packet = build_working_catalog_media_evidence_packet(self.load())
        self.assertIn("RCD-MCH-RD: media source state is missing", packet.blockers)

    def test_existing_owner_attachment_still_requires_verified_ingestion_reference(self):
        packet = build_working_catalog_media_evidence_packet(self.load())
        self.assertIn(
            "RCD-BAR-FMB: verified media ingestion reference is unresolved",
            packet.blockers,
        )
        self.assertIn(
            "RCD-BRD-ENS-1: verified media ingestion reference is unresolved",
            packet.blockers,
        )

    def test_packet_never_grants_media_or_production_authority(self):
        packet = build_working_catalog_media_evidence_packet(self.load())
        self.assertFalse(packet.ready_for_media_ingestion_review)
        self.assertFalse(packet.network_call_performed)
        self.assertFalse(packet.mutation_authorized)
        self.assertFalse(packet.production_publish_authorized)
        self.assertIn(
            "primary media selection and verified ingestion references require review",
            packet.blockers,
        )

    def test_empty_catalog_fails_closed(self):
        payload = self.load()
        payload["working_products"] = []
        packet = build_working_catalog_media_evidence_packet(payload)
        self.assertEqual(packet.items, ())
        self.assertFalse(packet.ready_for_media_ingestion_review)
        self.assertIn("catalog contains no products", packet.blockers)


if __name__ == "__main__":
    unittest.main()
