import json
from pathlib import Path
import unittest

from phil_ai_os_woocommerce.working_catalog_gap_report import build_working_catalog_gap_report


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"


class WorkingCatalogGapReportTests(unittest.TestCase):
    def load(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_current_working_subset_is_not_production_ready(self):
        report = build_working_catalog_gap_report(self.load())
        self.assertFalse(report.production_ready)
        self.assertIn("catalog approval is missing", report.global_gaps)
        self.assertIn("initial launch subset is not owner-confirmed complete", report.global_gaps)

    def test_current_product_gaps_are_reported_without_invention(self):
        report = build_working_catalog_gap_report(self.load())
        by_key = {item.key: item.missing for item in report.product_gaps}

        self.assertIn("Japanese product name", by_key["RCD-MCH-RD"])
        self.assertIn("Japanese description", by_key["RCD-MCH-RD"])
        self.assertIn("final shipping/package class", by_key["RCD-MCH-RD"])

        self.assertIn("Japanese product name", by_key["RCD-BAR-FMB"])
        self.assertIn("final shipping/package class", by_key["RCD-BAR-FMB"])

        self.assertIn("JPY price", by_key["RCD-BRD-ENS-1"])
        self.assertIn("Japanese product name", by_key["RCD-BRD-ENS-1"])
        self.assertIn("final shipping/package class", by_key["RCD-BRD-ENS-1"])

    def test_report_does_not_grant_authority_when_catalog_fields_are_filled(self):
        payload = self.load()
        for product in payload["working_products"]:
            product["japanese_name"] = "仮"
            product["japanese_description"] = "仮"
            product["source_package_rule"] = "resolved"
            if product.get("price_jpy") is None and product.get("product_type") == "simple":
                product["price_jpy"] = 1
        report = build_working_catalog_gap_report(payload)
        self.assertFalse(report.production_ready)
        self.assertIn("production mutation authority is not granted", report.global_gaps)
        self.assertIn("production publication authority is not granted", report.global_gaps)


if __name__ == "__main__":
    unittest.main()
