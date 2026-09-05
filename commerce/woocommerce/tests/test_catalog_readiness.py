import copy
import json
from pathlib import Path
import unittest

from phil_ai_os_woocommerce.catalog_readiness import evaluate_catalog_tax_readiness
from phil_ai_os_woocommerce.models import ContractValidationError


ROOT = Path(__file__).resolve().parents[1]


class CatalogTaxReadinessTests(unittest.TestCase):
    def pending_template(self):
        return json.loads(
            (ROOT / "fixtures" / "production-catalog-intake.template.json").read_text(
                encoding="utf-8"
            )
        )

    def approved_package(self):
        payload = self.pending_template()
        payload.update(
            {
                "package_state": "approved",
                "catalog_approved": True,
                "catalog_approval_ref": "decision://catalog/example",
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
                        "source": "approved-catalog-example",
                        "source_updated_at": "2026-09-02T00:00:00Z",
                        "approval_state": "approved",
                        "price_includes_tax": True,
                        "tax_class_candidate": "reduced_rate_food",
                    }
                ],
                "tax_decision": {
                    "taxable_business_status": "taxable",
                    "qualified_invoice_status": "not_registered",
                    "qualified_invoice_registration_number": None,
                    "yamato_shipping_separately_charged": "yes",
                    "cod_fee_treatment": "standard_rate",
                    "implementation_route": "tax_tables_candidate",
                    "decision_evidence_ref": "decision://tax/example",
                },
            }
        )
        return payload

    def test_pending_catalog_fails_closed_while_reconciled_exempt_tax_is_ready(self):
        result = evaluate_catalog_tax_readiness(self.pending_template())
        self.assertFalse(result.catalog_ready)
        self.assertTrue(result.tax_decision_ready)
        self.assertFalse(result.ready_for_preproduction_configuration)
        self.assertFalse(result.mutation_authorized)
        self.assertFalse(result.production_publish_authorized)
        self.assertIn("catalog approval is pending", result.blockers)
        self.assertNotIn("Yamato separate-charge treatment is pending", result.blockers)
        self.assertNotIn("COD fee treatment is pending", result.blockers)

    def test_complete_example_can_be_ready_but_never_authorizes_mutation(self):
        result = evaluate_catalog_tax_readiness(self.approved_package())
        self.assertTrue(result.catalog_ready)
        self.assertTrue(result.tax_decision_ready)
        self.assertTrue(result.ready_for_preproduction_configuration)
        self.assertFalse(result.mutation_authorized)
        self.assertFalse(result.production_publish_authorized)
        self.assertEqual(result.blockers, ())

    def test_exempt_tax_disabled_route_does_not_require_tax_class_shipping_or_cod_tax_treatment(self):
        payload = self.approved_package()
        payload["products"][0]["tax_class_candidate"] = "pending"
        payload["tax_decision"] = {
            "taxable_business_status": "exempt",
            "qualified_invoice_status": "not_registered",
            "qualified_invoice_registration_number": None,
            "yamato_shipping_separately_charged": "pending",
            "cod_fee_treatment": "pending",
            "implementation_route": "tax_disabled_candidate",
            "decision_evidence_ref": "ops/readiness/ruby-japan-consumption-tax-status-2026-09-03.json",
        }
        result = evaluate_catalog_tax_readiness(payload)
        self.assertTrue(result.catalog_ready)
        self.assertTrue(result.tax_decision_ready)
        self.assertTrue(result.ready_for_preproduction_configuration)
        self.assertNotIn("product[1] APPROVED-001 tax class is pending", result.blockers)
        self.assertNotIn("Yamato separate-charge treatment is pending", result.blockers)
        self.assertNotIn("COD fee treatment is pending", result.blockers)
        self.assertFalse(result.mutation_authorized)
        self.assertFalse(result.production_publish_authorized)

    def test_boundary_flags_must_remain_false(self):
        payload = self.pending_template()
        payload["mutation_authorized"] = True
        with self.assertRaises(ContractValidationError):
            evaluate_catalog_tax_readiness(payload)

    def test_product_must_remain_draft_and_hidden_during_intake(self):
        payload = self.approved_package()
        payload["products"][0]["status"] = "publish"
        payload["products"][0]["visibility"] = "visible"
        result = evaluate_catalog_tax_readiness(payload)
        self.assertFalse(result.catalog_ready)
        self.assertIn("product[1] APPROVED-001 must remain draft during intake", result.blockers)
        self.assertIn("product[1] APPROVED-001 must remain hidden during intake", result.blockers)

    def test_tax_route_must_match_confirmed_business_status(self):
        payload = self.approved_package()
        payload["tax_decision"]["implementation_route"] = "tax_disabled_candidate"
        result = evaluate_catalog_tax_readiness(payload)
        self.assertFalse(result.tax_decision_ready)
        self.assertIn(
            "taxable status requires the tax_tables_candidate route", result.blockers
        )

    def test_fixture_media_is_not_catalog_ready(self):
        payload = self.approved_package()
        payload["media"][0]["source_ref"] = "fixture://cake.jpg"
        result = evaluate_catalog_tax_readiness(payload)
        self.assertFalse(result.catalog_ready)
        self.assertIn("media cake-primary uses an unapproved source", result.blockers)

    def test_approved_catalog_rejects_placeholder_content(self):
        payload = self.approved_package()
        payload["catalog_approval_ref"] = "TBD"
        payload["categories"][0]["name"]["ja"] = "未定"
        payload["media"][0]["alt"]["en"] = "pending"
        payload["products"][0]["description"]["ja"] = "確認中"
        payload["products"][0]["source"] = "to be determined"

        result = evaluate_catalog_tax_readiness(payload)

        self.assertFalse(result.catalog_ready)
        self.assertIn("catalog approval reference contains a placeholder", result.blockers)
        self.assertIn("category cakes Japanese name contains a placeholder", result.blockers)
        self.assertIn("media cake-primary English alt text contains a placeholder", result.blockers)
        self.assertIn(
            "product[1] APPROVED-001 Japanese description contains a placeholder",
            result.blockers,
        )
        self.assertIn(
            "product[1] APPROVED-001 source provenance contains a placeholder",
            result.blockers,
        )
        self.assertFalse(result.mutation_authorized)
        self.assertFalse(result.production_publish_authorized)

    def test_input_is_not_mutated(self):
        payload = self.approved_package()
        original = copy.deepcopy(payload)
        evaluate_catalog_tax_readiness(payload)
        self.assertEqual(payload, original)


if __name__ == "__main__":
    unittest.main()
