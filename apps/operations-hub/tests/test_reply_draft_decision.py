import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub import (  # noqa: E402
    ReplyDraftDecisionError,
    build_reply_draft_decision_proposal,
    build_reply_draft_proposal,
    build_task_candidate,
    evaluate_governance,
    normalize_channel_event,
)


def fixture(source: str):
    return json.loads((ROOT / "fixtures" / f"{source}.json").read_text(encoding="utf-8"))


def reply_draft(source: str):
    event = normalize_channel_event(fixture(source))
    task = build_task_candidate(event, evaluate_governance(event))
    return build_reply_draft_proposal(task, f"Bounded reply draft for {source}.")


class ReplyDraftDecisionTests(unittest.TestCase):
    def test_operator_ready_channels_allow_non_authorizing_recommendations(self):
        for source in ("facebook", "instagram", "telegram"):
            with self.subTest(source=source):
                draft = reply_draft(source)
                proposal = build_reply_draft_decision_proposal(
                    draft,
                    recommendation="recommend_future_dispatch",
                    reviewer_ref="operator:test",
                )
                self.assertEqual("recommendation_only", proposal["state"])
                self.assertEqual(draft["reply_draft_id"], proposal["reply_draft_id"])
                self.assertEqual(draft["lifecycle_correlation_id"], proposal["lifecycle_correlation_id"])
                self.assertFalse(proposal["effects"]["operator_decision_recorded"])
                self.assertFalse(proposal["effects"]["reply_approved"])
                self.assertFalse(proposal["effects"]["channel_reply_authorized"])
                self.assertFalse(proposal["effects"]["network_dispatch_authorized"])
                self.assertFalse(proposal["mutation_authorized"])

    def test_governance_gated_channels_remain_blocked(self):
        for source in ("whatsapp", "google_business"):
            with self.subTest(source=source):
                with self.assertRaisesRegex(ReplyDraftDecisionError, "blocked by governance approval"):
                    build_reply_draft_decision_proposal(
                        reply_draft(source),
                        recommendation="recommend_future_dispatch",
                        reviewer_ref="operator:test",
                    )

    def test_all_supported_recommendations_remain_non_authorizing(self):
        draft = reply_draft("facebook")
        for recommendation in (
            "recommend_future_dispatch",
            "request_reply_revision",
            "reject_reply_draft",
        ):
            with self.subTest(recommendation=recommendation):
                proposal = build_reply_draft_decision_proposal(
                    draft,
                    recommendation=recommendation,
                    reviewer_ref="operator:test",
                    note="Synthetic review only.",
                )
                self.assertEqual(recommendation, proposal["recommendation"])
                self.assertTrue(all(value is False for value in proposal["effects"].values()))
                self.assertFalse(proposal["mutation_authorized"])

    def test_proposal_is_deterministic(self):
        draft = reply_draft("instagram")
        first = build_reply_draft_decision_proposal(
            draft,
            recommendation="request_reply_revision",
            reviewer_ref="operator:test",
            note="Adjust wording.",
        )
        second = build_reply_draft_decision_proposal(
            draft,
            recommendation="request_reply_revision",
            reviewer_ref="operator:test",
            note="Adjust wording.",
        )
        self.assertEqual(first["decision_proposal_id"], second["decision_proposal_id"])

    def test_rejects_reply_authority_tampering(self):
        draft = reply_draft("facebook")
        tampered = copy.deepcopy(draft)
        tampered["authority"]["channel_reply_authorized"] = True
        with self.assertRaisesRegex(ReplyDraftDecisionError, "channel_reply_authorized"):
            build_reply_draft_decision_proposal(
                tampered,
                recommendation="recommend_future_dispatch",
                reviewer_ref="operator:test",
            )

    def test_rejects_unsupported_recommendation(self):
        with self.assertRaisesRegex(ReplyDraftDecisionError, "unsupported reply draft recommendation"):
            build_reply_draft_decision_proposal(
                reply_draft("telegram"),
                recommendation="send_now",
                reviewer_ref="operator:test",
            )


if __name__ == "__main__":
    unittest.main()
