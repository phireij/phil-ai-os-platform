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
        self.assertIn(
            "Category: final category hierarchy, bilingual names, slugs, and mappings require approval",
            report.global_gaps,
        )
        self.assertIn(
            "Media: primary media selection and verified ingestion references require review",
            report.global_gaps,
        )

    def test_runtime_authority_is_not_a_catalog_completeness_gap(self):
        report = build_working_catalog_gap_report(self.load())
        self.assertNotIn("production mutation authority is not granted", report.global_gaps)
        self.assertNotIn("production publication authority is not granted", report.global_gaps)

        payload = self.load()
        payload["mutation_authorized"] = True
        payload["production_publish_authorized"] = True
        authorized = build_working_catalog_gap_report(payload)
        self.assertEqual(report.global_gaps, authorized.global_gaps)
        self.assertEqual(report.product_gaps, authorized.product_gaps)

    def test_current_product_gaps_are_reported_without_invention(self):
        report = build_working_catalog_gap_report(self.load())
        by_key = {item.key: item.missing for item in report.product_gaps}

        self.assertIn("Japanese product name", by_key["RCD-MCH-RD"])
        self.assertIn("Japanese description", by_key["RCD-MCH-RD"])
        self.assertIn("Fulfillment: final shipping/package class is missing", by_key["RCD-MCH-RD"])
        self.assertIn("Category: category source label is missing", by_key["RCD-MCH-RD"])
        self.assertIn("Media: media source state is missing", by_key["RCD-MCH-RD"])

        self.assertIn("Japanese product name", by_key["RCD-BAR-FMB"])
        self.assertIn(
            "Fulfillment: multiple temperature modes require owner classification",
            by_key["RCD-BAR-FMB"],
        )
        self.assertIn(
            "Fulfillment: quantity-dependent package rule requires final package policy",
            by_key["RCD-BAR-FMB"],
        )
        self.assertIn(
            "Fulfillment: ambient package candidate lacks physical-fit confirmation",
            by_key["RCD-BAR-FMB"],
        )
        self.assertIn("Media: verified media ingestion reference is unresolved", by_key["RCD-BAR-FMB"])

        self.assertNotIn("JPY price", by_key["RCD-BRD-ENS-1"])
        self.assertIn("Japanese product name", by_key["RCD-BRD-ENS-1"])
        self.assertIn(
            "Fulfillment: quantity-dependent package rule requires final package policy",
            by_key["RCD-BRD-ENS-1"],
        )
        self.assertIn("Media: verified media ingestion reference is unresolved", by_key["RCD-BRD-ENS-1"])

    def test_temperature_ambiguity_survives_even_if_package_rule_is_resolved(self):
        payload = self.load()
        bar = next(item for item in payload["working_products"] if item.get("sku") == "RCD-BAR-FMB")
        bar["source_package_rule"] = "ambient_size_60"
        report = build_working_catalog_gap_report(payload)
        by_key = {item.key: item.missing for item in report.product_gaps}
        self.assertIn(
            "Fulfillment: multiple temperature modes require owner classification",
            by_key["RCD-BAR-FMB"],
        )

    def test_unconfirmed_ambient_candidate_cannot_disappear_from_readiness(self):
        payload = self.load()
        bar = next(item for item in payload["working_products"] if item.get("sku") == "RCD-BAR-FMB")
        bar["source_temperature_marks"] = ["ambient"]
        bar["source_package_rule"] = "ambient_compact"
        bar["ambient_package_candidate_confirmed"] = False
        report = build_working_catalog_gap_report(payload)
        by_key = {item.key: item.missing for item in report.product_gaps}
        self.assertIn(
            "Fulfillment: ambient package candidate lacks physical-fit confirmation",
            by_key["RCD-BAR-FMB"],
        )

    def test_variable_product_media_gap_cannot_disappear_from_readiness(self):
        payload = self.load()
        cake = next(
            item for item in payload["working_products"] if item.get("parent_reference") == "RCD-MCH-RD"
        )
        self.assertIsNone(cake.get("photo_source_state"))
        report = build_working_catalog_gap_report(payload)
        by_key = {item.key: item.missing for item in report.product_gaps}
        self.assertIn("Media: media source state is missing", by_key["RCD-MCH-RD"])

    def test_missing_owner_evidence_is_a_global_readiness_gap(self):
        payload = self.load()
        payload["source_snapshot"]["field_evidence"] = [
            item
            for item in payload["source_snapshot"]["field_evidence"]
            if item.get("product_key") != "RCD-BRD-ENS-1"
        ]
        report = build_working_catalog_gap_report(payload)
        self.assertFalse(report.production_ready)
        self.assertIn(
            "owner evidence: Cheezy Ensaymada ¥300 requires structured owner visual evidence",
            report.global_gaps,
        )

    def test_corrected_sku_requires_structured_owner_evidence(self):
        payload = self.load()
        payload["source_snapshot"]["field_evidence"] = [
            item
            for item in payload["source_snapshot"]["field_evidence"]
            if item.get("product_key") != "RCD-MCH-RD-21"
        ]
        report = build_working_catalog_gap_report(payload)
        self.assertFalse(report.production_ready)
        self.assertIn(
            "owner evidence: 21 cm SKU correction requires structured owner direct evidence",
            report.global_gaps,
        )

    def test_empty_catalog_can_never_report_production_ready(self):
        payload = self.load()
        payload["working_products"] = []
        payload["catalog_approved"] = True
        payload["catalog_scope"]["scope_complete_for_intended_initial_launch"] = True
        payload["catalog_approval_ref"] = "owner-approval:test"
        payload["source_snapshot"]["field_evidence"] = []
        report = build_working_catalog_gap_report(payload)
        self.assertFalse(report.production_ready)
        self.assertIn("catalog contains no products", report.global_gaps)

    def test_invalid_or_duplicate_sku_blocks_production_readiness(self):
        payload = self.load()
        payload["working_products"][0]["variants"][0]["sku"] = "BAR-FMB"
        payload["working_products"][2]["sku"] = "RCD-BAR-FMB"
        report = build_working_catalog_gap_report(payload)
        self.assertFalse(report.production_ready)
        self.assertIn("invalid Ruby SKU: BAR-FMB", report.global_gaps)
        self.assertIn("duplicate Ruby SKU: RCD-BAR-FMB", report.global_gaps)

    def test_missing_drive_source_provenance_blocks_production_readiness(self):
        payload = self.load()
        payload["source_snapshot"].pop("drive_file_id", None)
        report = build_working_catalog_gap_report(payload)
        self.assertFalse(report.production_ready)
        self.assertIn("catalog source provenance is missing Drive file id", report.global_gaps)

    def test_missing_source_modified_timestamp_blocks_production_readiness(self):
        payload = self.load()
        payload["source_snapshot"].pop("observed_modified_at", None)
        report = build_working_catalog_gap_report(payload)
        self.assertFalse(report.production_ready)
        self.assertIn("catalog source provenance is missing observed modified timestamp", report.global_gaps)


if __name__ == "__main__":
    unittest.main()
