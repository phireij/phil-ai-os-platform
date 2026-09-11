import json
from pathlib import Path
import unittest

from phil_ai_os_woocommerce.working_catalog_subset import evaluate_working_catalog_subset


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"


class WorkingCatalogSubsetTests(unittest.TestCase):
    def load(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_current_subset_is_valid_for_preparation_only(self):
        result = evaluate_working_catalog_subset(self.load())
        self.assertTrue(result.valid_for_preparation)
        self.assertEqual(result.blockers, ())

    def test_subset_cannot_self_promote_to_complete_or_authorized(self):
        payload = self.load()
        payload["catalog_approved"] = True
        payload["catalog_scope"]["scope_complete_for_intended_initial_launch"] = True
        payload["mutation_authorized"] = True
        payload["production_publish_authorized"] = True
        result = evaluate_working_catalog_subset(payload)
        self.assertFalse(result.valid_for_preparation)
        self.assertIn("working subset must keep catalog_approved=false", result.blockers)
        self.assertIn("working subset must remain incomplete until owner confirmation", result.blockers)
        self.assertIn("working subset must keep mutation_authorized=false", result.blockers)
        self.assertIn("working subset must keep production_publish_authorized=false", result.blockers)

    def test_confirmed_moist_chocolate_21cm_correction_is_required(self):
        payload = self.load()
        variation = payload["working_products"][0]["variants"][1]
        variation["owner_correction_confirmed"] = False
        result = evaluate_working_catalog_subset(payload)
        self.assertFalse(result.valid_for_preparation)
        self.assertIn("21 cm SKU correction lacks explicit owner confirmation evidence", result.blockers)

    def test_structured_sku_evidence_is_required_even_if_legacy_flag_is_true(self):
        payload = self.load()
        payload["source_snapshot"]["field_evidence"] = [
            item
            for item in payload["source_snapshot"]["field_evidence"]
            if item.get("product_key") != "RCD-MCH-RD-21"
        ]
        result = evaluate_working_catalog_subset(payload)
        self.assertFalse(result.valid_for_preparation)
        self.assertIn(
            "field evidence: 21 cm SKU correction requires structured owner direct evidence",
            result.blockers,
        )

    def test_structured_ensaymada_price_evidence_is_required(self):
        payload = self.load()
        payload["source_snapshot"]["field_evidence"] = [
            item
            for item in payload["source_snapshot"]["field_evidence"]
            if item.get("product_key") != "RCD-BRD-ENS-1"
        ]
        result = evaluate_working_catalog_subset(payload)
        self.assertFalse(result.valid_for_preparation)
        self.assertIn(
            "field evidence: Cheezy Ensaymada ¥300 requires structured owner visual evidence",
            result.blockers,
        )

    def test_non_rcd_sku_fails_closed(self):
        payload = self.load()
        payload["working_products"][1]["sku"] = "BAR-FMB"
        result = evaluate_working_catalog_subset(payload)
        self.assertFalse(result.valid_for_preparation)
        self.assertIn("invalid Ruby SKU: BAR-FMB", result.blockers)

    def test_known_owner_blockers_cannot_be_silently_dropped(self):
        payload = self.load()
        payload["known_blockers"].remove("Japanese product names/descriptions are missing")
        result = evaluate_working_catalog_subset(payload)
        self.assertFalse(result.valid_for_preparation)
        self.assertIn(
            "working subset no longer records blocker: Japanese product names/descriptions are missing",
            result.blockers,
        )


if __name__ == "__main__":
    unittest.main()
