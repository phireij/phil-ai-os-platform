import unittest

from phil_ai_os_woocommerce.models import ContractValidationError, InventoryRecord


class InventoryContractTests(unittest.TestCase):
    def test_source_of_truth_is_required(self):
        with self.assertRaises(ContractValidationError):
            InventoryRecord(sku="SKU-1", quantity=1, stock_status="instock", source_of_truth="", revision=1)

    def test_revision_is_non_negative(self):
        with self.assertRaises(ContractValidationError):
            InventoryRecord(sku="SKU-1", quantity=1, stock_status="instock", source_of_truth="fixture", revision=-1)


if __name__ == "__main__":
    unittest.main()
