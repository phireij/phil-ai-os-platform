import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools_plan_preproduction_catalog_changes.py"
spec = importlib.util.spec_from_file_location("catalog_dry_run_planner", MODULE_PATH)
planner = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(planner)


class PreproductionCatalogDryRunPlannerTests(unittest.TestCase):
    def ready_package(self):
        payload = json.loads((ROOT / "fixtures/production-catalog-intake.template.json").read_text(encoding="utf-8"))
        payload["catalog_scope"]["scope_complete_for_intended_initial_launch"] = True
        payload.update(
            {
                "package_state": "approved",
                "catalog_approved": True,
                "catalog_approval_ref": "decision://owner/catalog/approved-2026-09-04",
                "categories": [
                    {
                        "key": "cakes",
                        "name": {"en": "Cakes", "ja": "ケーキ"},
                        "slug": {"en": "cakes", "ja": "cakes-ja"},
                        "parent_key": None,
                    }
                ],
                "media": [
                    {
                        "key": "cake-primary",
                        "source_ref": "verified-media://owner/cake-primary",
                        "alt": {"en": "Cake", "ja": "ケーキ"},
                        "role": "primary",
                        "position": 0,
                    }
                ],
                "products": [
                    {
                        "sku": "OWNER-001",
                        "name": {"en": "Owner Cake", "ja": "オーナーケーキ"},
                        "description": {"en": "Owner approved cake", "ja": "オーナー承認済みケーキ"},
                        "slug": {"en": "owner-cake", "ja": "owner-cake-ja"},
                        "regular_price": "500",
                        "currency": "JPY",
                        "fulfillment": {
                            "shipping_class": "cool-60",
                            "temperature_modes": ["chilled"],
                            "pickup_allowed": True,
                            "delivery_allowed": True,
                            "requires_order_approval": True,
                        },
                        "status": "draft",
                        "visibility": "hidden",
                        "category_keys": ["cakes"],
                        "media_keys": ["cake-primary"],
                        "source": "owner-approved-catalog-2026-09-04",
                        "source_updated_at": "2026-09-04T12:00:00+09:00",
                        "approval_state": "approved",
                        "price_includes_tax": True,
                        "tax_class_candidate": "pending",
                    }
                ],
            }
        )
        return payload

    def snapshot(self):
        return {
            "schema_version": "1.0",
            "captured_at": "2026-09-04T03:00:00Z",
            "scope": "woocommerce_catalog_metadata_read_only",
            "network_read_only": True,
            "mutation_authorized": False,
            "production_publish_authorized": False,
            "products": [],
            "categories": [],
        }

    def test_ready_owner_package_against_empty_snapshot_proposes_creates_only(self):
        result = planner.build_plan(self.ready_package(), self.snapshot())
        self.assertTrue(result["ready_for_controlled_review"])
        self.assertEqual(result["category_actions"][0]["action"], "create_candidate")
        self.assertEqual(result["product_actions"][0]["action"], "create_candidate")
        self.assertFalse(result["automatic_deletions_planned"])
        self.assertFalse(result["mutation_authorized"])
        self.assertFalse(result["production_publish_authorized"])
        self.assertFalse(result["network_calls_performed"])

    def test_existing_unmatched_sku_is_review_only_never_delete(self):
        snapshot = self.snapshot()
        snapshot["products"] = [{"id": 99, "sku": "LEGACY-001"}]
        result = planner.build_plan(self.ready_package(), snapshot)
        self.assertEqual(result["existing_unmatched_skus"], ["LEGACY-001"])
        self.assertTrue(any("no deletion is planned" in blocker for blocker in result["blockers"]))
        self.assertFalse(result["automatic_deletions_planned"])

    def test_existing_product_differences_become_update_candidate(self):
        snapshot = self.snapshot()
        snapshot["categories"] = [{"id": 7, "name": "Cakes", "slug": "cakes", "parent": 0, "count": 1}]
        snapshot["products"] = [
            {
                "id": 11,
                "sku": "OWNER-001",
                "name": "Old Name",
                "slug": "owner-cake",
                "regular_price": "450",
                "status": "draft",
                "catalog_visibility": "hidden",
                "shipping_class": "cool-60",
                "categories": [{"id": 7, "name": "Cakes", "slug": "cakes"}],
                "images": [],
            }
        ]
        result = planner.build_plan(self.ready_package(), snapshot)
        action = result["product_actions"][0]
        self.assertEqual(action["action"], "update_candidate")
        self.assertIn("name", action["changes"])
        self.assertIn("regular_price", action["changes"])
        self.assertIn("media_requires_source_ref_reconciliation", action["changes"])

    def test_pending_owner_package_blocks_plan(self):
        pending = json.loads((ROOT / "fixtures/production-catalog-intake.template.json").read_text(encoding="utf-8"))
        result = planner.build_plan(pending, self.snapshot())
        self.assertFalse(result["ready_for_controlled_review"])
        self.assertFalse(result["mutation_authorized"])
        self.assertTrue(any("owner catalog package is not ready" in blocker for blocker in result["blockers"]))

    def test_snapshot_with_authority_is_rejected(self):
        snapshot = self.snapshot()
        snapshot["mutation_authorized"] = True
        result = planner.build_plan(self.ready_package(), snapshot)
        self.assertFalse(result["ready_for_controlled_review"])
        self.assertTrue(any("must not carry mutation authority" in blocker for blocker in result["blockers"]))
        self.assertFalse(result["mutation_authorized"])


if __name__ == "__main__":
    unittest.main()
