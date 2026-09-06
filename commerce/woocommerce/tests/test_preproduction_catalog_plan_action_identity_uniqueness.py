import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools_validate_preproduction_catalog_plan.py"
spec = importlib.util.spec_from_file_location("catalog_plan_identity_acceptance", MODULE_PATH)
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
        "category_actions": [
            {
                "action": "create_candidate",
                "desired": {
                    "key": "cakes",
                    "name": "Cakes",
                    "slug": "cakes",
                    "parent_key": None,
                },
                "changes": ["missing_in_snapshot"],
            }
        ],
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
                    "shipping_class": "yamato-cool",
                    "category_slugs": ["cakes"],
                    "media_keys": ["owner-001-main"],
                },
                "changes": ["regular_price"],
            }
        ],
        "existing_unmatched_skus": [],
        "automatic_deletions_planned": False,
        "media_reconciliation_requires_review": True,
        "mutation_authorized": False,
        "production_publish_authorized": False,
    }


class CatalogPlanActionIdentityUniquenessTests(unittest.TestCase):
    def test_duplicate_category_action_key_is_rejected(self):
        plan = safe_plan()
        duplicate = copy.deepcopy(plan["category_actions"][0])
        duplicate["desired"]["slug"] = "cakes-second"
        plan["category_actions"].append(duplicate)
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertIn("duplicate category action key: cakes", result["blockers"])

    def test_duplicate_category_action_slug_is_rejected(self):
        plan = safe_plan()
        duplicate = copy.deepcopy(plan["category_actions"][0])
        duplicate["desired"]["key"] = "special-cakes"
        plan["category_actions"].append(duplicate)
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertIn("duplicate category action slug: cakes", result["blockers"])

    def test_duplicate_product_action_sku_is_rejected(self):
        plan = safe_plan()
        duplicate = copy.deepcopy(plan["product_actions"][0])
        duplicate["desired"]["slug"] = "owner-product-second"
        plan["product_actions"].append(duplicate)
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertIn("duplicate product action SKU: OWNER-001", result["blockers"])

    def test_duplicate_product_action_slug_is_rejected(self):
        plan = safe_plan()
        duplicate = copy.deepcopy(plan["product_actions"][0])
        duplicate["sku"] = "OWNER-002"
        duplicate["desired"]["sku"] = "OWNER-002"
        plan["product_actions"].append(duplicate)
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertIn("duplicate product action slug: owner-product", result["blockers"])

    def test_distinct_action_identities_remain_reviewable(self):
        plan = safe_plan()
        second_category = copy.deepcopy(plan["category_actions"][0])
        second_category["desired"].update({"key": "special-cakes", "name": "Special Cakes", "slug": "special-cakes"})
        plan["category_actions"].append(second_category)
        second_product = copy.deepcopy(plan["product_actions"][0])
        second_product["sku"] = "OWNER-002"
        second_product["desired"].update({"sku": "OWNER-002", "name": "Owner Product 2", "slug": "owner-product-2"})
        plan["product_actions"].append(second_product)
        result = validator.validate_plan(plan)
        self.assertTrue(result["accepted_for_human_review"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["mutation_authorized"])
        self.assertFalse(result["production_publish_authorized"])


if __name__ == "__main__":
    unittest.main()
