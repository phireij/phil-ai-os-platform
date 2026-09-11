import copy
import unittest

from phil_ai_os_woocommerce.catalog_dry_run import plan_catalog_product_reconciliation
from phil_ai_os_woocommerce.catalog_readiness import evaluate_catalog_tax_readiness
from phil_ai_os_woocommerce.models import ContractValidationError, ProductRecord


def approved_variable_intake():
    return {
        "schema_version": "1.0",
        "environment": "pre-production",
        "package_state": "approved",
        "catalog_approved": True,
        "catalog_approval_ref": "decision://catalog/variable-contract-test",
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
                "source_ref": "owner-media://cake-primary",
                "alt": {"en": "Chocolate cake", "ja": "チョコレートケーキ"},
                "role": "primary",
                "position": 0,
            }
        ],
        "products": [
            {
                "sku": "RCD-MCH-RD",
                "product_type": "variable",
                "name": {"en": "Moist Chocolate Round Cake", "ja": "モイストチョコレートケーキ"},
                "description": {"en": "Approved description", "ja": "承認済み説明"},
                "slug": {"en": "moist-chocolate-round", "ja": "moist-chocolate-round-ja"},
                "regular_price": None,
                "variations": [
                    {
                        "sku": "RCD-MCH-RD-15",
                        "regular_price": "3500",
                        "attributes": {"size_cm": "15"},
                    },
                    {
                        "sku": "RCD-MCH-RD-21",
                        "regular_price": "5500",
                        "attributes": {"size_cm": "21"},
                    },
                ],
                "currency": "JPY",
                "fulfillment": {
                    "shipping_class": "cool-80",
                    "temperature_modes": ["frozen"],
                    "pickup_allowed": True,
                    "delivery_allowed": True,
                    "requires_order_approval": True,
                },
                "status": "draft",
                "visibility": "hidden",
                "category_keys": ["cakes"],
                "media_keys": ["cake-primary"],
                "source": "owner-approved-catalog",
                "source_updated_at": "2026-09-12T06:00:00+09:00",
                "approval_state": "approved",
                "price_includes_tax": True,
                "tax_class_candidate": "exempt",
            }
        ],
        "tax_decision": {
            "taxable_business_status": "exempt",
            "qualified_invoice_status": "not_registered",
            "qualified_invoice_registration_number": None,
            "yamato_shipping_separately_charged": "yes",
            "cod_fee_treatment": "not_offered",
            "implementation_route": "tax_disabled_candidate",
            "decision_evidence_ref": "ops/readiness/tax-test.json",
        },
        "mutation_authorized": False,
        "production_publish_authorized": False,
    }


