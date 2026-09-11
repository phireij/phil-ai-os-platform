import copy
import json
from pathlib import Path
import unittest

from phil_ai_os_woocommerce.catalog_field_evidence import evaluate_field_evidence


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"


class CatalogFieldEvidenceTests(unittest.TestCase):
    def load(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_current_owner_evidence_is_structured_and_valid(self):
        result = evaluate_field_evidence(self.load())
        self.assertTrue(result.valid)
        self.assertEqual(result.blockers, ())

    def test_ensaymada_price_requires_matching_visual_evidence(self):
        payload = self.load()
        payload["source_snapshot"]["field_evidence"] = [
            item
            for item in payload["source_snapshot"]["field_evidence"]
            if item.get("product_key") != "RCD-BRD-ENS-1"
        ]
        result = evaluate_field_evidence(payload)
        self.assertFalse(result.valid)
        self.assertIn(
            "Cheezy Ensaymada ¥300 requires structured owner visual evidence",
            result.blockers,
        )

    def test_confirmed_sku_correction_requires_matching_direct_evidence(self):
        payload = self.load()
        payload["source_snapshot"]["field_evidence"] = [
            item
            for item in payload["source_snapshot"]["field_evidence"]
            if item.get("product_key") != "RCD-MCH-RD-21"
        ]
        result = evaluate_field_evidence(payload)
        self.assertFalse(result.valid)
        self.assertIn(
            "21 cm SKU correction requires structured owner direct evidence",
            result.blockers,
        )

    def test_duplicate_field_evidence_fails_closed(self):
        payload = self.load()
        payload["source_snapshot"]["field_evidence"].append(
            copy.deepcopy(payload["source_snapshot"]["field_evidence"][0])
        )
        result = evaluate_field_evidence(payload)
        self.assertFalse(result.valid)
        self.assertIn(
            "duplicate supplemental evidence for RCD-BRD-ENS-1.price_jpy",
            result.blockers,
        )

    def test_unapproved_evidence_type_fails_closed(self):
        payload = self.load()
        payload["source_snapshot"]["field_evidence"][0]["evidence_type"] = "model_inference"
        result = evaluate_field_evidence(payload)
        self.assertFalse(result.valid)
        self.assertTrue(any("unsupported" in blocker for blocker in result.blockers))


if __name__ == "__main__":
    unittest.main()
