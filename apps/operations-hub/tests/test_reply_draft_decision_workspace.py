import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub.governance import evaluate_governance  # noqa: E402
from operations_hub.normalizer import normalize_channel_event  # noqa: E402
from operations_hub.reply_draft import build_reply_draft_proposal  # noqa: E402
from operations_hub.reply_draft_decision import build_reply_draft_decision_proposal  # noqa: E402
from operations_hub.reply_draft_decision_register import ReplyDraftDecisionProposalRegister  # noqa: E402
from operations_hub.reply_draft_decision_workspace import (  # noqa: E402
    ReplyDraftDecisionWorkspaceError,
    build_reply_draft_decision_workspace,
)
from operations_hub.reply_draft_register import ReplyDraftRegister  # noqa: E402
from operations_hub.task_extraction import build_task_candidate  # noqa: E402


def fixture(source: str):
    return json.loads((ROOT / "fixtures" / f"{source}.json").read_text(encoding="utf-8"))


def reply_draft(source: str = "facebook"):
    event = normalize_channel_event(fixture(source))
    task = build_task_candidate(event, evaluate_governance(event))
    return build_reply_draft_proposal(task, f"Bounded reply draft for {source}.")


class ReplyDraftDecisionWorkspaceTests(unittest.TestCase):
    def test_workspace_correlates_valid_non_authorizing_proposal(self):
        draft = reply_draft()
        proposal = build_reply_draft_decision_proposal(
            draft,
            recommendation="recommend_future_dispatch",
            reviewer_ref="operator:test",
        )
        drafts = ReplyDraftRegister()
        proposals = ReplyDraftDecisionProposalRegister()
        drafts.register(draft)
        proposals.register(proposal)

        workspace = build_reply_draft_decision_workspace(drafts, proposals)
        self.assertEqual(1, workspace["draft_count"])
        self.assertEqual(1, workspace["recommendation_available"])
        self.assertEqual(draft["task_candidate_id"], workspace["items"][0]["task_candidate_id"])
        self.assertFalse(workspace["channel_reply_authorized"])
        self.assertFalse(workspace["network_dispatch_authorized"])
        self.assertFalse(workspace["mutation_authorized"])

    def test_workspace_fails_closed_on_task_candidate_mismatch(self):
        draft = reply_draft()
        proposal = build_reply_draft_decision_proposal(
            draft,
            recommendation="recommend_future_dispatch",
            reviewer_ref="operator:test",
        )
        proposal["task_candidate_id"] = "ops-task:different"

        drafts = ReplyDraftRegister()
        proposals = ReplyDraftDecisionProposalRegister()
        drafts.register(draft)
        proposals.register(proposal)

        with self.assertRaisesRegex(ReplyDraftDecisionWorkspaceError, "task candidate mismatch"):
            build_reply_draft_decision_workspace(drafts, proposals)


if __name__ == "__main__":
    unittest.main()