class VariableProductContractTests(unittest.TestCase):
    def test_variable_parent_projects_attributes_and_separate_variation_skus(self):
        raw = approved_variable_intake()["products"][0]
        product = ProductRecord.from_mapping(raw)

        self.assertEqual(product.product_type, "variable")
        self.assertEqual(
            product.all_skus(),
            ("RCD-MCH-RD", "RCD-MCH-RD-15", "RCD-MCH-RD-21"),
        )
        parent = product.to_wc_payload("en")
        self.assertEqual(parent["type"], "variable")
        self.assertNotIn("regular_price", parent)
        self.assertEqual(
            parent["attributes"],
            [
                {
                    "name": "size_cm",
                    "visible": True,
                    "variation": True,
                    "options": ["15", "21"],
                }
            ],
        )
        self.assertEqual(
            product.variation_payloads(),
            (
                {
                    "sku": "RCD-MCH-RD-15",
                    "regular_price": "3500",
                    "attributes": [{"name": "size_cm", "option": "15"}],
                },
                {
                    "sku": "RCD-MCH-RD-21",
                    "regular_price": "5500",
                    "attributes": [{"name": "size_cm", "option": "21"}],
                },
            ),
        )

    def test_variable_parent_price_and_duplicate_variations_fail_closed(self):
        raw = approved_variable_intake()["products"][0]

        with_parent_price = copy.deepcopy(raw)
        with_parent_price["regular_price"] = "3500"
        with self.assertRaisesRegex(ContractValidationError, "parent regular_price must be null"):
            ProductRecord.from_mapping(with_parent_price)

        duplicate_sku = copy.deepcopy(raw)
        duplicate_sku["variations"][1]["sku"] = "RCD-MCH-RD-15"
        with self.assertRaisesRegex(ContractValidationError, "variation SKUs must be unique"):
            ProductRecord.from_mapping(duplicate_sku)

        duplicate_combination = copy.deepcopy(raw)
        duplicate_combination["variations"][1]["attributes"] = {"size_cm": "15"}
        with self.assertRaisesRegex(
            ContractValidationError, "variation attribute combinations must be unique"
        ):
            ProductRecord.from_mapping(duplicate_combination)

    def test_simple_products_remain_backward_compatible_and_reject_variations(self):
        raw = copy.deepcopy(approved_variable_intake()["products"][0])
        raw["sku"] = "SIMPLE-001"
        raw.pop("product_type")
        raw["regular_price"] = "500"
        raw["variations"] = []
        product = ProductRecord.from_mapping(raw)
        self.assertEqual(product.product_type, "simple")
        self.assertEqual(product.to_wc_payload("en")["regular_price"], "500")

        raw["variations"] = [
            {"sku": "SIMPLE-001-A", "regular_price": "500", "attributes": {"size": "A"}}
        ]
        with self.assertRaisesRegex(ContractValidationError, "simple products cannot declare variations"):
            ProductRecord.from_mapping(raw)

    def test_catalog_readiness_detects_duplicate_parent_or_variation_skus_globally(self):
        payload = approved_variable_intake()
        duplicate = copy.deepcopy(payload["products"][0])
        duplicate["sku"] = "RCD-MCH-RD-15"
        duplicate["product_type"] = "simple"
        duplicate["regular_price"] = "300"
        duplicate["variations"] = []
        duplicate["slug"] = {"en": "duplicate", "ja": "duplicate-ja"}
        payload["products"].append(duplicate)

        readiness = evaluate_catalog_tax_readiness(payload)
        self.assertFalse(readiness.catalog_ready)
        self.assertIn("duplicate product SKU: RCD-MCH-RD-15", readiness.blockers)

    def test_dry_run_plans_parent_and_each_variation_without_authority(self):
        payload = approved_variable_intake()
        plan = plan_catalog_product_reconciliation(payload, [])
        self.assertEqual(plan.as_dict()["counts"], {"create": 1, "update": 0, "noop": 0})
        self.assertEqual(
            plan.as_dict()["variation_counts"],
            {"create": 2, "update": 0, "noop": 0},
        )
        self.assertEqual(
            [item.sku for item in plan.variations],
            ["RCD-MCH-RD-15", "RCD-MCH-RD-21"],
        )
        self.assertTrue(all(item.network_call is False for item in plan.variations))
        self.assertTrue(all(item.mutation_authorized is False for item in plan.variations))

    def test_dry_run_detects_noop_and_changed_variation(self):
        payload = approved_variable_intake()
        product = ProductRecord.from_mapping(payload["products"][0])
        parent = product.to_wc_payload("en")
        parent["id"] = 91
        parent["variations"] = []
        for remote_id, variation in enumerate(product.variation_payloads(), start=901):
            expanded = copy.deepcopy(variation)
            expanded["id"] = remote_id
            parent["variations"].append(expanded)
        parent["variations"][1]["regular_price"] = "5400"

        plan = plan_catalog_product_reconciliation(payload, [parent])
        self.assertEqual(plan.products[0].action, "noop")
        self.assertEqual(
            [(item.sku, item.action) for item in plan.variations],
            [("RCD-MCH-RD-15", "noop"), ("RCD-MCH-RD-21", "update")],
        )

    def test_remote_variation_snapshot_requires_expanded_objects_and_ids(self):
        payload = approved_variable_intake()
        product = ProductRecord.from_mapping(payload["products"][0])
        parent = product.to_wc_payload("en")
        parent["id"] = 91
        parent["variations"] = [901, 902]
        with self.assertRaisesRegex(ContractValidationError, "variation 1 must be an expanded object"):
            plan_catalog_product_reconciliation(payload, [parent])


if __name__ == "__main__":
    unittest.main()
