import csv
import io
import json
from pathlib import Path
import unittest

from phil_ai_os_woocommerce.working_catalog_owner_worksheet import (
    WORKSHEET_COLUMNS,
    build_working_catalog_owner_worksheet,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"


class WorkingCatalogOwnerWorksheetTests(unittest.TestCase):
    def load(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_current_subset_projects_parent_variations_and_simple_products(self):
        worksheet = build_working_catalog_owner_worksheet(self.load())
        self.assertEqual(WORKSHEET_COLUMNS, worksheet.columns)
        self.assertEqual(5, len(worksheet.rows))

        by_sku = {row["sku"]: row for row in worksheet.rows}
        parent = by_sku["RCD-MCH-RD"]
        self.assertEqual("variable_parent", parent["record_type"])
        self.assertEqual("variable", parent["product_type"])
        self.assertEqual("Moist Chocolate Round Cake", parent["english_name"])
        self.assertEqual("", parent["japanese_name"])
        self.assertEqual("", parent["price_jpy"])

        small = by_sku["RCD-MCH-RD-15"]
        large = by_sku["RCD-MCH-RD-21"]
        self.assertEqual("variation", small["record_type"])
        self.assertEqual("RCD-MCH-RD", small["parent_sku"])
        self.assertEqual('{"size_cm":15}', small["variant_attributes"])
        self.assertEqual("3500", small["price_jpy"])
        self.assertEqual("RCD-MCH-RD", large["parent_sku"])
        self.assertEqual('{"size_cm":21}', large["variant_attributes"])
        self.assertEqual("5500", large["price_jpy"])

        self.assertEqual("simple_product", by_sku["RCD-BAR-FMB"]["record_type"])
        self.assertEqual("250", by_sku["RCD-BAR-FMB"]["price_jpy"])
        self.assertEqual("simple_product", by_sku["RCD-BRD-ENS-1"]["record_type"])
        self.assertEqual("300", by_sku["RCD-BRD-ENS-1"]["price_jpy"])

    def test_unresolved_owner_fields_are_blank_not_invented(self):
        worksheet = build_working_catalog_owner_worksheet(self.load())
        product_rows = [row for row in worksheet.rows if row["record_type"] != "variation"]
        self.assertTrue(all(row["japanese_name"] == "" for row in product_rows))
        self.assertTrue(all(row["japanese_description"] == "" for row in product_rows))
        self.assertTrue(all(row["approved_category_key"] == "" for row in product_rows))
        self.assertTrue(all(row["primary_media_ref"] == "" for row in product_rows))
        self.assertTrue(all(row["shipping_class"] == "" for row in product_rows))
        self.assertTrue(all(row["final_temperature_mode"] == "" for row in product_rows))

    def test_product_rows_surface_current_owner_requirements(self):
        worksheet = build_working_catalog_owner_worksheet(self.load())
        by_sku = {row["sku"]: row for row in worksheet.rows}
        self.assertIn("Japanese product name", by_sku["RCD-MCH-RD"]["owner_action_requirements"])
        self.assertIn("Japanese description", by_sku["RCD-BAR-FMB"]["owner_action_requirements"])
        self.assertIn("Fulfillment:", by_sku["RCD-BRD-ENS-1"]["owner_action_requirements"])
        self.assertTrue(worksheet.global_requirements)

    def test_projection_is_non_authorizing(self):
        worksheet = build_working_catalog_owner_worksheet(self.load())
        self.assertFalse(worksheet.network_call_performed)
        self.assertFalse(worksheet.mutation_authorized)
        self.assertFalse(worksheet.production_publish_authorized)

    def test_rows_are_csv_serializable_with_stable_columns(self):
        worksheet = build_working_catalog_owner_worksheet(self.load())
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=worksheet.columns, extrasaction="raise")
        writer.writeheader()
        writer.writerows(worksheet.rows)
        rendered = buffer.getvalue()
        self.assertIn("record_type,parent_sku,sku,product_type", rendered)
        self.assertIn("RCD-MCH-RD-15", rendered)
        self.assertIn("RCD-BAR-FMB", rendered)

    def test_invalid_product_shape_fails_closed(self):
        payload = self.load()
        payload["working_products"][0]["product_type"] = "bundle"
        with self.assertRaisesRegex(ValueError, "unsupported product_type"):
            build_working_catalog_owner_worksheet(payload)


if __name__ == "__main__":
    unittest.main()
