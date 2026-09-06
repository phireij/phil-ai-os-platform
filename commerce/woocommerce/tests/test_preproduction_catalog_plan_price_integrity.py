import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools_validate_preproduction_catalog_plan.py"
spec = importlib.util.spec_from_file_location("catalog_plan_price_acceptance", MODULE_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(validator)


def safe_plan(price="1200"):
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
                    "regular_price": price,
                    "status": "draft",
                    "catalog_visibility": "hidden",
                    "shipping_class": "cool-60",
                    "category_slugs": [],
                    "media_keys": [],
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


class CatalogPlanPriceIntegrityTests(unittest.TestCase):
    def test_valid_non_negative_decimal_prices_remain_reviewable(self):
        for price in ("0", "500", "1200.50"):
            with self.subTest(price=price):
                result = validator.validate_plan(safe_plan(price))
                self.assertTrue(result["accepted_for_human_review"])
                self.assertFalse(result["execution_authorized"])

    def test_non_numeric_negative_or_non_finite_prices_are_rejected(self):
        for price in ("free", "-1", "NaN", "Infinity", "-Infinity"):
            with self.subTest(price=price):
                result = validator.validate_plan(safe_plan(price))
                self.assertFalse(result["accepted_for_human_review"])
                self.assertTrue(
                    any("regular_price must be a non-negative decimal string" in blocker for blocker in result["blockers"])
                )
                self.assertFalse(result["mutation_authorized"])
                self.assertFalse(result["production_publish_authorized"])
                self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
