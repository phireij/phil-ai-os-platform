import unittest

from phil_ai_os_woocommerce.models import ContractValidationError, LocalizedText, ProductRecord


class ProductContractTests(unittest.TestCase):
    def product(self) -> ProductRecord:
        return ProductRecord(
            sku="SKU-1",
            name=LocalizedText(en="Cake", ja="ケーキ"),
            description=LocalizedText(en="Description", ja="説明"),
            slug=LocalizedText(en="cake", ja="cake-ja"),
            regular_price="500",
            currency="JPY",
        )

    def test_bilingual_projection_is_deterministic(self):
        product = self.product()
        self.assertEqual(product.to_wc_payload("en")["name"], "Cake")
        self.assertEqual(product.to_wc_payload("ja")["name"], "ケーキ")
        self.assertEqual(product.to_wc_payload("en")["sku"], product.to_wc_payload("ja")["sku"])

    def test_missing_translation_fails_closed(self):
        with self.assertRaises(ContractValidationError):
            LocalizedText(en="Cake", ja="")

    def test_negative_price_rejected(self):
        with self.assertRaises(ContractValidationError):
            ProductRecord(
                sku="SKU-1",
                name=LocalizedText(en="Cake", ja="ケーキ"),
                description=LocalizedText(en="Description", ja="説明"),
                slug=LocalizedText(en="cake", ja="cake-ja"),
                regular_price="-1",
                currency="JPY",
            )


if __name__ == "__main__":
    unittest.main()
