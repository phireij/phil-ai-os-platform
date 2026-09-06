import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools_validate_preproduction_catalog_plan.py"
spec = importlib.util.spec_from_file_location("catalog_plan_reference_acceptance", MODULE_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(validator)


def safe_plan():
    return {
        "version": "ruby-preproduction-catalog-dry-run-plan-v1",
        "plan_only": True,
        "network_calls_performed": False,
        "owner_package_ready": True,
        "snapshot_accepted": True,
        "ready_for_controlled_review": True,
        "blockers": [],
        "category_actions": [],
        "product_actions": [
            {
                "action": "update_candidate",
                "sku": "OWNER-001",
                "desired": {
                    "sku": "OWNER-001",
                    "name": "Owner Product",
                    "slug": "owner-product",
                    "regular_price": "1200",
                    "status": "draft",
                    "catalog_visibility": "hidden",
                    "shipping_class": "cool-60",
                    "category_slugs": ["cakes", "special-cakes"],
                    "media_keys": ["owner-main", "owner-side"],
                },
                "changes": ["categories"],
            }
        ],
        "existing_unmatched_skus": [],
        "automatic_deletions_planned": False,
        "media_reconciliation_requires_review": True,
        "mutation_authorized": False,
        "production_publish_authorized": False,
    }


class CatalogPlanReferenceUniquenessTests(unittest.TestCase):
    def test_distinct_references_remain_reviewable(self):
        result = validator.validate_plan(safe_plan())
        self.assertTrue(result["accepted_for_human_review"])
        self.assertFalse(result["execution_authorized"])

    def test_duplicate_category_slugs_are_rejected(self):
        plan = safe_plan()
        plan["product_actions"][0]["desired"]["category_slugs"] = ["cakes", "cakes"]
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertTrue(any("category_slugs must not contain duplicates" in blocker for blocker in result["blockers"]))

    def test_duplicate_media_keys_are_rejected(self):
        plan = safe_plan()
        plan["product_actions"][0]["desired"]["media_keys"] = ["owner-main", "owner-main"]
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertTrue(any("media_keys must not contain duplicates" in blocker for blocker in result["blockers"]))

    def test_whitespace_normalized_duplicates_are_rejected(self):
        plan = safe_plan()
        plan["product_actions"][0]["desired"]["category_slugs"] = ["cakes", " cakes "]
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertTrue(any("category_slugs must not contain duplicates" in blocker for blocker in result["blockers"]))


if __name__ == "__main__":
    unittest.main()
