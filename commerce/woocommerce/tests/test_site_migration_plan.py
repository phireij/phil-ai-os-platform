import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SiteMigrationPlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((ROOT / "fixtures" / "site-migration-plan.json").read_text(encoding="utf-8"))

    def test_existing_site_is_reference_only(self):
        self.assertEqual(self.plan["source_platform"], "hostinger-website-builder")
        self.assertEqual(self.plan["source_role"], "reference-only")
        self.assertTrue(self.plan["verification_required"])
        self.assertFalse(self.plan["production_authority"])

    def test_only_approved_sections_are_copy_candidates(self):
        self.assertEqual(
            set(self.plan["copy_sections"]),
            {"store_information", "contact_information", "policies"},
        )
        self.assertEqual(set(self.plan["exclude_sections"]), {"products", "categories"})

    def test_public_domain_is_preserved_as_planning_data_only(self):
        self.assertEqual(self.plan["public_domain"], "https://www.rubyscakedelights.shop/")


if __name__ == "__main__":
    unittest.main()
