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
        "channels": {"total_events": 0},
        "tasks": {
            "task_count": 2,
            "duplicate_tasks": 0,
            "awaiting_approval": 1,
            "ready_for_operator_review": 1,
            "source_counts": {"facebook": 1, "telegram": 1},
            "task_type_counts": {"customer_message_review": 1, "order_intent_review": 1},
        },
        "orders": {"pending_staff_review": 0},
        "quotes": {"pending_approval": 0},
        "owner_review": {"pending_packets": 0},
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
    return {
        "read_only": True,
        "total_events": 0,
        "by_stage": {},
        "items": [],
        "plan_fingerprints_exposed": False,
        "authority_effect": "none",
    }


def recovery_model():
    return {
        "status": "read_only",
        "queue": "automation_recovery_review",
        "plan_count": 2,
        "duplicate_plans": 0,
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


class MissionControlAggregateIntegrityTests(unittest.TestCase):
    def test_rejects_recovery_action_counts_that_do_not_match_plan_count(self):
        recovery = recovery_model()
        recovery["retry_simulation_count"] = 0
        with self.assertRaisesRegex(MissionControlProjectionError, "action counts must match"):
            build_mission_control_lifecycle_projection(operations_dashboard(), audit_model(), recovery)

    def test_rejects_recovery_error_counts_that_do_not_match_plan_count(self):
        recovery = recovery_model()
        recovery["error_code_counts"] = {"synthetic_timeout": 1}
        with self.assertRaisesRegex(MissionControlProjectionError, "error_code_counts must match"):
            build_mission_control_lifecycle_projection(operations_dashboard(), audit_model(), recovery)

    def test_rejects_task_state_counts_that_do_not_match_task_count(self):
        dashboard = operations_dashboard()
        dashboard["tasks"]["ready_for_operator_review"] = 0
        with self.assertRaisesRegex(MissionControlProjectionError, "task state counts must match"):
            build_mission_control_lifecycle_projection(dashboard, audit_model())

    def test_rejects_task_source_counts_that_do_not_match_task_count(self):
        dashboard = operations_dashboard()
        dashboard["tasks"]["source_counts"] = {"facebook": 1}
        with self.assertRaisesRegex(MissionControlProjectionError, "source_counts must match"):
            build_mission_control_lifecycle_projection(dashboard, audit_model())

    def test_rejects_task_type_counts_that_do_not_match_task_count(self):
        dashboard = operations_dashboard()
        dashboard["tasks"]["task_type_counts"] = {"customer_message_review": 1}
        with self.assertRaisesRegex(MissionControlProjectionError, "task_type_counts must match"):
            build_mission_control_lifecycle_projection(dashboard, audit_model())


if __name__ == "__main__":
    unittest.main()
