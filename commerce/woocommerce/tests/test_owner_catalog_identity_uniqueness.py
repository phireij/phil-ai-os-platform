import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools_validate_owner_catalog_package.py"
spec = importlib.util.spec_from_file_location("owner_catalog_identity_validator", MODULE_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(validator)


class OwnerCatalogIdentityUniquenessTests(unittest.TestCase):
    def ready_package(self):
        payload = json.loads(
            (ROOT / "fixtures" / "production-catalog-intake.template.json").read_text(
                encoding="utf-8"
            )
        )
        payload["catalog_scope"]["scope_complete_for_intended_initial_launch"] = True
        payload.update(
            {
                "package_state": "approved",
                "catalog_approved": True,
                "catalog_approval_ref": "decision://owner/catalog/approved-identity-test",
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
                        "source": "owner-approved-catalog-identity-test",
                        "source_updated_at": "2026-09-05T12:00:00+09:00",
                        "approval_state": "approved",
                        "price_includes_tax": True,
                        "tax_class_candidate": "pending",
                    }
                ],
            }
        )
        return payload

    def test_duplicate_woocommerce_category_english_slug_blocks_handoff(self):
        payload = self.ready_package()
        payload["categories"].append(
            {
                "key": "special-cakes",
                "name": {"en": "Special Cakes", "ja": "特別ケーキ"},
                "slug": {"en": "cakes", "ja": "special-cakes-ja"},
                "parent_key": None,
            }
        )
        result = validator.validate_package(payload)
        self.assertTrue(result["valid_contract"])
        self.assertFalse(result["catalog_ready"])
        self.assertFalse(result["ready_for_preproduction_configuration"])
        self.assertIn("duplicate WooCommerce category English slug: cakes", result["blockers"])
        self.assertFalse(result["mutation_authorized"])
        self.assertFalse(result["production_publish_authorized"])

    def test_duplicate_product_category_reference_blocks_handoff(self):
        payload = self.ready_package()
        payload["products"][0]["category_keys"] = ["cakes", "cakes"]
        result = validator.validate_package(payload)
        self.assertFalse(result["catalog_ready"])
        self.assertIn("OWNER-001 contains duplicate category key: cakes", result["blockers"])

    def test_duplicate_product_media_reference_blocks_handoff(self):
        payload = self.ready_package()
        payload["products"][0]["media_keys"] = ["cake-primary", "cake-primary"]
        result = validator.validate_package(payload)
        self.assertFalse(result["catalog_ready"])
        self.assertIn("OWNER-001 contains duplicate media key: cake-primary", result["blockers"])


if __name__ == "__main__":
    unittest.main()
