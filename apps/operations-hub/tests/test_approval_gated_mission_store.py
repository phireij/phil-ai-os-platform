import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from operations_hub.approval_gated_mission_store import (
    ApprovalGatedMissionStore,
    ApprovalGatedMissionStoreError,
)
from operations_hub.approval_gated_policy import AssessmentRequest


def assessment(environment="internal", effect="reversible_internal", *factors):
    return AssessmentRequest(environment, effect, frozenset(factors), "approval-gated-policy-2026-10-25")


def steps():
    return [{"description": "Prepare a sandbox-only artifact.", "mode": "simulation", "target_reference": "github:sandbox:mission-control"}]


class ApprovalGatedMissionStoreTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        handle.close()
        self.path = Path(handle.name)
        self.store = ApprovalGatedMissionStore(str(self.path))
        self.store.initialize()

    def tearDown(self):
        self.path.unlink(missing_ok=True)

    def test_mission_plan_and_packet_are_durable_but_inert(self):
        mission = self.store.create_mission("ceo-a", "phil-ai-os", "ceo_conversation", assessment("internal", "reversible_internal", "reversibility"))
        plan = self.store.create_plan("ceo-a", mission["mission_id"], steps())
        packet = self.store.create_approval_packet("ceo-a", mission["mission_id"], plan["plan_id"])
        self.assertEqual("awaiting_approval", plan["approval_state"])
        self.assertEqual(plan["plan_digest"], packet["plan_digest"])
        self.assertEqual(("R1", "ceo_approval", "awaiting_decision"), (packet["risk_level"], packet["required_gate"], packet["decision_state"]))
        for record in (mission, plan, packet):
            self.assertEqual("design_only_inactive", record["activation_state"])
            self.assertFalse(record["execution_authorized"])
            self.assertFalse(record["mutation_authorized"])
            self.assertEqual("none", record["authority_effect"])

    def test_packet_uses_approved_ttl(self):
        mission = self.store.create_mission("ceo-a", "phil-ai-os", "ceo_conversation", assessment("production", "observe", "environment"))
        plan = self.store.create_plan("ceo-a", mission["mission_id"], steps())
        packet = self.store.create_approval_packet("ceo-a", mission["mission_id"], plan["plan_id"])
        delta_seconds = (datetime.fromisoformat(packet["expires_at"].replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds()
        self.assertGreater(delta_seconds, 14 * 60)
        self.assertLessEqual(delta_seconds, 15 * 60)

    def test_r0_and_r4_cannot_create_approval_packets(self):
        for item in (assessment("internal", "observe"), assessment("sandbox", "restricted")):
            with self.subTest(item=item):
                mission = self.store.create_mission("ceo-a", "phil-ai-os", "ceo_conversation", item)
                plan = self.store.create_plan("ceo-a", mission["mission_id"], steps())
                with self.assertRaisesRegex(ApprovalGatedMissionStoreError, "approval_not_required_or_blocked"):
                    self.store.create_approval_packet("ceo-a", mission["mission_id"], plan["plan_id"])

    def test_audit_events_are_chained_and_content_free(self):
        mission = self.store.create_mission("ceo-a", "phil-ai-os", "ceo_conversation", assessment())
        plan = self.store.create_plan("ceo-a", mission["mission_id"], steps())
        self.store.create_approval_packet("ceo-a", mission["mission_id"], plan["plan_id"])
        events = self.store.list_audit_events("ceo-a", mission["mission_id"])
        self.assertEqual([1, 2, 3, 4], [event["sequence"] for event in events])
        self.assertIsNone(events[0]["previous_event_hash"])
        for before, after in zip(events, events[1:]):
            self.assertEqual(before["event_hash"], after["previous_event_hash"])
        self.assertTrue(all(event["content_included"] is False for event in events))
        self.assertTrue(all(event["execution_authorized"] is False for event in events))

    def test_missing_owner_or_unsafe_steps_fail_closed(self):
        mission = self.store.create_mission("ceo-a", "phil-ai-os", "ceo_conversation", assessment())
        with self.assertRaisesRegex(ApprovalGatedMissionStoreError, "mission_not_found"):
            self.store.create_plan("ceo-b", mission["mission_id"], steps())
        with self.assertRaisesRegex(ApprovalGatedMissionStoreError, "plan_step_invalid"):
            self.store.create_plan("ceo-a", mission["mission_id"], [{"description": "No mode", "mode": "execute", "target_reference": "sandbox"}])


if __name__ == "__main__":
    unittest.main()
