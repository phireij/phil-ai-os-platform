import unittest

from phil_ai_os_woocommerce.adapter import ProductionConnectivityBlocked
from phil_ai_os_woocommerce.readonly_catalog_snapshot import (
    collect_catalog_reconciliation_snapshot,
)


class RecordingTransport:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def request(self, method, path, *, params=None, json_body=None):
        call = {
            "method": method,
            "path": path,
            "params": dict(params or {}),
            "json_body": json_body,
        }
        self.calls.append(call)
        key = (path, int((params or {}).get("page", "1")))
        return self.routes.get(key, [])


class ReadOnlyCatalogReconciliationSnapshotTests(unittest.TestCase):
    def variable_product(self):
        return {
            "id": 42,
            "sku": "RCD-MCH-RD",
            "name": "Moist Chocolate Round Cake",
            "description": "Approved source-backed English description",
            "slug": "moist-chocolate-round-cake",
            "type": "variable",
            "status": "draft",
            "catalog_visibility": "hidden",
            "regular_price": "",
            "shipping_class": "cool-80",
            "attributes": [
                {
                    "id": 1,
                    "name": "size_cm",
                    "visible": True,
                    "variation": True,
                    "options": ["21", "15"],
                }
            ],
            "meta_data": [
                {"id": 90, "key": "_philaios_delivery_allowed", "value": True},
                {"id": 91, "key": "_philaios_temperature_modes", "value": ["frozen"]},
                {"id": 92, "key": "private_plugin_metadata", "value": "must-not-export"},
            ],
            "variations": [901, 902],
        }

    def test_variable_products_are_expanded_with_get_only_variation_reads(self):
        transport = RecordingTransport(
            {
                ("/products", 1): [self.variable_product()],
                ("/products/42/variations", 1): [
                    {
                        "id": 902,
                        "sku": "RCD-MCH-RD-21",
                        "regular_price": "5500",
                        "attributes": [{"id": 1, "name": "size_cm", "option": "21"}],
                    },
                    {
                        "id": 901,
                        "sku": "RCD-MCH-RD-15",
                        "regular_price": "3500",
                        "attributes": [{"id": 1, "name": "size_cm", "option": "15"}],
                    },
                ],
            }
        )

        snapshot = collect_catalog_reconciliation_snapshot(
            transport,
            captured_at="2026-09-12T00:00:00Z",
        ).as_dict()

        self.assertEqual(snapshot["scope"], "woocommerce_catalog_reconciliation_read_only")
        self.assertTrue(snapshot["network_read_only"])
        self.assertFalse(snapshot["mutation_authorized"])
        self.assertFalse(snapshot["production_publish_authorized"])
        self.assertEqual(len(snapshot["products"]), 1)

        product = snapshot["products"][0]
        self.assertEqual(product["sku"], "RCD-MCH-RD")
        self.assertEqual(product["type"], "variable")
        self.assertEqual(product["description"], "Approved source-backed English description")
        self.assertEqual(
            product["attributes"],
            [
                {
                    "name": "size_cm",
                    "visible": True,
                    "variation": True,
                    "options": ["21", "15"],
                }
            ],
        )
        self.assertEqual(
            product["variations"],
            [
                {
                    "id": 901,
                    "sku": "RCD-MCH-RD-15",
                    "regular_price": "3500",
                    "attributes": [{"name": "size_cm", "option": "15"}],
                },
                {
                    "id": 902,
                    "sku": "RCD-MCH-RD-21",
                    "regular_price": "5500",
                    "attributes": [{"name": "size_cm", "option": "21"}],
                },
            ],
        )
        self.assertEqual(
            product["meta_data"],
            [
                {"key": "_philaios_delivery_allowed", "value": True},
                {"key": "_philaios_temperature_modes", "value": ["frozen"]},
            ],
        )
        self.assertNotIn("private_plugin_metadata", repr(product["meta_data"]))
        self.assertTrue(transport.calls)
        self.assertTrue(all(call["method"] == "GET" for call in transport.calls))
        self.assertTrue(all(call["json_body"] is None for call in transport.calls))
        self.assertIn("/products/42/variations", [call["path"] for call in transport.calls])
        self.assertNotIn("/products/categories", [call["path"] for call in transport.calls])

    def test_simple_product_does_not_trigger_variation_endpoint(self):
        simple = {
            "id": 7,
            "sku": "RCD-BAR-FMB",
            "name": "Fudgy Milky Bar",
            "description": "Approved source-backed English description",
            "slug": "fudgy-milky-bar",
            "type": "simple",
            "status": "draft",
            "catalog_visibility": "hidden",
            "regular_price": "250",
            "shipping_class": "ambient-compact",
            "attributes": [],
            "meta_data": [],
        }
        transport = RecordingTransport({("/products", 1): [simple]})

        snapshot = collect_catalog_reconciliation_snapshot(transport)

        self.assertEqual(snapshot.products[0]["sku"], "RCD-BAR-FMB")
        self.assertNotIn("variations", snapshot.products[0])
        self.assertEqual([call["path"] for call in transport.calls], ["/products"])

    def test_variable_product_requires_positive_parent_id_before_expansion(self):
        invalid = self.variable_product()
        invalid["id"] = None
        transport = RecordingTransport({("/products", 1): [invalid]})

        with self.assertRaisesRegex(ProductionConnectivityBlocked, "variable product id"):
            collect_catalog_reconciliation_snapshot(transport)

        self.assertEqual([call["path"] for call in transport.calls], ["/products"])

    def test_variation_projection_rejects_invalid_scalar_evidence(self):
        malformed_variations = [
            {"id": "901", "sku": "RCD-MCH-RD-15", "regular_price": "3500", "attributes": []},
            {"id": 901, "sku": ["RCD-MCH-RD-15"], "regular_price": "3500", "attributes": []},
            {"id": 901, "sku": "RCD-MCH-RD-15", "regular_price": 3500, "attributes": []},
            {"id": 901, "sku": "RCD-MCH-RD-15", "regular_price": "3500", "attributes": ["size"]},
        ]
        for variation in malformed_variations:
            with self.subTest(variation=variation):
                transport = RecordingTransport(
                    {
                        ("/products", 1): [self.variable_product()],
                        ("/products/42/variations", 1): [variation],
                    }
                )
                with self.assertRaises(ProductionConnectivityBlocked):
                    collect_catalog_reconciliation_snapshot(transport)

    def test_variation_pagination_is_bounded_and_explicit(self):
        transport = RecordingTransport(
            {
                ("/products", 1): [self.variable_product()],
                ("/products/42/variations", 1): [
                    {
                        "id": 901,
                        "sku": "RCD-MCH-RD-15",
                        "regular_price": "3500",
                        "attributes": [{"name": "size_cm", "option": "15"}],
                    }
                ],
                ("/products/42/variations", 2): [],
            }
        )

        snapshot = collect_catalog_reconciliation_snapshot(
            transport,
            variation_per_page=1,
            variation_max_pages=3,
        )

        self.assertEqual(len(snapshot.products[0]["variations"]), 1)
        variation_calls = [
            call for call in transport.calls if call["path"] == "/products/42/variations"
        ]
        self.assertEqual([call["params"]["page"] for call in variation_calls], ["1", "2"])


if __name__ == "__main__":
    unittest.main()
