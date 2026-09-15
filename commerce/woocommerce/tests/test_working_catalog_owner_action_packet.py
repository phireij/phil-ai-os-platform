import json
from pathlib import Path
import unittest

from phil_ai_os_woocommerce.working_catalog_owner_action_packet import (
    build_working_catalog_owner_action_packet,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"


class WorkingCatalogOwnerActionPacketTests(unittest.TestCase):
    def load(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_current_catalog_actions_are_explicit_and_non_authorizing(self):
        packet = build_working_catalog_owner_action_packet(self.load())
        self.assertFalse(packet.production_ready)
        self.assertFalse(packet.network_call_performed)
        self.assertFalse(packet.mutation_authorized)
        self.assertFalse(packet.production_publish_authorized)
        self.assertTrue(packet.actions)
        self.assertTrue(all(action.decision_value is None for action in packet.actions))

    def test_current_owner_gates_are_present_without_runtime_authority_gates(self):
        packet = build_working_catalog_owner_action_packet(self.load())
        by_requirement = {action.requirement: action for action in packet.actions}
        self.assertEqual(
            by_requirement["initial launch subset is not owner-confirmed complete"].category,
            "owner_scope_confirmation",
        )
        self.assertEqual(
            by_requirement["catalog approval is missing"].category,
            "owner_approval",
        )
        self.assertNotIn("production mutation authority is not granted", by_requirement)
        self.assertNotIn("production publication authority is not granted", by_requirement)

    def test_product_actions_preserve_exact_catalog_and_fulfillment_gaps(self):
        packet = build_working_catalog_owner_action_packet(self.load())
        by_product = {}
        for action in packet.actions:
            if action.product_key:
                by_product.setdefault(action.product_key, []).append(action)

        bar = by_product["RCD-BAR-FMB"]
        requirements = {action.requirement for action in bar}
        self.assertIn("Japanese product name", requirements)
        self.assertIn(
            "Fulfillment: multiple temperature modes require owner classification",
            requirements,
        )
        self.assertIn(
            "Fulfillment: quantity-dependent package rule requires final package policy",
            requirements,
        )
        self.assertTrue(
            any(action.category == "fulfillment_decision_or_evidence" for action in bar)
        )

    def test_category_candidate_blockers_are_included_in_owner_actions(self):
        packet = build_working_catalog_owner_action_packet(self.load())
        category_actions = [action for action in packet.actions if action.category == "category_mapping"]
        self.assertTrue(category_actions)
        moist = [action for action in category_actions if action.product_key == "RCD-MCH-RD"]
        self.assertTrue(moist)
        self.assertEqual(moist[0].requirement, "category source label is missing")
        self.assertIn(
            "final category hierarchy, bilingual names, slugs, and mappings require approval",
            {action.requirement for action in category_actions},
        )

    def test_media_evidence_blockers_are_included_without_invented_references(self):
        packet = build_working_catalog_owner_action_packet(self.load())
        media_actions = [
            action for action in packet.actions if action.category == "media_ingestion_evidence"
        ]
        self.assertTrue(media_actions)
        by_product = {action.product_key: action for action in media_actions if action.product_key}
        self.assertEqual(by_product["RCD-MCH-RD"].requirement, "media source state is missing")
        self.assertEqual(
            by_product["RCD-BAR-FMB"].requirement,
            "verified media ingestion reference is unresolved",
        )
        self.assertTrue(all(action.decision_value is None for action in media_actions))

    def test_semantically_duplicate_category_and_media_wrappers_are_collapsed(self):
        packet = build_working_catalog_owner_action_packet(self.load())

        semantic_identities = []
        for action in packet.actions:
            requirement = action.requirement
            for prefix in ("Category: ", "Media: "):
                if requirement.startswith(prefix):
                    requirement = requirement[len(prefix) :]
                    break
            semantic_identities.append((action.scope, action.product_key, requirement))

        self.assertEqual(len(semantic_identities), len(set(semantic_identities)))
        self.assertFalse(
            any(
                action.category == "owner_or_operational_review"
                and action.requirement.startswith(("Category: ", "Media: "))
                for action in packet.actions
            )
        )
        self.assertTrue(
            any(
                action.category == "category_mapping"
                and action.product_key == "RCD-MCH-RD"
                and action.requirement == "category source label is missing"
                for action in packet.actions
            )
        )
        self.assertTrue(
            any(
                action.category == "media_ingestion_evidence"
                and action.product_key == "RCD-BAR-FMB"
                and action.requirement == "verified media ingestion reference is unresolved"
                for action in packet.actions
            )
        )

    def test_supplemental_category_or_media_blockers_keep_packet_fail_closed(self):
        payload = self.load()
        payload["catalog_approved"] = True
        payload["catalog_approval_ref"] = "owner-approval-placeholder-for-test"
        payload["catalog_scope"]["scope_complete_for_intended_initial_launch"] = True
        payload["source_snapshot"]["owner_declared_subset_complete"] = True
        packet = build_working_catalog_owner_action_packet(payload)
        self.assertFalse(packet.production_ready)
        self.assertTrue(
            any(action.category in {"category_mapping", "media_ingestion_evidence"} for action in packet.actions)
        )

    def test_missing_structured_owner_evidence_becomes_owner_evidence_action(self):
        payload = self.load()
        payload["source_snapshot"]["field_evidence"] = [
            item
            for item in payload["source_snapshot"]["field_evidence"]
            if item.get("product_key") != "RCD-BRD-ENS-1"
        ]
        packet = build_working_catalog_owner_action_packet(payload)
        evidence_actions = [
            action for action in packet.actions if action.category == "owner_evidence"
        ]
        self.assertTrue(evidence_actions)
        self.assertTrue(
            any("Cheezy Ensaymada ¥300" in action.requirement for action in evidence_actions)
        )

    def test_action_keys_are_deterministic_and_unique(self):
        first = build_working_catalog_owner_action_packet(self.load())
        second = build_working_catalog_owner_action_packet(self.load())
        first_keys = [action.action_key for action in first.actions]
        second_keys = [action.action_key for action in second.actions]
        self.assertEqual(first_keys, second_keys)
        self.assertEqual(len(first_keys), len(set(first_keys)))


if __name__ == "__main__":
    unittest.main()
