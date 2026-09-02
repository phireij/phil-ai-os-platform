import unittest

from phil_ai_os_woocommerce import InventoryConflictError, StaleInventoryRevision
from phil_ai_os_woocommerce.adapter import MockWooCommerceTransport, WooCommerceAdapter
from phil_ai_os_woocommerce.models import (
    FulfillmentProfile,
    InventoryRecord,
    LocalizedText,
    ProductRecord,
)


class InventoryRevisionGuardTests(unittest.TestCase):
    def setUp(self):
        self.transport = MockWooCommerceTransport()
        self.adapter = WooCommerceAdapter(self.transport, allow_mutations=True)
        product = ProductRecord(
            sku="SKU-REV-1",
            name=LocalizedText(en="Cake", ja="ケーキ"),
            description=LocalizedText(en="Description", ja="説明"),
            slug=LocalizedText(en="cake-rev", ja="cake-rev-ja"),
            regular_price="500",
            currency="JPY",
            fulfillment=FulfillmentProfile("cool-60", ("chilled",), True, True),
        )
        self.adapter.reconcile_product(product)

    def inventory(self, quantity: int, revision: int, source: str = "synthetic-fixture") -> InventoryRecord:
        return InventoryRecord(
            sku="SKU-REV-1",
            quantity=quantity,
            stock_status="instock" if quantity else "outofstock",
            source_of_truth=source,
            revision=revision,
        )

    def test_stale_revision_fails_closed(self):
        self.adapter.reconcile_inventory(self.inventory(8, 2))
        with self.assertRaises(StaleInventoryRevision):
            self.adapter.reconcile_inventory(self.inventory(7, 1))

    def test_same_revision_with_different_payload_is_conflict(self):
        self.adapter.reconcile_inventory(self.inventory(8, 2))
        with self.assertRaises(InventoryConflictError):
            self.adapter.reconcile_inventory(self.inventory(9, 2))

    def test_source_change_requires_explicit_reconciliation_policy(self):
        self.adapter.reconcile_inventory(self.inventory(8, 2, "source-a"))
        with self.assertRaises(InventoryConflictError):
            self.adapter.reconcile_inventory(self.inventory(8, 3, "source-b"))


if __name__ == "__main__":
    unittest.main()
