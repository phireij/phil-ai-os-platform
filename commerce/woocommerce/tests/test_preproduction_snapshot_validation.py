from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools_plan_preproduction_catalog_changes.py"
spec = importlib.util.spec_from_file_location("preproduction_catalog_plan", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def valid_snapshot():
    return {
        "schema_version": "1.0",
        "captured_at": "2026-09-05T03:30:00Z",
        "scope": "woocommerce_catalog_metadata_read_only",
        "network_read_only": True,
        "mutation_authorized": False,
        "production_publish_authorized": False,
        "products": [{"sku": "SKU-001", "name": "Cake"}],
        "categories": [{"slug": "cakes", "name": "Cakes"}],
    }


class PreproductionSnapshotValidationTests(unittest.TestCase):
    def test_valid_snapshot_has_no_blockers(self):
        self.assertEqual(module._validate_snapshot(valid_snapshot()), [])

    def test_missing_or_naive_capture_timestamp_fails_closed(self):
        snapshot = valid_snapshot()
        snapshot.pop("captured_at")
        self.assertIn(
            "snapshot captured_at must be a timezone-aware ISO timestamp",
            module._validate_snapshot(snapshot),
        )
        snapshot["captured_at"] = "2026-09-05T03:30:00"
        self.assertIn(
            "snapshot captured_at must be a timezone-aware ISO timestamp",
            module._validate_snapshot(snapshot),
        )

    def test_non_object_entries_fail_closed(self):
        snapshot = valid_snapshot()
        snapshot["products"] = ["SKU-001"]
        snapshot["categories"] = [123]
        blockers = module._validate_snapshot(snapshot)
        self.assertIn("snapshot product[1] must be an object", blockers)
        self.assertIn("snapshot category[1] must be an object", blockers)

    def test_missing_identity_fields_fail_closed(self):
        snapshot = valid_snapshot()
        snapshot["products"] = [{}]
        snapshot["categories"] = [{}]
        blockers = module._validate_snapshot(snapshot)
        self.assertIn("snapshot product[1] requires explicit SKU", blockers)
        self.assertIn("snapshot category[1] requires explicit slug", blockers)

    def test_duplicate_product_sku_fails_closed(self):
        snapshot = valid_snapshot()
        snapshot["products"] = [{"sku": "SKU-001"}, {"sku": "SKU-001"}]
        blockers = module._validate_snapshot(snapshot)
        self.assertIn("snapshot contains duplicate product SKU: SKU-001", blockers)

    def test_duplicate_category_slug_fails_closed(self):
        snapshot = valid_snapshot()
        snapshot["categories"] = [{"slug": "cakes"}, {"slug": "cakes"}]
        blockers = module._validate_snapshot(snapshot)
        self.assertIn("snapshot contains duplicate category slug: cakes", blockers)


if __name__ == "__main__":
    unittest.main()
