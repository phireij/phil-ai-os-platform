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


def audit_item(sequence, stage, outcome, request_id=None):
    return {
        "sequence": sequence,
        "lifecycle_correlation_id": "lifecycle:one",
        "plan_id": "plan:one",
        "request_id": request_id,
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


class MissionControlRequestIntegrityTests(unittest.TestCase):
    def test_allows_later_stage_only_with_request_id_without_exposing_it(self):
        audit = audit_model(
            [audit_item(1, "result_preview", "simulated_failure", "dry-run:one")]
        )
        projection = build_mission_control_lifecycle_projection(operations_dashboard(), audit)
        lifecycle = projection["automation"]["lifecycles"][0]
        self.assertEqual("result_preview", lifecycle["latest_stage"])
        self.assertEqual("simulated_failure", lifecycle["latest_outcome"])
        self.assertNotIn('"request_id"', json.dumps(projection, ensure_ascii=False))
        self.assertFalse(projection["mutation_authorized"])

    def test_rejects_missing_request_id_for_boundary_or_result(self):
        for stage, outcome in (
            ("boundary_preview", "dry_run_created"),
            ("result_preview", "simulated_success"),
        ):
            with self.subTest(stage=stage):
                audit = audit_model([audit_item(1, stage, outcome)])
                with self.assertRaisesRegex(
                    MissionControlProjectionError,
                    "boundary/result request_id is required",
                ):
                    build_mission_control_lifecycle_projection(operations_dashboard(), audit)

    def test_rejects_request_id_outside_boundary_or_result_stage(self):
        audit = audit_model(
            [audit_item(1, "plan_created", "simulation_ready", "dry-run:unexpected")]
        )
        with self.assertRaisesRegex(
            MissionControlProjectionError,
            "request_id must remain unset outside boundary/result stages",
        ):
            build_mission_control_lifecycle_projection(operations_dashboard(), audit)

    def test_rejects_conflicting_request_ids_within_one_lifecycle(self):
        audit = audit_model(
            [
                audit_item(1, "boundary_preview", "dry_run_created", "dry-run:one"),
                audit_item(2, "result_preview", "simulated_success", "dry-run:two"),
            ]
        )
        with self.assertRaisesRegex(
            MissionControlProjectionError,
            "lifecycle must reference exactly one request_id",
        ):
            build_mission_control_lifecycle_projection(operations_dashboard(), audit)


if __name__ == "__main__":
    unittest.main()
