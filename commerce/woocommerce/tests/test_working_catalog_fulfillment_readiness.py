import json
from pathlib import Path
import unittest

from phil_ai_os_woocommerce.working_catalog_fulfillment_readiness import (
    evaluate_working_catalog_fulfillment_readiness,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"


class WorkingCatalogFulfillmentReadinessTests(unittest.TestCase):
    def load(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_current_subset_stays_fail_closed_for_final_classification(self):
        report = evaluate_working_catalog_fulfillment_readiness(self.load())
        self.assertFalse(report.ready_for_final_classification)
        self.assertFalse(report.production_mutation_authorized)

        by_key = {item.key: item for item in report.product_results}

        moist = by_key["RCD-MCH-RD"]
        self.assertEqual(moist.temperature_status, "resolved:frozen")
        self.assertEqual(moist.package_status, "missing")
        self.assertIn("final shipping/package class is missing", moist.blockers)

        bar = by_key["RCD-BAR-FMB"]
        self.assertEqual(bar.temperature_status, "ambiguous")
        self.assertEqual(bar.package_status, "quantity_dependent")
        self.assertIn("multiple temperature modes require owner classification", bar.blockers)
        self.assertIn("quantity-dependent package rule requires final package policy", bar.blockers)
        self.assertIn("ambient package candidate lacks physical-fit confirmation", bar.blockers)

        ens = by_key["RCD-BRD-ENS-1"]
        self.assertEqual(ens.temperature_status, "resolved:chilled")
        self.assertEqual(ens.package_status, "quantity_dependent")
        self.assertIn("quantity-dependent package rule requires final package policy", ens.blockers)

    def test_single_resolved_product_can_be_ready_without_granting_mutation(self):
        payload = {
            "working_products": [
                {
                    "sku": "RCD-TEST-ONE",
                    "delivery_allowed": True,
                    "source_temperature_marks": ["ambient"],
                    "source_package_rule": "ambient_60",
                }
            ]
        }
        report = evaluate_working_catalog_fulfillment_readiness(payload)
        self.assertTrue(report.ready_for_final_classification)
        self.assertFalse(report.production_mutation_authorized)

    def test_unknown_temperature_mark_is_invalid(self):
        payload = {
            "working_products": [
                {
                    "sku": "RCD-TEST-ONE",
                    "delivery_allowed": True,
                    "source_temperature_marks": ["room_temp_guess"],
                    "source_package_rule": "ambient_60",
                }
            ]
        }
        report = evaluate_working_catalog_fulfillment_readiness(payload)
        item = report.product_results[0]
        self.assertEqual(item.temperature_status, "invalid")
        self.assertFalse(report.ready_for_final_classification)
        self.assertIn("unsupported temperature mark(s): room_temp_guess", item.blockers)


if __name__ == "__main__":
    unittest.main()
