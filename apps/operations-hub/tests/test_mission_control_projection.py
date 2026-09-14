import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub import (  # noqa: E402
    MissionControlProjectionError,
    build_mission_control_lifecycle_projection,
)


def operations_dashboard():
    return {
        "status": "read_only",
        "dashboard": "operations_hub_workload",
        "channels": {"total_events": 5},
        "tasks": {
            "task_count": 5,
            "duplicate_tasks": 1,
            "awaiting_approval": 2,
            "ready_for_operator_review": 3,
            "source_counts": {"facebook": 2, "telegram": 1, "whatsapp": 2},
            "task_type_counts": {"customer_message_review": 2, "order_intent_review": 3},
        },
        "orders": {"pending_staff_review": 1},
        "quotes": {"pending_approval": 1},
        "owner_review": {"pending_packets": 1},
        "privacy": {
            "raw_customer_text_exposed": False,
            "custom_notes_exposed": False,
            "reference_image_names_exposed": False,
        },
        "execution_authorized": False,
        "channel_reply_authorized": False,
        "quote_authorized": False,
        "customer_notification_authorized": False,
        "woo_commerce_mutation_authorized": False,
        "order_creation_authorized": False,
        "payment_execution_authorized": False,
        "sms_send_authorized": False,
        "inventory_mutation_authorized": False,
        "production_publish_authorized": False,
        "mutation_authorized": False,
    }


def audit_model():
    items = []
    sequence = 0
    for lifecycle_id, outcome in (("ops:facebook:1", "simulated_success"), ("ops:whatsapp:2", "simulated_failure")):
        for stage, stage_outcome in (
            ("plan_created", "simulation_ready"),
            ("approval_evaluated", "not_required"),
            ("boundary_preview", "dry_run_created"),
            ("result_preview", outcome),
        ):
            sequence += 1
            items.append(
                {
                    "sequence": sequence,
                    "lifecycle_correlation_id": lifecycle_id,
                    "plan_id": f"plan:{lifecycle_id}",
                    "request_id": None,
                    "stage": stage,
                    "outcome": stage_outcome,
                    "simulated": True,
                    "execution_authorized": False,
                    "channel_reply_authorized": False,
                    "mutation_authorized": False,
                    "authority_effect": "none",
                }
            )
    return {
        "total_events": len(items),
        "by_stage": {
            "plan_created": 2,
            "approval_evaluated": 2,
            "boundary_preview": 2,
            "result_preview": 2,
        },
        "items": items,
        "read_only": True,
        "authority_effect": "none",
    }


def recovery_model():
    return {
        "status": "read_only",
        "queue": "automation_recovery_review",
        "plan_count": 2,
        "duplicate_plans": 1,
        "retry_simulation_count": 1,
        "stop_for_review_count": 1,
        "error_code_counts": {"synthetic_timeout": 1, "synthetic_permanent_failure": 1},
        "automatic_retry": False,
        "retry_authorized": False,
        "automatic_rollback": False,
        "rollback_authorized": False,
        "execution_authorized": False,
        "mutation_authorized": False,
        "authority_effect": "none",
    }


