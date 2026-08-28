import unittest

from phil_ai_os_woocommerce.adapter import (
    MockWooCommerceTransport,
    ProductionConnectivityBlocked,
    WooCommerceAdapter,
)
from phil_ai_os_woocommerce.models import LocalizedText, ProductRecord


def sample_product(price: str = "500") -> ProductRecord:
    return ProductRecord(
        sku="SKU-1",
        name=LocalizedText(en="Cake", ja="ケーキ"),
        description=LocalizedText(en="Description", ja="説明"),
        slug=LocalizedText(en="cake", ja="cake-ja"),
        regular_price=price,
        currency="JPY",
    )


class AdapterTests(unittest.TestCase):
    def test_default_adapter_blocks_live_connectivity(self):
        adapter = WooCommerceAdapter()
        with self.assertRaises(ProductionConnectivityBlocked):
            adapter.get_product_by_sku("SKU-1")

    def test_mock_mutation_must_be_explicitly_enabled(self):
        adapter = WooCommerceAdapter(MockWooCommerceTransport())
        with self.assertRaises(ProductionConnectivityBlocked):
            adapter.reconcile_product(sample_product())

    def test_create_noop_update_and_replay(self):
        transport = MockWooCommerceTransport()
        adapter = WooCommerceAdapter(transport, allow_mutations=True)

        created = adapter.reconcile_product(sample_product())
        self.assertEqual(created.action, "create")
        self.assertEqual(created.remote_id, 1)

        replay = adapter.reconcile_product(sample_product())
        self.assertEqual(replay.action, "replay")
        self.assertEqual(replay.remote_id, 1)

        updated = adapter.reconcile_product(sample_product("550"))
        self.assertEqual(updated.action, "update")
        self.assertEqual(updated.remote_id, 1)

        product = adapter.get_product_by_sku("SKU-1")
        self.assertEqual(product["regular_price"], "550")

    def test_noop_with_fresh_idempotency_store(self):
        transport = MockWooCommerceTransport()
        writer = WooCommerceAdapter(transport, allow_mutations=True)
        writer.reconcile_product(sample_product())

        reader = WooCommerceAdapter(transport, allow_mutations=True)
        result = reader.reconcile_product(sample_product())
        self.assertEqual(result.action, "noop")


if __name__ == "__main__":
    unittest.main()
