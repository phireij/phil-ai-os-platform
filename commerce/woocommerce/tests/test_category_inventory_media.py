import unittest

from phil_ai_os_woocommerce.adapter import MockWooCommerceTransport, ProductionConnectivityBlocked, WooCommerceAdapter
from phil_ai_os_woocommerce.models import CategoryRecord, InventoryRecord, LocalizedText, MediaRecord, ProductRecord


class CategoryInventoryMediaTests(unittest.TestCase):
    def setUp(self):
        self.transport = MockWooCommerceTransport()
        self.adapter = WooCommerceAdapter(self.transport, allow_mutations=True)

    def product(self):
        return ProductRecord(
            sku="SKU-1",
            name=LocalizedText(en="Cake", ja="ケーキ"),
            description=LocalizedText(en="Description", ja="説明"),
            slug=LocalizedText(en="cake", ja="cake-ja"),
            regular_price="500",
            currency="JPY",
        )

    def test_category_create_and_replay(self):
        category = CategoryRecord(
            key="cakes",
            name=LocalizedText(en="Cakes", ja="ケーキ"),
            slug=LocalizedText(en="cakes", ja="cakes-ja"),
        )
        first = self.adapter.reconcile_category(category)
        second = self.adapter.reconcile_category(category)
        self.assertEqual(first.action, "create")
        self.assertEqual(second.action, "replay")

    def test_inventory_requires_existing_product(self):
        inventory = InventoryRecord("MISSING", 2, "instock", "fixture", 1)
        with self.assertRaises(ValueError):
            self.adapter.reconcile_inventory(inventory)

    def test_inventory_update_and_replay(self):
        self.adapter.reconcile_product(self.product())
        inventory = InventoryRecord("SKU-1", 7, "instock", "fixture", 1)
        first = self.adapter.reconcile_inventory(inventory)
        second = self.adapter.reconcile_inventory(inventory)
        self.assertEqual(first.action, "update")
        self.assertEqual(second.action, "replay")
        remote = self.adapter.get_product_by_sku("SKU-1")
        self.assertEqual(remote["stock_quantity"], 7)

    def test_media_is_plan_only(self):
        media = MediaRecord(
            key="m1",
            source_ref="fixture://m1.jpg",
            alt=LocalizedText(en="Cake", ja="ケーキ"),
            role="primary",
            position=0,
        )
        manifest = self.adapter.plan_media(media, locale="ja")
        self.assertEqual(manifest["alt"], "ケーキ")
        self.assertEqual(len([c for c in self.transport.calls if c["path"].startswith("/media")]), 0)

    def test_category_mutation_defaults_blocked(self):
        adapter = WooCommerceAdapter(MockWooCommerceTransport())
        category = CategoryRecord(
            key="cakes",
            name=LocalizedText(en="Cakes", ja="ケーキ"),
            slug=LocalizedText(en="cakes", ja="cakes-ja"),
        )
        with self.assertRaises(ProductionConnectivityBlocked):
            adapter.reconcile_category(category)


if __name__ == "__main__":
    unittest.main()
