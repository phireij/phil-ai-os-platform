import unittest

from phil_ai_os_woocommerce.adapter import MockWooCommerceTransport
from phil_ai_os_woocommerce.rollback import capture_mock_snapshot, restore_mock_snapshot


class MockRollbackTests(unittest.TestCase):
    def test_product_state_restores_after_mutation(self):
        transport = MockWooCommerceTransport()
        created = transport.request(
            "POST",
            "/products",
            json_body={"sku": "SKU-ROLLBACK", "name": "Before"},
        )
        snapshot = capture_mock_snapshot(transport)

        transport.request(
            "PUT",
            f"/products/{created['id']}",
            json_body={"name": "After"},
        )
        self.assertEqual(
            transport.request("GET", "/products", params={"sku": "SKU-ROLLBACK"})[0]["name"],
            "After",
        )

        restore_mock_snapshot(transport, snapshot)
        restored = transport.request("GET", "/products", params={"sku": "SKU-ROLLBACK"})[0]
        self.assertEqual(restored["name"], "Before")

    def test_category_state_and_identity_counter_restore(self):
        transport = MockWooCommerceTransport()
        snapshot = capture_mock_snapshot(transport)
        first = transport.request(
            "POST",
            "/products/categories",
            json_body={"name": "Temporary", "slug": "temporary"},
        )
        self.assertEqual(first["id"], 1)

        restore_mock_snapshot(transport, snapshot)
        self.assertEqual(transport.request("GET", "/products/categories", params={"slug": "temporary"}), [])

        recreated = transport.request(
            "POST",
            "/products/categories",
            json_body={"name": "Recreated", "slug": "recreated"},
        )
        self.assertEqual(recreated["id"], 1)


if __name__ == "__main__":
    unittest.main()
