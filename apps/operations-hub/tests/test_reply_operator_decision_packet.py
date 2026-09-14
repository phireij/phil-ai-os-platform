import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub import (  # noqa: E402
    ReplyOperatorDecisionPacketError,
    build_reply_draft_decision_proposal,
    build_reply_draft_proposal,
    build_reply_operator_decision_packet,
    build_task_candidate,
    evaluate_governance,
    normalize_channel_event,
)


def fixture(source: str):
    return json.loads((ROOT / "fixtures" / f"{source}.json").read_text(encoding="utf-8"))


def draft_and_proposal(source: str, recommendation: str = "recommend_future_dispatch"):
    event = normalize_channel_event(fixture(source))
    task = build_task_candidate(event, evaluate_governance(event))
    draft = build_reply_draft_proposal(task, f"Bounded reply draft for {source}.")
    proposal = build_reply_draft_decision_proposal(
        draft,
        recommendation=recommendation,
        reviewer_ref="operator:test",
    )
    return draft, proposal


class ReplyOperatorDecisionPacketTests(unittest.TestCase):
    def test_operator_ready_packet_remains_non_authorizing(self):
        draft, proposal = draft_and_proposal("facebook")
        packet = build_reply_operator_decision_packet(draft, proposal)
        self.assertEqual("awaiting_explicit_operator_decision", packet["state"])
        self.assertEqual(draft["draft_text"], packet["draft_text"])
        self.assertEqual("recommend_future_dispatch", packet["recommendation"])
        self.assertIsNone(packet["operator_decision"])
        self.assertTrue(packet["authority"]["operator_review_only"])
        self.assertTrue(packet["authority"]["operator_decision_required"])
        self.assertEqual("none", packet["authority"]["authority_effect"])
        for field, value in packet["authority"].items():
            if field in {"operator_review_only", "operator_decision_required", "authority_effect"}:
                continue
            self.assertIs(value, False, field)

    def test_packet_is_deterministic(self):
        draft, proposal = draft_and_proposal("instagram", "request_reply_revision")
        first = build_reply_operator_decision_packet(draft, proposal)
        second = build_reply_operator_decision_packet(draft, proposal)
        self.assertEqual(first["operator_decision_packet_id"], second["operator_decision_packet_id"])

    def test_packet_identity_binds_operator_visible_draft_text(self):
        draft, proposal = draft_and_proposal("facebook")
        first = build_reply_operator_decision_packet(draft, proposal)

        tampered_draft = copy.deepcopy(draft)
        tampered_draft["draft_text"] = "Altered operator-visible reply text."
        second = build_reply_operator_decision_packet(tampered_draft, proposal)

        self.assertNotEqual(first["operator_decision_packet_id"], second["operator_decision_packet_id"])
        self.assertEqual("Altered operator-visible reply text.", second["draft_text"])

    def test_packet_identity_binds_operator_visible_locale(self):
        draft, proposal = draft_and_proposal("facebook")
        first = build_reply_operator_decision_packet(draft, proposal)

        tampered_draft = copy.deepcopy(draft)
        tampered_draft["locale"] = "ja" if draft["locale"] != "ja" else "en"
        second = build_reply_operator_decision_packet(tampered_draft, proposal)

        self.assertNotEqual(first["operator_decision_packet_id"], second["operator_decision_packet_id"])

    def test_all_supported_recommendations_can_be_presented_for_explicit_decision(self):
        for recommendation in (
            "recommend_future_dispatch",
            "request_reply_revision",
            "reject_reply_draft",
        ):
            with self.subTest(recommendation=recommendation):
                draft, proposal = draft_and_proposal("telegram", recommendation)
                packet = build_reply_operator_decision_packet(draft, proposal)
                self.assertEqual(recommendation, packet["recommendation"])
                self.assertIsNone(packet["operator_decision"])
                self.assertFalse(packet["authority"]["channel_reply_authorized"])
                self.assertFalse(packet["authority"]["network_dispatch_authorized"])

    def test_governance_gated_channels_cannot_reach_packet(self):
        event = normalize_channel_event(fixture("whatsapp"))
        task = build_task_candidate(event, evaluate_governance(event))
        draft = build_reply_draft_proposal(task, "Bounded complaint reply.")
        synthetic = {
            "schema": "phil-ai-os-operations-reply-draft-decision-proposal",
            "version": 1,
            "state": "recommendation_only",
            "decision_proposal_id": "ops-reply-decision:" + "a" * 24,
            "reply_draft_id": draft["reply_draft_id"],
            "task_candidate_id": draft["task_candidate_id"],
            "lifecycle_correlation_id": draft["lifecycle_correlation_id"],
            "source": draft["source"],
            "recommendation": "recommend_future_dispatch",
            "reviewer_ref": "operator:test",
            "note": "",
            "effects": {
                "operator_decision_recorded": False,
                "reply_approved": False,
                "channel_reply_authorized": False,
                "network_dispatch_authorized": False,
                "execution_authorized": False,
                "woo_commerce_mutation_authorized": False,
                "order_creation_authorized": False,
                "payment_execution_authorized": False,
                "sms_send_authorized": False,
                "inventory_mutation_authorized": False,
                "production_publish_authorized": False,
            },
            "mutation_authorized": False,
        }
        with self.assertRaisesRegex(ReplyOperatorDecisionPacketError, "blocked by governance approval"):
            build_reply_operator_decision_packet(draft, synthetic)

    def test_rejects_correlation_drift(self):
        draft, proposal = draft_and_proposal("facebook")
        tampered = copy.deepcopy(proposal)
        tampered["lifecycle_correlation_id"] = "ops:different"
        with self.assertRaisesRegex(ReplyOperatorDecisionPacketError, "lifecycle_correlation_id mismatch"):
            build_reply_operator_decision_packet(draft, tampered)

    def test_rejects_authority_tampering(self):
        draft, proposal = draft_and_proposal("facebook")
        tampered = copy.deepcopy(proposal)
        tampered["effects"]["channel_reply_authorized"] = True
        with self.assertRaisesRegex(ReplyOperatorDecisionPacketError, "effects must remain false"):
            build_reply_operator_decision_packet(draft, tampered)


if __name__ == "__main__":
    unittest.main()
