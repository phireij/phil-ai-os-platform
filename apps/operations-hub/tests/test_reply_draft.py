import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub import evaluate_governance, normalize_channel_event  # noqa: E402
from operations_hub.reply_draft import ReplyDraftError, build_reply_draft_proposal  # noqa: E402
from operations_hub.reply_draft_register import ReplyDraftRegister  # noqa: E402
from operations_hub.task_extraction import build_task_candidate  # noqa: E402


def fixture(source: str):
    return json.loads((ROOT / "fixtures" / f"{source}.json").read_text(encoding="utf-8"))


def task(source: str):
    event = normalize_channel_event(fixture(source))
    return build_task_candidate(event, evaluate_governance(event))


class ReplyDraftTests(unittest.TestCase):
    def test_builds_operator_gated_draft_without_reply_authority(self):
        candidate = task("facebook")
        draft = build_reply_draft_proposal(candidate, "Thank you for your message. We will review your order inquiry.")
        self.assertEqual("awaiting_operator_approval", draft["state"])
        self.assertEqual(candidate["task_candidate_id"], draft["task_candidate_id"])
        self.assertEqual(candidate["lifecycle_correlation_id"], draft["lifecycle_correlation_id"])
        self.assertTrue(draft["authority"]["draft_only"])
        self.assertTrue(draft["authority"]["operator_approval_required"])
        self.assertFalse(draft["authority"]["channel_reply_authorized"])
        self.assertFalse(draft["authority"]["network_dispatch_authorized"])
        self.assertEqual("none", draft["authority"]["authority_effect"])
        self.assertIsNone(draft["operator_decision"])

    def test_governance_sensitive_task_still_requires_operator_approval(self):
        candidate = task("whatsapp")
        self.assertTrue(candidate["approval_required"])
        draft = build_reply_draft_proposal(candidate, "Thank you for telling us. We will review this carefully.")
        self.assertTrue(draft["governance_approval_required"])
        self.assertEqual("required", draft["governance_approval_state"])
        self.assertEqual("awaiting_operator_approval", draft["state"])
        self.assertFalse(draft["authority"]["channel_reply_authorized"])

    def test_draft_is_deterministic_for_same_task_text_and_author(self):
        candidate = task("instagram")
        first = build_reply_draft_proposal(candidate, "Thanks for your product inquiry.")
        second = build_reply_draft_proposal(candidate, "Thanks for your product inquiry.")
        self.assertEqual(first["reply_draft_id"], second["reply_draft_id"])

    def test_register_is_idempotent_and_summary_hides_draft_text(self):
        proposal = build_reply_draft_proposal(task("telegram"), "Thank you. We will check pickup availability.")
        register = ReplyDraftRegister()
        self.assertTrue(register.register(proposal)["accepted"])
        self.assertTrue(register.register(proposal)["duplicate"])
        model = register.read_model()
        self.assertEqual(1, model["draft_count"])
        self.assertEqual(1, model["duplicate_drafts"])
        self.assertEqual(1, model["awaiting_operator_approval"])
        self.assertNotIn("draft_text", json.dumps(model, ensure_ascii=False))
        self.assertFalse(model["channel_reply_authorized"])
        self.assertFalse(model["network_dispatch_authorized"])
        self.assertFalse(model["mutation_authorized"])
        self.assertEqual(proposal["draft_text"], register.detail(proposal["reply_draft_id"])["draft_text"])

    def test_register_summarizes_five_channel_drafts(self):
        register = ReplyDraftRegister()
        for source in ("facebook", "instagram", "telegram", "whatsapp", "google_business"):
            register.register(build_reply_draft_proposal(task(source), f"Draft response for {source}."))
        model = register.read_model()
        self.assertEqual(5, model["draft_count"])
        self.assertEqual(5, model["awaiting_operator_approval"])
        self.assertEqual(5, len(model["source_counts"]))

    def test_rejects_tampered_task_authority(self):
        candidate = task("facebook")
        candidate["authority"]["channel_reply_authorized"] = True
        with self.assertRaisesRegex(ReplyDraftError, "channel_reply_authorized"):
            build_reply_draft_proposal(candidate, "Draft")

    def test_register_rejects_tampered_reply_authority(self):
        proposal = build_reply_draft_proposal(task("google_business"), "Thank you for your review.")
        tampered = copy.deepcopy(proposal)
        tampered["authority"]["network_dispatch_authorized"] = True
        with self.assertRaisesRegex(ReplyDraftError, "network_dispatch_authorized"):
            ReplyDraftRegister().register(tampered)

    def test_rejects_unsupported_drafter(self):
        with self.assertRaisesRegex(ReplyDraftError, "drafted_by"):
            build_reply_draft_proposal(task("instagram"), "Draft", drafted_by="auto_sender")


if __name__ == "__main__":
    unittest.main()
