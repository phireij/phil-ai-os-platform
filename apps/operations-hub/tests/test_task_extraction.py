import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub import (  # noqa: E402
    OperationsQueue,
    OrderQuoteApprovalDecisionProposalRegister,
    OrderQuoteApprovalRequestRegister,
    OrderQuoteOwnerDecisionPacketRegister,
    OrderReviewQueue,
    build_operations_dashboard,
    evaluate_governance,
    normalize_channel_event,
)
from operations_hub.task_extraction import TaskExtractionError, build_task_candidate  # noqa: E402
from operations_hub.task_queue import TaskCandidateQueue  # noqa: E402


def fixture(source: str):
    return json.loads((ROOT / "fixtures" / f"{source}.json").read_text(encoding="utf-8"))


def candidate(source: str):
    event = normalize_channel_event(fixture(source))
    return build_task_candidate(event, evaluate_governance(event))


class TaskExtractionTests(unittest.TestCase):
    def test_extracts_expected_task_types_across_all_channels(self):
        expected = {
            "facebook": ("order_inquiry_task", "ready_for_operator_review", False),
            "instagram": ("product_inquiry_task", "ready_for_operator_review", False),
            "telegram": ("pickup_inquiry_task", "ready_for_operator_review", False),
            "whatsapp": ("customer_issue_task", "awaiting_approval", True),
            "google_business": ("public_review_task", "awaiting_approval", True),
        }
        for source, (task_type, state, approval_required) in expected.items():
            with self.subTest(source=source):
                task = candidate(source)
                self.assertEqual(task_type, task["task_type"])
                self.assertEqual(state, task["state"])
                self.assertIs(approval_required, task["approval_required"])
                self.assertTrue(task["authority"]["operator_review_only"])
                self.assertEqual("none", task["authority"]["authority_effect"])
                for key, value in task["authority"].items():
                    if key in {"operator_review_only", "authority_effect"}:
                        continue
                    self.assertIs(value, False, key)

    def test_task_candidate_is_deterministic(self):
        first = candidate("facebook")
        second = candidate("facebook")
        self.assertEqual(first["task_candidate_id"], second["task_candidate_id"])
        self.assertEqual(first["lifecycle_correlation_id"], second["lifecycle_correlation_id"])

    def test_queue_is_idempotent_and_summary_hides_customer_text(self):
        queue = TaskCandidateQueue()
        task = candidate("whatsapp")
        self.assertTrue(queue.ingest(task)["accepted"])
        self.assertTrue(queue.ingest(task)["duplicate"])
        model = queue.read_model()
        self.assertEqual(1, model["task_count"])
        self.assertEqual(1, model["duplicate_tasks"])
        self.assertEqual(1, model["awaiting_approval"])
        self.assertEqual(0, model["ready_for_operator_review"])
        serialized = json.dumps(model, ensure_ascii=False)
        self.assertNotIn("I have a problem", serialized)
        self.assertNotIn("customer_context", serialized)
        detail = queue.task_detail(task["task_candidate_id"])
        self.assertEqual(task["customer_context"], detail["customer_context"])
        self.assertFalse(model["execution_authorized"])
        self.assertFalse(model["channel_reply_authorized"])
        self.assertFalse(model["mutation_authorized"])

    def test_queue_rejects_conflicting_content_for_existing_task_id(self):
        queue = TaskCandidateQueue()
        task = candidate("facebook")
        queue.ingest(task)
        conflicting = copy.deepcopy(task)
        conflicting["customer_context"]["text"] = "different customer text"
        with self.assertRaisesRegex(TaskExtractionError, "ID conflicts"):
            queue.ingest(conflicting)
        self.assertEqual(0, queue.read_model()["duplicate_tasks"])

    def test_queue_copies_ingested_candidate_and_detail_state(self):
        queue = TaskCandidateQueue()
        task = candidate("instagram")
        original_text = task["customer_context"]["text"]
        task_id = task["task_candidate_id"]
        queue.ingest(task)

        task["customer_context"]["text"] = "caller mutated input"
        task["authority"]["mutation_authorized"] = True
        detail = queue.task_detail(task_id)
        self.assertEqual(original_text, detail["customer_context"]["text"])
        self.assertFalse(detail["authority"]["mutation_authorized"])

        detail["customer_context"]["text"] = "caller mutated detail"
        detail["authority"]["mutation_authorized"] = True
        reread = queue.task_detail(task_id)
        self.assertEqual(original_text, reread["customer_context"]["text"])
        self.assertFalse(reread["authority"]["mutation_authorized"])

    def test_queue_summarizes_five_channel_task_workload(self):
        queue = TaskCandidateQueue()
        for source in ("facebook", "instagram", "telegram", "whatsapp", "google_business"):
            queue.ingest(candidate(source))
        model = queue.read_model()
        self.assertEqual(5, model["task_count"])
        self.assertEqual(2, model["awaiting_approval"])
        self.assertEqual(3, model["ready_for_operator_review"])
        self.assertEqual(5, len(model["source_counts"]))
        self.assertEqual(1, model["task_type_counts"]["order_inquiry_task"])
        self.assertEqual(1, model["task_type_counts"]["customer_issue_task"])
        self.assertEqual(1, model["task_type_counts"]["public_review_task"])

    def test_dashboard_surfaces_task_counts_without_customer_payloads(self):
        task_queue = TaskCandidateQueue()
        for source in ("facebook", "instagram", "telegram", "whatsapp", "google_business"):
            task_queue.ingest(candidate(source))
        dashboard = build_operations_dashboard(
            OperationsQueue(),
            OrderReviewQueue(),
            OrderQuoteApprovalRequestRegister(),
            OrderQuoteApprovalDecisionProposalRegister(),
            OrderQuoteOwnerDecisionPacketRegister(),
            task_queue=task_queue,
        )
        self.assertEqual(5, dashboard["tasks"]["task_count"])
        self.assertEqual(2, dashboard["tasks"]["awaiting_approval"])
        self.assertEqual(3, dashboard["tasks"]["ready_for_operator_review"])
        serialized = json.dumps(dashboard, ensure_ascii=False)
        self.assertNotIn("Can I order", serialized)
        self.assertNotIn("customer_context", serialized)
        self.assertFalse(dashboard["execution_authorized"])
        self.assertFalse(dashboard["channel_reply_authorized"])
        self.assertFalse(dashboard["mutation_authorized"])

    def test_rejects_governance_authority_expansion(self):
        event = normalize_channel_event(fixture("facebook"))
        governance = evaluate_governance(event)
        governance["execution_authorized"] = True
        with self.assertRaisesRegex(TaskExtractionError, "execution_authorized"):
            build_task_candidate(event, governance)

    def test_rejects_event_governance_mismatch(self):
        event = normalize_channel_event(fixture("facebook"))
        governance = evaluate_governance(event)
        governance["lifecycle_correlation_id"] = "ops:different"
        with self.assertRaisesRegex(TaskExtractionError, "correlation mismatch"):
            build_task_candidate(event, governance)

    def test_queue_rejects_tampered_candidate_authority(self):
        task = candidate("instagram")
        tampered = copy.deepcopy(task)
        tampered["authority"]["channel_reply_authorized"] = True
        with self.assertRaisesRegex(TaskExtractionError, "channel_reply_authorized"):
            TaskCandidateQueue().ingest(tampered)


if __name__ == "__main__":
    unittest.main()
