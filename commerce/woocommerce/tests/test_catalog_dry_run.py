import copy
import unittest

from phil_ai_os_woocommerce.catalog_dry_run import plan_catalog_product_reconciliation
from phil_ai_os_woocommerce.models import ContractValidationError, ProductRecord


def intake_package():
    return {
        "schema_version": "1.0",
        "environment": "pre-production",
        "package_state": "approved",
        "catalog_approved": True,
        "catalog_approval_ref": "decision://catalog/owner-approved",
        "catalog_scope": {
            "scope_type": "initial_launch_subset",
            "full_product_range_required_for_sprint3_closure": False,
            "additional_products_may_be_added_after_sprint3": True,
            "scope_complete_for_intended_initial_launch": True,
        },
        "source_contract": {
            "owner_source_required": True,
            "owner_approval_required": True,
            "source_updated_at_required": True,
            "bilingual_en_ja_required": True,
            "verified_media_source_required": True,
            "currency": "JPY",
            "intake_product_status": "draft",
            "intake_product_visibility": "hidden",
            "production_write_authority_granted_by_handoff": False,
        },
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
                "source_ref": "verified-media://cake-primary",
                "alt": {"en": "Cake", "ja": "ケーキ"},
                "role": "primary",
                "position": 0,
            }
        ],
        "products": [
            {
                "sku": "APPROVED-001",
                "name": {"en": "Approved Cake", "ja": "承認済みケーキ"},
                "description": {"en": "Approved description", "ja": "承認済み説明"},
                "slug": {"en": "approved-cake", "ja": "approved-cake-ja"},
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
                "source": "owner-approved-catalog",
                "source_updated_at": "2026-09-03T05:00:00+09:00",
                "approval_state": "approved",
                "price_includes_tax": True,
                "tax_class_candidate": "reduced_rate_food",
            }
        ],
        "tax_decision": {
            "taxable_business_status": "pending",
            "qualified_invoice_status": "pending",
            "qualified_invoice_registration_number": None,
            "yamato_shipping_separately_charged": "pending",
            "cod_fee_treatment": "pending",
            "implementation_route": "pending",
            "decision_evidence_ref": None,
        },
        "mutation_authorized": False,
        "production_publish_authorized": False,
    }


def desired_remote(payload):
    product = ProductRecord.from_mapping(payload["products"][0])
    remote = product.to_wc_payload("en")
    remote["id"] = 91
    return remote


class CatalogDryRunTests(unittest.TestCase):
    def test_missing_remote_product_plans_create_without_side_effect_authority(self):
        plan = plan_catalog_product_reconciliation(intake_package(), [])
        self.assertTrue(plan.catalog_ready)
        self.assertFalse(plan.tax_decision_ready)
        self.assertEqual(plan.products[0].action, "create")
        self.assertFalse(plan.network_call)
        self.assertFalse(plan.mutation_authorized)
        self.assertFalse(plan.production_publish_authorized)

    def test_identical_remote_product_plans_noop(self):
        payload = intake_package()
        plan = plan_catalog_product_reconciliation(payload, [desired_remote(payload)])
        self.assertEqual(plan.products[0].action, "noop")
        self.assertEqual(plan.products[0].remote_id, 91)
        self.assertEqual(
            plan.products[0].before_fingerprint,
            plan.products[0].after_fingerprint,
        )

    def test_changed_remote_product_plans_update_without_executing_it(self):
        payload = intake_package()
        remote = desired_remote(payload)
        remote["regular_price"] = "450"
        plan = plan_catalog_product_reconciliation(payload, [remote])
        self.assertEqual(plan.products[0].action, "update")
        self.assertFalse(plan.products[0].network_call)
        self.assertFalse(plan.products[0].mutation_authorized)

    def test_catalog_blockers_prevent_even_a_dry_run_plan(self):
        payload = intake_package()
        payload["catalog_approved"] = False
        with self.assertRaises(ContractValidationError):
            plan_catalog_product_reconciliation(payload, [])

    def test_duplicate_remote_sku_snapshot_fails_closed(self):
        payload = intake_package()
        remote = desired_remote(payload)
        with self.assertRaises(ContractValidationError):
            plan_catalog_product_reconciliation(payload, [remote, copy.deepcopy(remote)])

    def test_malformed_remote_snapshot_entries_fail_closed_with_contract_error(self):
        with self.assertRaisesRegex(
            ContractValidationError, "remote product snapshot entry 1 must be an object"
        ):
            plan_catalog_product_reconciliation(intake_package(), ["not-an-object"])

        with self.assertRaisesRegex(
            ContractValidationError, "remote product snapshot must be a sequence of objects"
        ):
            plan_catalog_product_reconciliation(intake_package(), "not-a-snapshot")

    def test_boolean_remote_id_is_not_accepted_as_integer_identity(self):
        payload = intake_package()
        remote = desired_remote(payload)
        remote["id"] = True
        with self.assertRaisesRegex(
            ContractValidationError, "remote product APPROVED-001 requires positive integer id"
        ):
            plan_catalog_product_reconciliation(payload, [remote])

    def test_plan_summary_is_deterministic_and_non_authorizing(self):
        payload = intake_package()
        summary = plan_catalog_product_reconciliation(payload, []).as_dict()
        self.assertEqual(summary["counts"], {"create": 1, "update": 0, "noop": 0})
        self.assertFalse(summary["network_call"])
        self.assertFalse(summary["mutation_authorized"])
        self.assertFalse(summary["production_publish_authorized"])


if __name__ == "__main__":
    unittest.main()
