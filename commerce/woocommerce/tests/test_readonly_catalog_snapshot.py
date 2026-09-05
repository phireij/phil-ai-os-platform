import unittest

from phil_ai_os_woocommerce.adapter import ProductionConnectivityBlocked
from phil_ai_os_woocommerce.readonly_catalog_snapshot import collect_catalog_snapshot


class RecordingTransport:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def request(self, method, path, *, params=None, json_body=None):
        self.calls.append({"method": method, "path": path, "params": dict(params or {}), "json_body": json_body})
        key = (path, int((params or {}).get("page", "1")))
        return self.routes.get(key, [])


class ReadOnlyCatalogSnapshotTests(unittest.TestCase):
    def test_snapshot_uses_get_only_and_projects_safe_catalog_metadata(self):
        transport = RecordingTransport(
            {
                ("/products", 1): [
                    {
                        "id": 2,
                        "sku": "SKU-002",
                        "name": "Cake",
                        "slug": "cake",
                        "type": "simple",
                        "status": "draft",
                        "catalog_visibility": "hidden",
                        "regular_price": "500",
                        "manage_stock": True,
                        "stock_quantity": 3,
                        "stock_status": "instock",
                        "shipping_class": "cool-60",
                        "date_modified_gmt": "2026-09-02T12:00:00",
                        "description": "must not be exported",
                        "categories": [{"id": 5, "name": "Cakes", "slug": "cakes"}],
                        "images": [{"id": 8, "name": "Primary", "alt": "Cake image", "src": "https://example.invalid/a.jpg"}],
                    }
                ],
                ("/products/categories", 1): [
                    {"id": 5, "name": "Cakes", "slug": "cakes", "parent": 0, "count": 1}
                ],
            }
        )
        snapshot = collect_catalog_snapshot(
            transport,
            captured_at="2026-09-03T00:00:00Z",
            per_page=100,
            max_pages=2,
        ).as_dict()

        self.assertTrue(snapshot["network_read_only"])
        self.assertFalse(snapshot["mutation_authorized"])
        self.assertFalse(snapshot["production_publish_authorized"])
        self.assertEqual(snapshot["captured_at"], "2026-09-03T00:00:00Z")
        self.assertEqual(snapshot["products"][0]["sku"], "SKU-002")
        self.assertNotIn("description", snapshot["products"][0])
        self.assertNotIn("src", snapshot["products"][0]["images"][0])
        self.assertEqual(snapshot["categories"][0]["slug"], "cakes")
        self.assertTrue(transport.calls)
        self.assertTrue(all(call["method"] == "GET" for call in transport.calls))
        self.assertTrue(all(call["json_body"] is None for call in transport.calls))

    def test_invalid_explicit_capture_timestamp_fails_before_network_read(self):
        transport = RecordingTransport({})
        for captured_at in ("", "2026-09-05T03:30:00", "not-a-timestamp"):
            with self.subTest(captured_at=captured_at):
                with self.assertRaises(ValueError):
                    collect_catalog_snapshot(transport, captured_at=captured_at)
        self.assertEqual(transport.calls, [])

    def test_snapshot_rejects_malformed_product_nested_collections(self):
        bad_products = [
            {"id": 1, "sku": "A", "categories": "cakes"},
            {"id": 1, "sku": "A", "categories": ["cakes"]},
            {"id": 1, "sku": "A", "images": {"id": 8}},
            {"id": 1, "sku": "A", "images": ["image"]},
        ]
        for product in bad_products:
            with self.subTest(product=product):
                transport = RecordingTransport(
                    {
                        ("/products", 1): [product],
                        ("/products/categories", 1): [],
                    }
                )
                with self.assertRaises(ProductionConnectivityBlocked):
                    collect_catalog_snapshot(transport)

    def test_snapshot_rejects_malformed_product_scalar_evidence(self):
        bad_products = [
            {"id": "1", "sku": "A"},
            {"id": 1, "sku": {"value": "A"}},
            {"id": 1, "sku": "A", "name": ["Cake"]},
            {"id": 1, "sku": "A", "regular_price": 500},
            {"id": 1, "sku": "A", "manage_stock": "yes"},
            {"id": 1, "sku": "A", "stock_quantity": 1.5},
            {"id": 1, "sku": "A", "categories": [{"id": "5", "slug": "cakes"}]},
            {"id": 1, "sku": "A", "images": [{"id": 8, "alt": {"en": "Cake"}}]},
        ]
        for product in bad_products:
            with self.subTest(product=product):
                transport = RecordingTransport(
                    {
                        ("/products", 1): [product],
                        ("/products/categories", 1): [],
                    }
                )
                with self.assertRaises(ProductionConnectivityBlocked):
                    collect_catalog_snapshot(transport)

    def test_snapshot_rejects_malformed_category_scalar_evidence(self):
        bad_categories = [
            {"id": "5", "slug": "cakes"},
            {"id": 5, "slug": ["cakes"]},
            {"id": 5, "slug": "cakes", "name": {"en": "Cakes"}},
            {"id": 5, "slug": "cakes", "parent": "0"},
            {"id": 5, "slug": "cakes", "count": 1.5},
        ]
        for category in bad_categories:
            with self.subTest(category=category):
                transport = RecordingTransport(
                    {
                        ("/products", 1): [],
                        ("/products/categories", 1): [category],
                    }
                )
                with self.assertRaises(ProductionConnectivityBlocked):
                    collect_catalog_snapshot(transport)

    def test_snapshot_paginates_within_bound(self):
        transport = RecordingTransport(
            {
                ("/products", 1): [{"id": 1, "sku": "A"}],
                ("/products", 2): [],
                ("/products/categories", 1): [],
            }
        )
        snapshot = collect_catalog_snapshot(transport, per_page=1, max_pages=3)
        self.assertEqual(len(snapshot.products), 1)
        self.assertIn(("/products", 2), [(c["path"], int(c["params"]["page"])) for c in transport.calls])

    def test_snapshot_fails_closed_if_pagination_bound_is_exhausted(self):
        transport = RecordingTransport(
            {
                ("/products", 1): [{"id": 1, "sku": "A"}],
                ("/products", 2): [{"id": 2, "sku": "B"}],
            }
        )
        with self.assertRaises(ProductionConnectivityBlocked):
            collect_catalog_snapshot(transport, per_page=1, max_pages=2)

    def test_snapshot_rejects_non_list_payload(self):
        transport = RecordingTransport({("/products", 1): {"id": 1}})
        with self.assertRaises(ProductionConnectivityBlocked):
            collect_catalog_snapshot(transport)

    def test_snapshot_rejects_unbounded_parameters(self):
        transport = RecordingTransport({})
        with self.assertRaises(ValueError):
            collect_catalog_snapshot(transport, per_page=101)
        with self.assertRaises(ValueError):
            collect_catalog_snapshot(transport, max_pages=21)


if __name__ == "__main__":
    unittest.main()
