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
        "channels": {"total_events": 0},
        "tasks": {
            "task_count": 0,
            "duplicate_tasks": 0,
            "awaiting_approval": 0,
            "ready_for_operator_review": 0,
            "source_counts": {},
            "task_type_counts": {},
        },
        "orders": {"pending_staff_review": 0},
        "quotes": {"pending_approval": 0},
        "owner_review": {"pending_packets": 0},
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


def audit_item(lifecycle_id, plan_id, sequence, stage="plan_created", outcome="simulation_ready"):
    return {
        "sequence": sequence,
        "lifecycle_correlation_id": lifecycle_id,
        "plan_id": plan_id,
        "request_id": f"dry-run:{lifecycle_id}" if stage in {"boundary_preview", "result_preview"} else None,
        "stage": stage,
        "outcome": outcome,
        "simulated": True,
        "execution_authorized": False,
        "channel_reply_authorized": False,
        "mutation_authorized": False,
        "authority_effect": "none",
    }


def audit_model(items):
    by_stage = {}
    for item in items:
        by_stage[item["stage"]] = by_stage.get(item["stage"], 0) + 1
    return {
        "read_only": True,
        "total_events": len(items),
        "by_stage": by_stage,
        "items": items,
        "plan_fingerprints_exposed": False,
        "authority_effect": "none",
    }


class MissionControlLifecyclePlanIntegrityTests(unittest.TestCase):
    def test_rejects_missing_plan_id(self):
        item = audit_item("lifecycle:one", "plan:one", 1)
        del item["plan_id"]
        with self.assertRaisesRegex(MissionControlProjectionError, "plan_id is required"):
            build_mission_control_lifecycle_projection(
                operations_dashboard(),
                audit_model([item]),
            )

    def test_rejects_multiple_plan_ids_within_one_lifecycle(self):
        audit = audit_model(
            [
                audit_item("lifecycle:one", "plan:one", 1),
                audit_item("lifecycle:one", "plan:two", 2, "result_preview", "simulated_success"),
            ]
        )
        with self.assertRaisesRegex(
            MissionControlProjectionError,
            "lifecycle must reference exactly one plan_id",
        ):
            build_mission_control_lifecycle_projection(operations_dashboard(), audit)

    def test_rejects_one_plan_id_across_multiple_lifecycles(self):
        audit = audit_model(
            [
                audit_item("lifecycle:one", "plan:shared", 1),
                audit_item("lifecycle:two", "plan:shared", 1),
            ]
        )
        with self.assertRaisesRegex(
            MissionControlProjectionError,
            "plan_id must reference exactly one lifecycle",
        ):
            build_mission_control_lifecycle_projection(operations_dashboard(), audit)

    def test_preserves_valid_lifecycle_without_exposing_plan_id(self):
        audit = audit_model(
            [
                audit_item("lifecycle:one", "plan:one", 1),
                audit_item("lifecycle:one", "plan:one", 2, "result_preview", "simulated_success"),
            ]
        )
        projection = build_mission_control_lifecycle_projection(operations_dashboard(), audit)
        lifecycle = projection["automation"]["lifecycles"][0]
        self.assertEqual(1, projection["automation"]["lifecycle_count"])
        self.assertEqual(2, lifecycle["latest_sequence"])
        self.assertEqual("simulated_success", lifecycle["latest_outcome"])
        self.assertNotIn('"plan_id"', json.dumps(projection, ensure_ascii=False))
        self.assertFalse(projection["mutation_authorized"])


if __name__ == "__main__":
    unittest.main()
