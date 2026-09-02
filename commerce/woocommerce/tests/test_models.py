import unittest

from phil_ai_os_woocommerce.models import (
    ContractValidationError,
    FulfillmentProfile,
    LocalizedText,
    ProductRecord,
)


class ProductContractTests(unittest.TestCase):
    def fulfillment(self) -> FulfillmentProfile:
        return FulfillmentProfile("cool-60", ("chilled",), True, True)

    def product(self) -> ProductRecord:
        return ProductRecord(
            sku="SKU-1",
            name=LocalizedText(en="Cake", ja="ケーキ"),
            description=LocalizedText(en="Description", ja="説明"),
            slug=LocalizedText(en="cake", ja="cake-ja"),
            regular_price="500",
            currency="JPY",
            fulfillment=self.fulfillment(),
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
                fulfillment=self.fulfillment(),
            )

    def test_delivery_requires_shipping_class_and_temperature(self):
        with self.assertRaises(ContractValidationError):
            FulfillmentProfile(None, (), True, True)

    def test_pickup_only_rejects_delivery_configuration(self):
        with self.assertRaises(ContractValidationError):
            FulfillmentProfile("cool-60", ("chilled",), True, False)

    def test_fulfillment_projection_is_explicit(self):
        payload = self.product().to_wc_payload("en")
        self.assertEqual(payload["shipping_class"], "cool-60")
        metadata = {item["key"]: item["value"] for item in payload["meta_data"]}
        self.assertEqual(metadata["_philaios_temperature_modes"], ["chilled"])
        self.assertTrue(metadata["_philaios_requires_order_approval"])


if __name__ == "__main__":
    unittest.main()
