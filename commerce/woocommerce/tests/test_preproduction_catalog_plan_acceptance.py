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
                {
                    "action": "create_candidate",
                    "desired": {"key": "cakes", "name": "Cakes", "slug": "cakes", "parent_key": None},
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
                        "catalog_visibility": "visible",
                        "shipping_class": "yamato-cool",
                        "category_slugs": ["cakes"],
                        "media_keys": ["owner-001-main"],
                    },
                    "changes": ["regular_price"],
                }
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

    def test_changes_must_be_meaningful_and_semantically_match_action(self):
        cases = [
            ("product_actions", 0, [""], "non-empty strings"),
            ("product_actions", 0, ["regular_price", "regular_price"], "duplicates"),
            ("product_actions", 0, [], "at least one change"),
            ("product_actions", 0, ["missing_in_snapshot"], "cannot include missing_in_snapshot"),
            ("category_actions", 0, [], "must carry at least one change"),
        ]
        for collection, index, changes, expected in cases:
            with self.subTest(collection=collection, changes=changes):
                plan = self.safe_plan()
                plan[collection][index]["changes"] = changes
                result = validator.validate_plan(plan)
                self.assertFalse(result["accepted_for_human_review"])
                self.assertTrue(any(expected in blocker for blocker in result["blockers"]))

    def test_noop_must_have_no_changes(self):
        plan = self.safe_plan()
        action = plan["product_actions"][0]
        action["action"] = "noop"
        action["changes"] = ["regular_price"]
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertTrue(any("noop action must not carry changes" in blocker for blocker in result["blockers"]))

    def test_action_identity_and_desired_payload_are_required(self):
        cases = [
            (lambda plan: plan["category_actions"][0]["desired"].update({"slug": ""}), "desired.slug"),
            (lambda plan: plan["product_actions"][0].update({"sku": ""}), ".sku must be a non-empty string"),
            (lambda plan: plan["product_actions"][0]["desired"].update({"sku": "OTHER-001"}), "must match action sku"),
            (lambda plan: plan["product_actions"][0]["desired"].update({"category_slugs": [""]}), "category_slugs"),
            (lambda plan: plan["product_actions"][0]["desired"].update({"media_keys": "owner-main"}), "media_keys"),
        ]
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                plan = self.safe_plan()
                mutate(plan)
                result = validator.validate_plan(plan)
                self.assertFalse(result["accepted_for_human_review"])
                self.assertTrue(any(expected in blocker for blocker in result["blockers"]))

    def test_existing_unmatched_skus_must_be_unique(self):
        plan = self.safe_plan()
        plan["existing_unmatched_skus"] = ["LEGACY-001", "LEGACY-001"]
        result = validator.validate_plan(plan)
        self.assertFalse(result["accepted_for_human_review"])
        self.assertTrue(any("must not contain duplicates" in blocker for blocker in result["blockers"]))


if __name__ == "__main__":
    unittest.main()
