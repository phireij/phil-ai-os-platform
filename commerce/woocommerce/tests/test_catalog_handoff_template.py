import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CatalogHandoffTemplateTests(unittest.TestCase):
    def template(self):
        return json.loads(
            (ROOT / "fixtures" / "production-catalog-intake.template.json").read_text(
                encoding="utf-8"
            )
        )

    def test_template_reconciles_current_verified_tax_shipping_and_cod_state(self):
        payload = self.template()
        tax = payload["tax_decision"]
        self.assertEqual(tax["taxable_business_status"], "exempt")
        self.assertEqual(tax["qualified_invoice_status"], "not_registered")
        self.assertIsNone(tax["qualified_invoice_registration_number"])
        self.assertEqual(tax["yamato_shipping_separately_charged"], "yes")
        self.assertEqual(tax["cod_fee_treatment"], "not_offered")
        self.assertEqual(tax["implementation_route"], "tax_disabled_candidate")

    def test_template_remains_empty_pending_owner_catalog(self):
        payload = self.template()
        self.assertEqual(payload["package_state"], "draft")
        self.assertFalse(payload["catalog_approved"])
        self.assertIsNone(payload["catalog_approval_ref"])
        self.assertEqual(payload["categories"], [])
        self.assertEqual(payload["media"], [])
        self.assertEqual(payload["products"], [])

    def test_handoff_contract_requires_owner_provenance_and_bilingual_media_complete_source(self):
        source = self.template()["source_contract"]
        self.assertTrue(source["owner_source_required"])
        self.assertTrue(source["owner_approval_required"])
        self.assertTrue(source["source_updated_at_required"])
        self.assertTrue(source["bilingual_en_ja_required"])
        self.assertTrue(source["verified_media_source_required"])
        self.assertEqual(source["currency"], "JPY")
        self.assertEqual(source["intake_product_status"], "draft")
        self.assertEqual(source["intake_product_visibility"], "hidden")

    def test_handoff_never_grants_production_authority(self):
        payload = self.template()
        self.assertFalse(payload["source_contract"]["production_write_authority_granted_by_handoff"])
        self.assertFalse(payload["mutation_authorized"])
        self.assertFalse(payload["production_publish_authorized"])


if __name__ == "__main__":
    unittest.main()
