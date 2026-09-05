import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools_validate_owner_catalog_package.py"
spec = importlib.util.spec_from_file_location("owner_catalog_validator", MODULE_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(validator)


class OwnerCatalogPackageValidatorTests(unittest.TestCase):
    def pending_template(self):
        return json.loads(
            (ROOT / "fixtures" / "production-catalog-intake.template.json").read_text(
                encoding="utf-8"
            )
        )

    def ready_package(self):
        payload = self.pending_template()
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

    def test_pending_template_reports_blockers_without_authority(self):
        result = validator.validate_package(self.pending_template())
        self.assertTrue(result["valid_contract"])
        self.assertFalse(result["scope_ready"])
        self.assertFalse(result["ready_for_preproduction_configuration"])
        self.assertIn("catalog approval is pending", result["blockers"])
        self.assertIn(
            "owner must confirm the submitted subset is complete for the intended initial launch",
            result["blockers"],
        )
        self.assertFalse(result["mutation_authorized"])
        self.assertFalse(result["production_publish_authorized"])

    def test_owner_complete_initial_launch_subset_can_be_ready_without_full_catalog(self):
        result = validator.validate_package(self.ready_package())
        self.assertTrue(result["valid_contract"])
        self.assertEqual(result["catalog_scope_type"], "initial_launch_subset")
        self.assertFalse(result["full_product_range_required_for_sprint3_closure"])
        self.assertTrue(result["scope_ready"])
        self.assertTrue(result["catalog_ready"])
        self.assertTrue(result["tax_decision_ready"])
        self.assertTrue(result["current_state_reconciled"])
        self.assertTrue(result["ready_for_preproduction_configuration"])
        self.assertEqual(result["blockers"], [])
        self.assertFalse(result["mutation_authorized"])
        self.assertFalse(result["production_publish_authorized"])

    def test_scope_must_not_claim_full_product_range_required(self):
        payload = self.ready_package()
        payload["catalog_scope"]["full_product_range_required_for_sprint3_closure"] = True
        result = validator.validate_package(payload)
        self.assertFalse(result["scope_ready"])
        self.assertFalse(result["ready_for_preproduction_configuration"])
        self.assertIn(
            "Sprint 3 catalog scope must not require Ruby's full product range",
            result["blockers"],
        )

    def test_scope_must_be_confirmed_complete_for_intended_initial_launch(self):
        payload = self.ready_package()
        payload["catalog_scope"]["scope_complete_for_intended_initial_launch"] = False
        result = validator.validate_package(payload)
        self.assertFalse(result["scope_ready"])
        self.assertFalse(result["ready_for_preproduction_configuration"])

    def test_stale_tax_posture_blocks_handoff(self):
        payload = self.ready_package()
        payload["tax_decision"]["taxable_business_status"] = "taxable"
        payload["tax_decision"]["implementation_route"] = "tax_tables_candidate"
        result = validator.validate_package(payload)
        self.assertFalse(result["ready_for_preproduction_configuration"])
        self.assertIn(
            "owner package taxable_business_status must match current exempt posture",
            result["blockers"],
        )

    def test_cod_drift_blocks_handoff(self):
        payload = self.ready_package()
        payload["tax_decision"]["cod_fee_treatment"] = "standard_rate"
        result = validator.validate_package(payload)
        self.assertFalse(result["ready_for_preproduction_configuration"])
        self.assertIn("owner package COD treatment must remain not_offered", result["blockers"])

    def test_unapproved_media_and_bad_timestamp_remain_blocked(self):
        payload = self.ready_package()
        payload["media"][0]["source_ref"] = "fixture://cake.jpg"
        payload["products"][0]["source_updated_at"] = "2026-09-04"
        result = validator.validate_package(payload)
        self.assertFalse(result["ready_for_preproduction_configuration"])
        self.assertTrue(any("unapproved source" in blocker for blocker in result["blockers"]))
        self.assertTrue(any("timezone-aware ISO timestamp" in blocker for blocker in result["blockers"]))

    def test_missing_internal_readiness_evidence_fails_closed(self):
        payload = self.ready_package()
        original_tax_evidence = validator.TAX_EVIDENCE
        try:
            validator.TAX_EVIDENCE = ROOT / "fixtures" / "missing-tax-readiness-evidence.json"
            result = validator.validate_package(payload)
        finally:
            validator.TAX_EVIDENCE = original_tax_evidence

        self.assertFalse(result["valid_contract"])
        self.assertFalse(result["current_state_reconciled"])
        self.assertFalse(result["ready_for_preproduction_configuration"])
        self.assertTrue(any("contract validation failed" in blocker for blocker in result["blockers"]))
        self.assertFalse(result["mutation_authorized"])
        self.assertFalse(result["production_publish_authorized"])

    def test_input_is_not_mutated(self):
        payload = self.ready_package()
        original = copy.deepcopy(payload)
        validator.validate_package(payload)
        self.assertEqual(payload, original)

    def test_authority_flag_expansion_is_invalid_contract(self):
        payload = self.ready_package()
        payload["mutation_authorized"] = True
        result = validator.validate_package(payload)
        self.assertFalse(result["valid_contract"])
        self.assertFalse(result["ready_for_preproduction_configuration"])
        self.assertFalse(result["mutation_authorized"])


if __name__ == "__main__":
    unittest.main()