class MissionControlProjectionTests(unittest.TestCase):
    def test_projects_lifecycle_and_result_status_without_customer_payloads(self):
        projection = build_mission_control_lifecycle_projection(operations_dashboard(), audit_model())
        self.assertEqual(4, projection["version"])
        self.assertEqual("read_only", projection["status"])
        self.assertEqual("read_only", projection["mission_control_mode"])
        self.assertEqual(5, projection["operations"]["channel_events"])
        self.assertEqual(5, projection["operations"]["tasks"])
        self.assertEqual(3, projection["operations"]["tasks_ready_for_operator_review"])
        self.assertEqual(2, projection["automation"]["lifecycle_count"])
        self.assertEqual(8, projection["automation"]["total_audit_events"])
        latest = {item["lifecycle_correlation_id"]: item for item in projection["automation"]["lifecycles"]}
        self.assertEqual("simulated_success", latest["ops:facebook:1"]["latest_outcome"])
        self.assertEqual("simulated_failure", latest["ops:whatsapp:2"]["latest_outcome"])
        serialized = json.dumps(projection, ensure_ascii=False)
        self.assertNotIn("customer_context", serialized)
        self.assertNotIn('"draft_text":', serialized)
        self.assertNotIn('"normalized_intent":', serialized)
        self.assertFalse(projection["channel_reply_authorized"])
        self.assertFalse(projection["mutation_authorized"])
        self.assertEqual("none", projection["authority_effect"])

    def test_projects_privacy_safe_task_composition(self):
        projection = build_mission_control_lifecycle_projection(operations_dashboard(), audit_model())
        tasks = projection["task_composition"]
        self.assertEqual(1, tasks["duplicate_tasks"])
        self.assertEqual({"facebook": 2, "telegram": 1, "whatsapp": 2}, tasks["by_source"])
        self.assertEqual({"customer_message_review": 2, "order_intent_review": 3}, tasks["by_type"])
        self.assertTrue(tasks["read_only"])
        self.assertFalse(tasks["customer_payloads_exposed"])
        self.assertFalse(tasks["normalized_intent_exposed"])

    def test_projects_bounded_recovery_posture_without_authority(self):
        projection = build_mission_control_lifecycle_projection(operations_dashboard(), audit_model(), recovery_model())
        recovery = projection["recovery"]
        self.assertEqual(2, recovery["plan_count"])
        self.assertEqual(1, recovery["duplicate_plans"])
        self.assertEqual(1, recovery["retry_simulation_count"])
        self.assertEqual(1, recovery["stop_for_review_count"])
        self.assertEqual(
            {"synthetic_permanent_failure": 1, "synthetic_timeout": 1},
            recovery["error_code_counts"],
        )
        self.assertTrue(recovery["read_only"])
        for field in (
            "automatic_retry",
            "retry_authorized",
            "automatic_rollback",
            "rollback_authorized",
            "execution_authorized",
            "mutation_authorized",
        ):
            self.assertFalse(recovery[field])
        self.assertEqual("none", recovery["authority_effect"])
        attention = {item["kind"]: item for item in projection["attention"]["items"]}
        self.assertEqual(7, projection["attention"]["count"])
        self.assertEqual(1, attention["recovery_stop_for_review"]["count"])

    def test_default_recovery_posture_is_empty_and_non_authorizing(self):
        projection = build_mission_control_lifecycle_projection(operations_dashboard(), audit_model())
        recovery = projection["recovery"]
        self.assertEqual(0, recovery["plan_count"])
        self.assertEqual(0, recovery["retry_simulation_count"])
        self.assertEqual(0, recovery["stop_for_review_count"])
        self.assertTrue(recovery["read_only"])
        self.assertFalse(recovery["retry_authorized"])

    def test_projects_control_plane_posture_without_granting_authority(self):
        projection = build_mission_control_lifecycle_projection(operations_dashboard(), audit_model())
        control = projection["control_plane"]
        self.assertEqual("A0", control["autonomy_level"])
        self.assertEqual("general", control["execution_task_class"])
        self.assertEqual("idle", control["hermes_state"])
        self.assertFalse(control["specialists_enabled"])
        self.assertFalse(control["mission_control_write_enabled"])
        self.assertFalse(control["live_execution_enabled"])
        self.assertTrue(control["operator_decision_required_for_sensitive_actions"])

    def test_projects_operator_attention_counts_deterministically(self):
        projection = build_mission_control_lifecycle_projection(operations_dashboard(), audit_model())
        items = {item["kind"]: item for item in projection["attention"]["items"]}
        self.assertEqual(6, projection["attention"]["count"])
        self.assertEqual(2, items["tasks_awaiting_approval"]["count"])
        self.assertEqual(1, items["orders_pending_staff_review"]["count"])
        self.assertEqual(1, items["quotes_pending_approval"]["count"])
        self.assertEqual(1, items["owner_review_pending_packets"]["count"])
        self.assertEqual(1, items["simulated_lifecycle_failures"]["count"])
        self.assertTrue(projection["attention"]["read_only"])

    def test_rejects_operations_authority_expansion(self):
        dashboard = operations_dashboard()
        dashboard["order_creation_authorized"] = True
        with self.assertRaisesRegex(MissionControlProjectionError, "order_creation_authorized"):
            build_mission_control_lifecycle_projection(dashboard, audit_model())

    def test_rejects_automation_authority_expansion(self):
        audit = audit_model()
        audit["items"][0]["channel_reply_authorized"] = True
        with self.assertRaisesRegex(MissionControlProjectionError, "channel_reply_authorized"):
            build_mission_control_lifecycle_projection(operations_dashboard(), audit)

    def test_rejects_recovery_authority_expansion(self):
        recovery = recovery_model()
        recovery["retry_authorized"] = True
        with self.assertRaisesRegex(MissionControlProjectionError, "retry_authorized"):
            build_mission_control_lifecycle_projection(operations_dashboard(), audit_model(), recovery)

    def test_rejects_non_read_only_inputs(self):
        dashboard = operations_dashboard()
        dashboard["status"] = "mutable"
        with self.assertRaisesRegex(MissionControlProjectionError, "read_only"):
            build_mission_control_lifecycle_projection(dashboard, audit_model())
        audit = audit_model()
        audit["read_only"] = False
        with self.assertRaisesRegex(MissionControlProjectionError, "automation audit must remain read_only"):
            build_mission_control_lifecycle_projection(operations_dashboard(), audit)
        recovery = recovery_model()
        recovery["status"] = "mutable"
        with self.assertRaisesRegex(MissionControlProjectionError, "recovery read model must remain read_only"):
            build_mission_control_lifecycle_projection(operations_dashboard(), audit_model(), recovery)

    def test_rejects_invalid_attention_count_input(self):
        dashboard = operations_dashboard()
        dashboard["tasks"]["awaiting_approval"] = -1
        with self.assertRaisesRegex(MissionControlProjectionError, "tasks_awaiting_approval"):
            build_mission_control_lifecycle_projection(dashboard, audit_model())

    def test_rejects_invalid_task_composition_counts(self):
        dashboard = operations_dashboard()
        dashboard["tasks"]["source_counts"]["facebook"] = -1
        with self.assertRaisesRegex(MissionControlProjectionError, "tasks source_counts.facebook"):
            build_mission_control_lifecycle_projection(dashboard, audit_model())

    def test_rejects_invalid_recovery_counts(self):
        recovery = recovery_model()
        recovery["stop_for_review_count"] = -1
        with self.assertRaisesRegex(MissionControlProjectionError, "recovery stop_for_review_count"):
            build_mission_control_lifecycle_projection(operations_dashboard(), audit_model(), recovery)

    def test_projection_is_deterministic_for_same_inputs(self):
        dashboard = operations_dashboard()
        audit = audit_model()
        recovery = recovery_model()
        first = build_mission_control_lifecycle_projection(dashboard, audit, recovery)
        second = build_mission_control_lifecycle_projection(
            copy.deepcopy(dashboard), copy.deepcopy(audit), copy.deepcopy(recovery)
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
