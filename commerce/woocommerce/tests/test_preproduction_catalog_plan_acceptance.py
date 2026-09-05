import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools_validate_preproduction_catalog_plan.py"
spec = importlib.util.spec_from_file_location("catalog_plan_acceptance", MODULE_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(validator)


class CatalogPlanAcceptanceTests(unittest.TestCase):
    def safe_plan(self):
        return {
            "version": "ruby-preproduction-catalog-dry-run-plan-v1",
            "plan_only": True,
            "network_calls_performed": False,
            "owner_package_ready": True,
            "snapshot_accepted": True,
            "ready_for_controlled_review": True,
            "blockers": [],
            "category_actions": [
                {"action": "create_candidate", "desired": {"key": "cakes"}, "changes": ["missing_in_snapshot"]}
            ],
            "product_actions": [
                {"action": "update_candidate", "sku": "OWNER-001", "desired": {}, "changes": ["regular_price"]}
            ],
            "existing_unmatched_skus": ["LEGACY-001"],
            "automatic_deletions_planned": False,
            "media_reconciliation_requires_review": True,
            "mutation_authorized": False,
            "production_publish_authorized": False,
        }

    def test_safe_plan_is_accepted_only_for_human_review(self):
        result = validator.validate_plan(self.safe_plan())
        self.assertTrue(result["accepted_for_human_review"])
        self.assertEqual(result["blockers"], [])
        self.assertFalse(result["mutation_authorized"])
        self.assertFalse(result["production_publish_authorized"])
        self.assertFalse(result["execution_authorized"])

    def test_delete_action_is_rejected(self):
        plan = self.safe_plan()
        plan["product_actions"].append({"action": "delete", "sku": "LEGACY-001", "changes": []})
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertTrue(any("forbidden action" in blocker for blocker in result["blockers"]))

    def test_authority_expansion_is_rejected(self):
        plan = self.safe_plan()
        plan["mutation_authorized"] = True
        plan["production_publish_authorized"] = True
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertTrue(any("mutation authority" in blocker for blocker in result["blockers"]))
        self.assertTrue(any("publication authority" in blocker for blocker in result["blockers"]))
        self.assertFalse(result["mutation_authorized"])
        self.assertFalse(result["execution_authorized"])

    def test_automatic_deletion_flag_is_rejected_even_without_delete_action(self):
        plan = self.safe_plan()
        plan["automatic_deletions_planned"] = True
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertTrue(any("automatic deletion" in blocker for blocker in result["blockers"]))

    def test_media_review_cannot_be_bypassed(self):
        plan = self.safe_plan()
        plan["media_reconciliation_requires_review"] = False
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertTrue(any("media reconciliation" in blocker for blocker in result["blockers"]))

    def test_plan_with_source_blockers_is_rejected(self):
        plan = self.safe_plan()
        plan["blockers"] = ["existing snapshot contains SKUs absent from owner package; no deletion is planned"]
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertTrue(any("carries blockers" in blocker for blocker in result["blockers"]))

    def test_plan_not_ready_for_controlled_review_is_rejected(self):
        plan = self.safe_plan()
        plan["ready_for_controlled_review"] = False
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertTrue(any("ready for controlled review" in blocker for blocker in result["blockers"]))

    def test_unready_owner_package_or_snapshot_is_rejected(self):
        plan = self.safe_plan()
        plan["owner_package_ready"] = False
        plan["snapshot_accepted"] = False
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertTrue(any("owner package" in blocker for blocker in result["blockers"]))
        self.assertTrue(any("snapshot" in blocker for blocker in result["blockers"]))

    def test_plan_blockers_must_be_non_empty_strings(self):
        plan = self.safe_plan()
        plan["blockers"] = [""]
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertTrue(any("non-empty strings" in blocker for blocker in result["blockers"]))


if __name__ == "__main__":
    unittest.main()
