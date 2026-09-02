import copy
import unittest

from phil_ai_os_woocommerce.catalog_readiness import evaluate_catalog_tax_readiness


def approved_package():
    return {
        "schema_version": "1.0",
        "environment": "pre-production",
        "package_state": "approved",
        "catalog_approved": True,
        "catalog_approval_ref": "decision://catalog/approved-source",
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
                "source": "approved-catalog-owner-confirmed",
                "source_updated_at": "2026-09-03T05:00:00+09:00",
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
        "mutation_authorized": False,
        "production_publish_authorized": False,
    }


class CatalogProvenanceTests(unittest.TestCase):
    def test_approved_owner_source_remains_ready_without_mutation_authority(self):
        result = evaluate_catalog_tax_readiness(approved_package())
        self.assertTrue(result.catalog_ready)
        self.assertFalse(result.mutation_authorized)
        self.assertFalse(result.production_publish_authorized)

    def test_historical_or_builder_product_source_cannot_become_catalog_ready(self):
        for source in ("historical-builder-export", "legacy-catalog", "fixture"):
            with self.subTest(source=source):
                payload = approved_package()
                payload["products"][0]["source"] = source
                result = evaluate_catalog_tax_readiness(payload)
                self.assertFalse(result.catalog_ready)
                self.assertIn(
                    "product[1] APPROVED-001 source provenance is not approved",
                    result.blockers,
                )

    def test_product_source_timestamp_must_be_timezone_aware_iso(self):
        for timestamp in (None, "", "2026-09-03T05:00:00", "not-a-date"):
            with self.subTest(timestamp=timestamp):
                payload = approved_package()
                payload["products"][0]["source_updated_at"] = timestamp
                result = evaluate_catalog_tax_readiness(payload)
                self.assertFalse(result.catalog_ready)
                self.assertIn(
                    "product[1] APPROVED-001 source_updated_at must be a timezone-aware ISO timestamp",
                    result.blockers,
                )

    def test_unknown_category_parent_fails_catalog_readiness(self):
        payload = approved_package()
        payload["categories"][0]["parent_key"] = "missing-parent"
        result = evaluate_catalog_tax_readiness(payload)
        self.assertFalse(result.catalog_ready)
        self.assertIn(
            "category cakes has unknown parent key: missing-parent", result.blockers
        )

    def test_category_cycle_fails_catalog_readiness(self):
        payload = approved_package()
        payload["categories"] = [
            {
                "key": "cakes",
                "name": {"en": "Cakes", "ja": "ケーキ"},
                "slug": {"en": "cakes", "ja": "cakes-ja"},
                "parent_key": "desserts",
            },
            {
                "key": "desserts",
                "name": {"en": "Desserts", "ja": "デザート"},
                "slug": {"en": "desserts", "ja": "desserts-ja"},
                "parent_key": "cakes",
            },
        ]
        result = evaluate_catalog_tax_readiness(payload)
        self.assertFalse(result.catalog_ready)
        self.assertTrue(
            any(blocker.startswith("category hierarchy cycle detected at:") for blocker in result.blockers)
        )

    def test_exactly_one_primary_media_is_required_per_product(self):
        payload = approved_package()
        payload["media"].append(
            {
                "key": "cake-primary-2",
                "source_ref": "verified-media://cake-primary-2",
                "alt": {"en": "Cake second", "ja": "ケーキ2"},
                "role": "primary",
                "position": 1,
            }
        )
        payload["products"][0]["media_keys"].append("cake-primary-2")
        result = evaluate_catalog_tax_readiness(payload)
        self.assertFalse(result.catalog_ready)
        self.assertIn(
            "product[1] APPROVED-001 requires exactly one primary media item; found 2",
            result.blockers,
        )

    def test_unapproved_media_source_cannot_become_catalog_ready(self):
        payload = approved_package()
        payload["media"][0]["source_ref"] = "builder://old-site/cake.jpg"
        result = evaluate_catalog_tax_readiness(payload)
        self.assertFalse(result.catalog_ready)
        self.assertIn("media cake-primary uses an unapproved source", result.blockers)


if __name__ == "__main__":
    unittest.main()
