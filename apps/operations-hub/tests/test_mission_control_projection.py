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
        "tasks": {"task_count": 5, "awaiting_approval": 2},
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


class MissionControlProjectionTests(unittest.TestCase):
    def test_projects_lifecycle_and_result_status_without_customer_payloads(self):
        projection = build_mission_control_lifecycle_projection(operations_dashboard(), audit_model())
        self.assertEqual("read_only", projection["status"])
        self.assertEqual("read_only", projection["mission_control_mode"])
        self.assertEqual(5, projection["operations"]["channel_events"])
        self.assertEqual(5, projection["operations"]["tasks"])
        self.assertEqual(2, projection["automation"]["lifecycle_count"])
        self.assertEqual(8, projection["automation"]["total_audit_events"])
        latest = {item["lifecycle_correlation_id"]: item for item in projection["automation"]["lifecycles"]}
        self.assertEqual("simulated_success", latest["ops:facebook:1"]["latest_outcome"])
        self.assertEqual("simulated_failure", latest["ops:whatsapp:2"]["latest_outcome"])
        serialized = json.dumps(projection, ensure_ascii=False)
        self.assertNotIn("customer_context", serialized)
        self.assertNotIn('"draft_text":', serialized)
        self.assertFalse(projection["channel_reply_authorized"])
        self.assertFalse(projection["mutation_authorized"])
        self.assertEqual("none", projection["authority_effect"])

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

    def test_rejects_non_read_only_inputs(self):
        dashboard = operations_dashboard()
        dashboard["status"] = "mutable"
        with self.assertRaisesRegex(MissionControlProjectionError, "read_only"):
            build_mission_control_lifecycle_projection(dashboard, audit_model())
        audit = audit_model()
        audit["read_only"] = False
        with self.assertRaisesRegex(MissionControlProjectionError, "automation audit must remain read_only"):
            build_mission_control_lifecycle_projection(operations_dashboard(), audit)

    def test_projection_is_deterministic_for_same_inputs(self):
        dashboard = operations_dashboard()
        audit = audit_model()
        first = build_mission_control_lifecycle_projection(dashboard, audit)
        second = build_mission_control_lifecycle_projection(copy.deepcopy(dashboard), copy.deepcopy(audit))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
