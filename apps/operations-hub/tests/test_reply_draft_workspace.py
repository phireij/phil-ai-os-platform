import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub import (  # noqa: E402
    ReplyDraftRegister,
    ReplyDraftWorkspaceError,
    TaskCandidateQueue,
    build_reply_draft_proposal,
    build_reply_draft_workspace,
    build_task_candidate,
    evaluate_governance,
    normalize_channel_event,
)


def fixture(source: str):
    return json.loads((ROOT / "fixtures" / f"{source}.json").read_text(encoding="utf-8"))


def task(source: str):
    event = normalize_channel_event(fixture(source))
    return build_task_candidate(event, evaluate_governance(event))


class ReplyDraftWorkspaceTests(unittest.TestCase):
    def test_workspace_routes_safe_and_governance_gated_drafts(self):
        queue = TaskCandidateQueue()
        register = ReplyDraftRegister()
        for source in ("facebook", "instagram", "telegram", "whatsapp", "google_business"):
            candidate = task(source)
            queue.ingest(candidate)
            register.register(build_reply_draft_proposal(candidate, f"Draft reply for {source}."))

        workspace = build_reply_draft_workspace(queue, register)
        self.assertEqual("read_only", workspace["status"])
        self.assertEqual(5, workspace["draft_count"])
        self.assertEqual(3, workspace["ready_for_operator_approval"])
        self.assertEqual(2, workspace["blocked_by_governance_approval"])
        self.assertFalse(workspace["channel_reply_authorized"])
        self.assertFalse(workspace["network_dispatch_authorized"])
        self.assertFalse(workspace["mutation_authorized"])
        self.assertNotIn("Draft reply for", json.dumps(workspace, ensure_ascii=False))

    def test_workspace_fails_closed_on_orphaned_draft(self):
        queue = TaskCandidateQueue()
        register = ReplyDraftRegister()
        candidate = task("facebook")
        register.register(build_reply_draft_proposal(candidate, "Draft reply."))
        with self.assertRaisesRegex(ReplyDraftWorkspaceError, "unknown task candidate"):
            build_reply_draft_workspace(queue, register)

    def test_workspace_fails_closed_on_correlation_drift(self):
        queue = TaskCandidateQueue()
        register = ReplyDraftRegister()
        candidate = task("facebook")
        queue.ingest(candidate)
        draft = build_reply_draft_proposal(candidate, "Draft reply.")
        draft["lifecycle_correlation_id"] = "ops:different"
        register.register(draft)
        with self.assertRaisesRegex(ReplyDraftWorkspaceError, "correlation mismatch"):
            build_reply_draft_workspace(queue, register)

    def test_workspace_fails_closed_on_task_type_drift(self):
        queue = TaskCandidateQueue()
        register = ReplyDraftRegister()
        candidate = task("facebook")
        queue.ingest(candidate)
        draft = build_reply_draft_proposal(candidate, "Draft reply.")
        draft["task_type"] = "product_inquiry_task"
        register.register(draft)
        with self.assertRaisesRegex(ReplyDraftWorkspaceError, "task_type mismatch"):
            build_reply_draft_workspace(queue, register)

    def test_workspace_fails_closed_on_normalized_intent_drift(self):
        queue = TaskCandidateQueue()
        register = ReplyDraftRegister()
        candidate = task("facebook")
        queue.ingest(candidate)
        draft = build_reply_draft_proposal(candidate, "Draft reply.")
        draft["normalized_intent"] = "product_inquiry"
        register.register(draft)
        with self.assertRaisesRegex(ReplyDraftWorkspaceError, "normalized_intent mismatch"):
            build_reply_draft_workspace(queue, register)


if __name__ == "__main__":
    unittest.main()
