from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools_plan_preproduction_catalog_changes.py"
spec = importlib.util.spec_from_file_location("catalog_plan", SCRIPT)
catalog_plan = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(catalog_plan)


def _snapshot() -> dict:
    return {
        "schema_version": "1.0",
        "scope": "woocommerce_catalog_metadata_read_only",
        "captured_at": "2026-09-07T00:00:00+09:00",
        "network_read_only": True,
        "mutation_authorized": False,
        "production_publish_authorized": False,
        "categories": [{"name": "Cakes", "slug": "cakes"}],
        "products": [
            {
                "sku": "SKU-1",
                "name": "Cake",
                "slug": "cake",
                "regular_price": "1000",
                "status": "draft",
                "catalog_visibility": "hidden",
                "shipping_class": "",
                "categories": [{"slug": "cakes"}],
            }
        ],
    }


class CatalogSnapshotCategoryReferenceIntegrityTests(unittest.TestCase):
    def test_duplicate_product_category_slug_is_rejected(self):
        snapshot = _snapshot()
        snapshot["products"][0]["categories"].append({"slug": "cakes"})
        blockers = catalog_plan._validate_snapshot(snapshot)
        self.assertIn("snapshot product[1] contains duplicate category slug: cakes", blockers)

    def test_unknown_product_category_slug_is_rejected(self):
        snapshot = _snapshot()
        snapshot["products"][0]["categories"] = [{"slug": "missing"}]
        blockers = catalog_plan._validate_snapshot(snapshot)
        self.assertIn("snapshot product[1] references unknown category slug: missing", blockers)

    def test_known_unique_product_category_slug_is_accepted(self):
        blockers = catalog_plan._validate_snapshot(_snapshot())
        self.assertEqual([], blockers)


if __name__ == "__main__":
    unittest.main()
