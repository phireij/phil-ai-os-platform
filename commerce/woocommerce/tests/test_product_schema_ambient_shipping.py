import json
from pathlib import Path
import unittest


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "product.schema.json"


class ProductSchemaAmbientShippingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.fulfillment = cls.schema["$defs"]["fulfillmentProfile"]

    def test_ambient_shipping_classes_are_declared(self):
        allowed = set(self.fulfillment["properties"]["shipping_class"]["enum"])
        self.assertTrue(
            {
                "ambient-compact",
                "ambient-60",
                "ambient-80",
                "ambient-100",
                "ambient-120",
            }.issubset(allowed)
        )

    def test_existing_cool_shipping_classes_are_preserved(self):
        allowed = set(self.fulfillment["properties"]["shipping_class"]["enum"])
        self.assertTrue(
            {"cool-60", "cool-80", "cool-100", "cool-120"}.issubset(allowed)
        )

    def test_ambient_temperature_mode_is_declared(self):
        allowed = set(
            self.fulfillment["properties"]["temperature_modes"]["items"]["enum"]
        )
        self.assertEqual(allowed, {"ambient", "chilled", "frozen"})

    def test_delivery_still_requires_shipping_class_and_temperature_mode(self):
        delivery_rule = self.fulfillment["allOf"][0]
        then_properties = delivery_rule["then"]["properties"]
        self.assertEqual(then_properties["shipping_class"], {"type": "string"})
        self.assertEqual(then_properties["temperature_modes"]["minItems"], 1)


if __name__ == "__main__":
    unittest.main()
