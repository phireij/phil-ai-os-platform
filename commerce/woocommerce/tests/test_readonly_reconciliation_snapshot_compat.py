import unittest

from phil_ai_os_woocommerce.models import ProductRecord
from phil_ai_os_woocommerce.readonly_catalog_snapshot import collect_catalog_reconciliation_snapshot
from phil_ai_os_woocommerce.reconciliation import comparable_remote_product


class Transport:
    def __init__(self, parent, variations):
        self.parent = parent
        self.variations = variations

    def request(self, method, path, *, params=None, json_body=None):
        if method != "GET" or json_body is not None:
            raise AssertionError("compatibility snapshot must remain GET-only")
        page = int((params or {}).get("page", "1"))
        if page != 1:
            return []
        if path == "/products":
            return [self.parent]
        if path == "/products/42/variations":
            return self.variations
        return []


class ReadOnlyReconciliationSnapshotCompatibilityTests(unittest.TestCase):
    def test_snapshot_parent_normalizes_to_canonical_variable_projection(self):
        product = ProductRecord.from_mapping(
            {
                "sku": "PARENT-001",
                "product_type": "variable",
                "name": {"en": "Test Cake", "ja": "テストケーキ"},
                "description": {"en": "Test description", "ja": "テスト説明"},
                "slug": {"en": "test-cake", "ja": "test-cake-ja"},
                "regular_price": None,
                "variations": [
                    {
                        "sku": "PARENT-001-15",
                        "regular_price": "3500",
                        "attributes": {"size_cm": "15"},
                    }
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
            }
        )
        remote_parent = {
            "id": 42,
            "sku": "PARENT-001",
            "name": "Test Cake",
            "description": "Test description",
            "slug": "test-cake",
            "type": "variable",
            "status": "draft",
            "catalog_visibility": "hidden",
            "regular_price": "",
            "shipping_class": "cool-80",
            "attributes": [
                {
                    "name": "size_cm",
                    "visible": True,
                    "variation": True,
                    "options": ["15"],
                }
            ],
            "meta_data": [
                {"key": "_philaios_requires_order_approval", "value": True},
                {"key": "_philaios_delivery_allowed", "value": True},
                {"key": "_philaios_pickup_allowed", "value": True},
                {"key": "_philaios_temperature_modes", "value": ["frozen"]},
            ],
        }
        variations = [
            {
                "id": 901,
                "sku": "PARENT-001-15",
                "regular_price": "3500",
                "attributes": [{"name": "size_cm", "option": "15"}],
            }
        ]

        snapshot = collect_catalog_reconciliation_snapshot(Transport(remote_parent, variations))
        before = comparable_remote_product(snapshot.products[0], variable=True)
        desired = product.to_wc_payload("en")

        self.assertEqual(before, desired)
        self.assertEqual(snapshot.products[0]["variations"][0]["sku"], "PARENT-001-15")


if __name__ == "__main__":
    unittest.main()
