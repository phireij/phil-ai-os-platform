import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools_validate_owner_catalog_package.py"
spec = importlib.util.spec_from_file_location("owner_catalog_shape_validator", MODULE_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(validator)


class OwnerCatalogShapeFailClosedTests(unittest.TestCase):
    def template(self):
        return json.loads(
            (ROOT / "fixtures" / "production-catalog-intake.template.json").read_text(
                encoding="utf-8"
            )
        )

    def test_malformed_owner_catalog_object_shapes_fail_closed(self):
        cases = (
            (
                "category entry",
                lambda payload: payload.update({"categories": ["not-an-object"]}),
                "categories[0] must be an object",
            ),
            (
                "category localized name",
                lambda payload: payload.update(
                    {"categories": [{"name": [], "slug": {"en": "cakes", "ja": "cakes-ja"}}]}
                ),
                "categories[0].name must be an object",
            ),
            (
                "media alt text",
                lambda payload: payload.update(
                    {"media": [{"alt": [], "source_ref": "verified-media://owner/cake"}]}
                ),
                "media[0].alt must be an object",
            ),
            (
                "product fulfillment",
                lambda payload: payload.update(
                    {
                        "products": [
                            {
                                "name": {"en": "Cake", "ja": "ケーキ"},
                                "description": {"en": "Cake", "ja": "ケーキ"},
                                "slug": {"en": "cake", "ja": "cake-ja"},
                                "fulfillment": [],
                            }
                        ]
                    }
                ),
                "products[0].fulfillment must be an object",
            ),
        )

        for label, mutate, expected in cases:
            with self.subTest(label=label):
                payload = self.template()
                mutate(payload)
                result = validator.validate_package(payload)
                self.assertFalse(result["valid_contract"])
                self.assertFalse(result["ready_for_preproduction_configuration"])
                self.assertIn(expected, result["blockers"][0])
                self.assertFalse(result["mutation_authorized"])
                self.assertFalse(result["production_publish_authorized"])


if __name__ == "__main__":
    unittest.main()
