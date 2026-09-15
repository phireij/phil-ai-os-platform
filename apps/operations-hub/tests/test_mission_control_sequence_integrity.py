import hashlib
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


def canonical_request_id(lifecycle_id):
    plan_id = f"plan:{lifecycle_id}"
    material = f"{plan_id}|{lifecycle_id}|dry-run".encode("utf-8")
    return "dry-run:" + hashlib.sha256(material).hexdigest()[:24]


def audit_item(lifecycle_id, sequence, stage="plan_created", outcome="simulation_ready"):
    return {
        "sequence": sequence,
        "lifecycle_correlation_id": lifecycle_id,
        "plan_id": f"plan:{lifecycle_id}",
        "request_id": canonical_request_id(lifecycle_id) if stage in {"boundary_preview", "result_preview"} else None,
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


class MissionControlLifecycleSequenceIntegrityTests(unittest.TestCase):
    def test_rejects_duplicate_sequence_within_one_lifecycle(self):
        audit = audit_model(
            [
                audit_item("lifecycle:one", 1),
                audit_item("lifecycle:one", 1, "result_preview", "simulated_success"),
            ]
        )
        with self.assertRaisesRegex(
            MissionControlProjectionError,
            "sequence must be unique within each lifecycle",
        ):
            build_mission_control_lifecycle_projection(operations_dashboard(), audit)

    def test_allows_sequence_restart_across_distinct_lifecycles(self):
        audit = audit_model(
            [
                audit_item("lifecycle:one", 1),
                audit_item("lifecycle:two", 1),
            ]
        )
        projection = build_mission_control_lifecycle_projection(operations_dashboard(), audit)
        lifecycles = projection["automation"]["lifecycles"]
        self.assertEqual(2, projection["automation"]["lifecycle_count"])
        self.assertEqual([1, 1], [item["latest_sequence"] for item in lifecycles])
        self.assertTrue(projection["automation"]["simulated_only"])
        self.assertFalse(projection["mutation_authorized"])


if __name__ == "__main__":
    unittest.main()
