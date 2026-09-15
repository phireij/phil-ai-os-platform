import json
from pathlib import Path
import unittest

from phil_ai_os_woocommerce.working_catalog_owner_decision_brief import (
    build_working_catalog_owner_decision_brief,
    render_working_catalog_owner_decision_brief,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"
PROPOSALS = ROOT / "fixtures" / "working-catalog-owner-draft-assistance-2026-09-15.json"


class WorkingCatalogOwnerDecisionBriefTests(unittest.TestCase):
    def load(self):
        return (
            json.loads(CATALOG.read_text(encoding="utf-8")),
            json.loads(PROPOSALS.read_text(encoding="utf-8")),
        )

    def test_current_actions_are_fully_partitioned_without_hiding_blockers(self):
        catalog, proposals = self.load()
        brief = build_working_catalog_owner_decision_brief(catalog, proposals)

        self.assertEqual(len(brief.owner_decisions), 14)
        self.assertEqual(len(brief.post_decision_records), 1)
        self.assertEqual(len(brief.operational_evidence), 5)
        self.assertEqual(len(brief.deferred_authority_gates), 2)
        self.assertEqual(len(brief.needs_review), 0)
        self.assertEqual(
            sum(
                len(items)
                for items in (
                    brief.owner_decisions,
                    brief.post_decision_records,
                    brief.operational_evidence,
                    brief.deferred_authority_gates,
                    brief.needs_review,
                )
            ),
            22,
        )
        self.assertFalse(brief.production_ready)

    def test_japanese_copy_proposals_are_advisory_for_six_owner_decisions(self):
        catalog, proposals = self.load()
        brief = build_working_catalog_owner_decision_brief(catalog, proposals)

        self.assertEqual(len(brief.japanese_draft_action_keys), 6)
        self.assertEqual(
            set(brief.japanese_draft_action_keys),
            {
                "product:RCD-BAR-FMB:japanese-description",
                "product:RCD-BAR-FMB:japanese-product-name",
                "product:RCD-BRD-ENS-1:japanese-description",
                "product:RCD-BRD-ENS-1:japanese-product-name",
                "product:RCD-MCH-RD:japanese-description",
                "product:RCD-MCH-RD:japanese-product-name",
            },
        )

    def test_physical_fit_and_media_are_evidence_not_owner_catalog_values(self):
        catalog, proposals = self.load()
        brief = build_working_catalog_owner_decision_brief(catalog, proposals)
        requirements = {item.requirement for item in brief.operational_evidence}

        self.assertIn(
            "Fulfillment: ambient package candidate lacks physical-fit confirmation",
            requirements,
        )
        self.assertIn("primary media selection and verified ingestion references require review", requirements)
        self.assertIn("verified media ingestion reference is unresolved", requirements)
        self.assertNotIn(
            "Fulfillment: multiple temperature modes require owner classification",
            requirements,
        )

    def test_approval_reference_is_post_decision_record_and_authority_stays_deferred(self):
        catalog, proposals = self.load()
        brief = build_working_catalog_owner_decision_brief(catalog, proposals)

        self.assertEqual(
            tuple(item.requirement for item in brief.post_decision_records),
            ("catalog approval reference is missing",),
        )
        self.assertEqual(
            {item.requirement for item in brief.deferred_authority_gates},
            {
                "production mutation authority is not granted",
                "production publication authority is not granted",
            },
        )
        self.assertFalse(brief.network_call_performed)
        self.assertFalse(brief.mutation_authorized)
        self.assertFalse(brief.production_publish_authorized)

    def test_rendered_brief_explains_what_needs_ceo_attention_without_granting_authority(self):
        catalog, proposals = self.load()
        rendered = render_working_catalog_owner_decision_brief(
            build_working_catalog_owner_decision_brief(catalog, proposals)
        )

        self.assertIn("# Initial Launch Catalog V1 — CEO Decision Brief", rendered)
        self.assertIn("CEO-controlled decisions: **14**", rendered)
        self.assertIn("Japanese copy decisions with draft assistance: **6**", rendered)
        self.assertIn("Operational/evidence items: **5**", rendered)
        self.assertIn("Deferred authority gates: **2**", rendered)
        self.assertIn("Needs classification/review: **0**", rendered)
        self.assertIn("Deferred authority gates — no approval requested now", rendered)
        self.assertIn("WooCommerce mutation authorized: **No**", rendered)
        self.assertIn("Production publication authorized: **No**", rendered)

    def test_stale_japanese_proposals_still_fail_closed(self):
        catalog, proposals = self.load()
        catalog["working_products"][0]["english_name"] = "Changed source name"
        with self.assertRaisesRegex(ValueError, "English name is stale"):
            build_working_catalog_owner_decision_brief(catalog, proposals)


if __name__ == "__main__":
    unittest.main()
