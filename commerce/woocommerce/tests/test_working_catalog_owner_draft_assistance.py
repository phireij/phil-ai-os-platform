import json
from pathlib import Path
import unittest

from phil_ai_os_woocommerce.working_catalog_owner_draft_assistance import (
    build_working_catalog_owner_draft_assistance,
    render_working_catalog_owner_draft_assistance_markdown,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"
PROPOSALS = ROOT / "fixtures" / "working-catalog-owner-draft-assistance-2026-09-15.json"


class WorkingCatalogOwnerDraftAssistanceTests(unittest.TestCase):
    def load_catalog(self):
        return json.loads(CATALOG.read_text(encoding="utf-8"))

    def load_proposals(self):
        return json.loads(PROPOSALS.read_text(encoding="utf-8"))

    def test_current_drafts_are_separate_and_non_authorizing(self):
        assistance = build_working_catalog_owner_draft_assistance(
            self.load_catalog(), self.load_proposals()
        )
        self.assertEqual(
            [item.product_key for item in assistance.drafts],
            ["RCD-BAR-FMB", "RCD-BRD-ENS-1", "RCD-MCH-RD"],
        )
        self.assertFalse(assistance.owner_approved)
        self.assertFalse(assistance.canonical_apply_authorized)
        self.assertFalse(assistance.network_call_performed)
        self.assertFalse(assistance.mutation_authorized)
        self.assertFalse(assistance.production_publish_authorized)

    def test_exact_english_source_text_is_a_staleness_guard(self):
        catalog = self.load_catalog()
        catalog["working_products"][0]["english_name"] = "Changed source name"
        with self.assertRaisesRegex(ValueError, "English name is stale for RCD-MCH-RD"):
            build_working_catalog_owner_draft_assistance(catalog, self.load_proposals())

    def test_canonical_japanese_copy_cannot_be_overwritten_by_draft(self):
        catalog = self.load_catalog()
        catalog["working_products"][1]["japanese_name"] = "確定済み名称"
        with self.assertRaisesRegex(
            ValueError, "cannot overwrite canonical Japanese name for RCD-BAR-FMB"
        ):
            build_working_catalog_owner_draft_assistance(catalog, self.load_proposals())

    def test_all_products_missing_japanese_copy_require_explicit_draft_coverage(self):
        proposals = self.load_proposals()
        proposals["products"] = proposals["products"][:-1]
        with self.assertRaisesRegex(ValueError, "draft assistance coverage mismatch"):
            build_working_catalog_owner_draft_assistance(self.load_catalog(), proposals)

    def test_authority_flags_must_remain_false(self):
        for field in (
            "owner_approved",
            "canonical_apply_authorized",
            "network_call_performed",
            "mutation_authorized",
            "production_publish_authorized",
        ):
            proposals = self.load_proposals()
            proposals[field] = True
            with self.assertRaisesRegex(ValueError, f"{field}=false"):
                build_working_catalog_owner_draft_assistance(self.load_catalog(), proposals)

    def test_rendered_markdown_is_explicitly_proposal_only(self):
        assistance = build_working_catalog_owner_draft_assistance(
            self.load_catalog(), self.load_proposals()
        )
        rendered = render_working_catalog_owner_draft_assistance_markdown(assistance)
        self.assertIn("# Working Catalog Japanese Copy — Draft Assistance", rendered)
        self.assertIn("**Proposal only.**", rendered)
        self.assertIn("モイストチョコレート・ラウンドケーキ", rendered)
        self.assertIn("チージー・エンサイマダ", rendered)
        self.assertIn("Owner approved: **No**", rendered)
        self.assertIn("Canonical apply authorized: **No**", rendered)
        self.assertIn("Production publication authorized: **No**", rendered)
        self.assertIn("does not approve Initial Launch Catalog V1", rendered)


if __name__ == "__main__":
    unittest.main()
