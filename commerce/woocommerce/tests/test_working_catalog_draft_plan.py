import json
from pathlib import Path
import unittest

from phil_ai_os_woocommerce.working_catalog_draft_plan import (
    build_working_catalog_draft_plan,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"


class WorkingCatalogDraftPlanTests(unittest.TestCase):
    def load(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_current_subset_builds_draft_hidden_non_authorizing_plan(self):
        plan = build_working_catalog_draft_plan(self.load())
        self.assertFalse(plan.network_call_performed)
        self.assertFalse(plan.mutation_authorized)
        self.assertFalse(plan.production_publish_authorized)
        self.assertEqual(len(plan.products), 3)
        for product in plan.products:
            self.assertEqual(product.status, "draft")
            self.assertEqual(product.catalog_visibility, "hidden")
            self.assertIsNone(product.japanese_name)
            self.assertIn("japanese_name", product.unresolved_fields)
            self.assertIn("japanese_description", product.unresolved_fields)

    def test_confirmed_prices_and_corrected_sku_are_preserved(self):
        plan = build_working_catalog_draft_plan(self.load())
        by_key = {product.key: product for product in plan.products}

        moist = by_key["RCD-MCH-RD"]
        variations = {item.sku: item for item in moist.variations}
        self.assertEqual(variations["RCD-MCH-RD-15"].price_jpy, 3500)
        self.assertEqual(variations["RCD-MCH-RD-21"].price_jpy, 5500)
        self.assertNotIn("RCS-MCH-RD-21", variations)

        self.assertEqual(by_key["RCD-BAR-FMB"].price_jpy, 250)
        self.assertEqual(by_key["RCD-BRD-ENS-1"].price_jpy, 300)
        self.assertNotIn("price_jpy", by_key["RCD-BRD-ENS-1"].unresolved_fields)

    def test_unresolved_fulfillment_and_media_are_not_guessed(self):
        plan = build_working_catalog_draft_plan(self.load())
        by_key = {product.key: product for product in plan.products}

        moist = by_key["RCD-MCH-RD"]
        self.assertTrue(
            any(value.startswith("fulfillment:") for value in moist.unresolved_fields)
        )
        self.assertIn("verified_media_ingestion_reference", moist.unresolved_fields)

        bar = by_key["RCD-BAR-FMB"]
        self.assertIn(
            "fulfillment:multiple temperature modes require owner classification",
            bar.unresolved_fields,
        )
        self.assertIn(
            "fulfillment:quantity-dependent package rule requires final package policy",
            bar.unresolved_fields,
        )

        ens = by_key["RCD-BRD-ENS-1"]
        self.assertIn(
            "fulfillment:quantity-dependent package rule requires final package policy",
            ens.unresolved_fields,
        )


if __name__ == "__main__":
    unittest.main()
