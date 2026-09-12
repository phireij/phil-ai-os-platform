import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub import (  # noqa: E402
    ReplyDraftDecisionProposalRegister,
    ReplyDraftDecisionWorkspaceError,
    ReplyDraftRegister,
    build_reply_draft_decision_proposal,
    build_reply_draft_decision_workspace,
    build_reply_draft_proposal,
    build_task_candidate,
    evaluate_governance,
    normalize_channel_event,
)


def fixture(source: str):
    return json.loads((ROOT / "fixtures" / f"{source}.json").read_text(encoding="utf-8"))


def draft(source: str):
    event = normalize_channel_event(fixture(source))
    task = build_task_candidate(event, evaluate_governance(event))
    return build_reply_draft_proposal(task, f"Bounded reply draft for {source}.")


class ReplyDraftDecisionReviewTests(unittest.TestCase):
    def test_register_is_idempotent_and_hides_review_note(self):
        proposal_register = ReplyDraftDecisionProposalRegister()
        proposal = build_reply_draft_decision_proposal(
            draft("facebook"),
            recommendation="recommend_future_dispatch",
            reviewer_ref="operator:test",
            note="Synthetic note that must not appear in summary.",
        )
        self.assertTrue(proposal_register.register(proposal)["accepted"])
        self.assertTrue(proposal_register.register(proposal)["duplicate"])
        model = proposal_register.read_model()
        self.assertEqual(1, model["proposal_count"])
        self.assertEqual(1, model["duplicate_proposals"])
        self.assertNotIn("Synthetic note", json.dumps(model, ensure_ascii=False))
        self.assertFalse(model["channel_reply_authorized"])
        self.assertFalse(model["network_dispatch_authorized"])
        self.assertFalse(model["mutation_authorized"])

    def test_workspace_correlates_ready_proposals_and_pending_drafts(self):
        drafts = ReplyDraftRegister()
        proposals = ReplyDraftDecisionProposalRegister()
        for source in ("facebook", "instagram", "telegram", "whatsapp", "google_business"):
            reply = draft(source)
            drafts.register(reply)
            if source in {"facebook", "instagram", "telegram"}:
                proposals.register(
                    build_reply_draft_decision_proposal(
                        reply,
                        recommendation="recommend_future_dispatch",
                        reviewer_ref="operator:test",
                    )
                )

        workspace = build_reply_draft_decision_workspace(drafts, proposals)
        self.assertEqual(5, workspace["draft_count"])
        self.assertEqual(2, workspace["awaiting_recommendation"])
        self.assertEqual(3, workspace["recommendation_available"])
        self.assertEqual(0, workspace["conflicting_recommendations"])
        self.assertFalse(workspace["operator_decision_recorded"])
        self.assertFalse(workspace["reply_approved"])
        self.assertFalse(workspace["channel_reply_authorized"])
        self.assertFalse(workspace["network_dispatch_authorized"])

    def test_workspace_surfaces_conflicting_recommendations_without_resolving_them(self):
        drafts = ReplyDraftRegister()
        proposals = ReplyDraftDecisionProposalRegister()
        reply = draft("facebook")
        drafts.register(reply)
        for recommendation in ("recommend_future_dispatch", "request_reply_revision"):
            proposals.register(
                build_reply_draft_decision_proposal(
                    reply,
                    recommendation=recommendation,
                    reviewer_ref="operator:test",
                )
            )
        workspace = build_reply_draft_decision_workspace(drafts, proposals)
        self.assertEqual(1, workspace["conflicting_recommendations"])
        self.assertEqual(
            ["recommend_future_dispatch", "request_reply_revision"],
            workspace["items"][0]["recommendations"],
        )
        self.assertFalse(workspace["items"][0]["operator_decision_recorded"])
        self.assertFalse(workspace["items"][0]["reply_approved"])

    def test_workspace_fails_closed_on_orphaned_proposal(self):
        drafts = ReplyDraftRegister()
        proposals = ReplyDraftDecisionProposalRegister()
        proposal = build_reply_draft_decision_proposal(
            draft("facebook"),
            recommendation="reject_reply_draft",
            reviewer_ref="operator:test",
        )
        proposals.register(proposal)
        with self.assertRaisesRegex(ReplyDraftDecisionWorkspaceError, "unknown reply draft"):
            build_reply_draft_decision_workspace(drafts, proposals)

    def test_register_rejects_authority_tampering(self):
        proposal = build_reply_draft_decision_proposal(
            draft("instagram"),
            recommendation="request_reply_revision",
            reviewer_ref="operator:test",
        )
        tampered = copy.deepcopy(proposal)
        tampered["effects"]["channel_reply_authorized"] = True
        with self.assertRaisesRegex(Exception, "effects must remain false"):
            ReplyDraftDecisionProposalRegister().register(tampered)


if __name__ == "__main__":
    unittest.main()
