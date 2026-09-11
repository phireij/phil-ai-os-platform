from __future__ import annotations

import copy
import unittest

import tools_generate_storefront_catalog_preview as generator


class RubyStorefrontCatalogProjectionTests(unittest.TestCase):
    def test_committed_projection_matches_canonical_working_catalog(self):
        projection = generator.build_projection()
        self.assertTrue(generator.check_projection())
        self.assertTrue(projection["preview_only"])
        self.assertFalse(projection["catalog_approved"])
        self.assertFalse(projection["mutation_authorized"])
        self.assertFalse(projection["production_publish_authorized"])

        products = {item["key"]: item for item in projection["products"]}
        self.assertEqual(set(products), {"RCD-MCH-RD", "RCD-BAR-FMB", "RCD-BRD-ENS-1"})
        self.assertEqual(products["RCD-MCH-RD"]["price_jpy"], 3500)
        self.assertEqual(
            [(item["size_cm"], item["sku"], item["price_jpy"]) for item in products["RCD-MCH-RD"]["variants"]],
            [(15, "RCD-MCH-RD-15", 3500), (21, "RCD-MCH-RD-21", 5500)],
        )
        self.assertEqual(products["RCD-BAR-FMB"]["price_jpy"], 250)
        self.assertEqual(products["RCD-BRD-ENS-1"]["price_jpy"], 300)

    def test_projection_excludes_internal_owner_provenance(self):
        rendered = generator.render_module(generator.build_projection())
        for forbidden in (
            "drive_file_id",
            "field_evidence",
            "owner_visual_confirmation",
            "owner_direct_confirmation",
            "allergens_source_text",
            "known_blockers",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_projection_rejects_authority_expansion(self):
        source = generator.build_projection()
        self.assertFalse(source["mutation_authorized"])

        canonical = __import__("json").loads(generator.SOURCE.read_text(encoding="utf-8"))
        for field in ("catalog_approved", "mutation_authorized", "production_publish_authorized"):
            expanded = copy.deepcopy(canonical)
            expanded[field] = True
            with self.assertRaises(ValueError):
                generator.build_projection_from_source(expanded)

        expanded = copy.deepcopy(canonical)
        expanded["source_contract"]["production_write_authority_granted_by_handoff"] = True
        with self.assertRaises(ValueError):
            generator.build_projection_from_source(expanded)


if __name__ == "__main__":
    unittest.main()
