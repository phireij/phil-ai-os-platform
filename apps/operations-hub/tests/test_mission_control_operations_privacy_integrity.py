import copy
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


class MissionControlOperationsPrivacyIntegrityTests(unittest.TestCase):
    def test_preserves_explicitly_hidden_operations_privacy(self):
        projection = build_mission_control_lifecycle_projection(
            operations_dashboard(), audit_model()
        )
        self.assertFalse(projection["privacy"]["raw_customer_text_exposed"])
        self.assertFalse(projection["privacy"]["custom_notes_exposed"])
        self.assertFalse(projection["privacy"]["reference_image_names_exposed"])
        self.assertFalse(projection["mutation_authorized"])

    def test_rejects_missing_operations_privacy_object(self):
        dashboard = operations_dashboard()
        del dashboard["privacy"]
        with self.assertRaisesRegex(
            MissionControlProjectionError,
            "operations dashboard privacy must be an object",
        ):
            build_mission_control_lifecycle_projection(dashboard, audit_model())

    def test_rejects_exposed_operations_privacy_fields(self):
        for field in (
            "raw_customer_text_exposed",
            "custom_notes_exposed",
            "reference_image_names_exposed",
        ):
            with self.subTest(field=field):
                dashboard = operations_dashboard()
                dashboard["privacy"][field] = True
                with self.assertRaisesRegex(MissionControlProjectionError, field):
                    build_mission_control_lifecycle_projection(dashboard, audit_model())

    def test_rejects_missing_operations_privacy_fields(self):
        for field in (
            "raw_customer_text_exposed",
            "custom_notes_exposed",
            "reference_image_names_exposed",
        ):
            with self.subTest(field=field):
                dashboard = copy.deepcopy(operations_dashboard())
                del dashboard["privacy"][field]
                with self.assertRaisesRegex(MissionControlProjectionError, field):
                    build_mission_control_lifecycle_projection(dashboard, audit_model())


if __name__ == "__main__":
    unittest.main()
