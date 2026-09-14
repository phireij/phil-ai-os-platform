import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub.dashboard import OperationsDashboardError, _read_only  # noqa: E402


class OperationsDashboardItemAuthorityIntegrityTests(unittest.TestCase):
    def test_accepts_read_only_items_when_declared_authority_is_false(self):
        model = {
            "status": "read_only",
            "mutation_authorized": False,
            "items": [
                {
                    "quote_authorized": False,
                    "customer_notification_authorized": False,
                    "mutation_authorized": False,
                }
            ],
        }
        self.assertIs(model, _read_only(model, "source"))

    def test_rejects_item_authority_expansion(self):
        for field in (
            "mutation_authorized",
            "execution_authorized",
            "channel_reply_authorized",
            "quote_authorized",
            "customer_notification_authorized",
            "order_creation_authorized",
            "payment_execution_authorized",
        ):
            with self.subTest(field=field):
                model = {
                    "status": "read_only",
                    "mutation_authorized": False,
                    "items": [{"mutation_authorized": False, field: True}],
                }
                with self.assertRaisesRegex(OperationsDashboardError, field):
                    _read_only(model, "source")

    def test_rejects_future_item_authority_capability_fail_closed(self):
        model = {
            "status": "read_only",
            "mutation_authorized": False,
            "items": [
                {
                    "mutation_authorized": False,
                    "future_item_capability_authorized": True,
                }
            ],
        }
        with self.assertRaisesRegex(OperationsDashboardError, "future_item_capability_authorized"):
            _read_only(model, "source")

    def test_rejects_malformed_item_shape_before_projection(self):
        model = {
            "status": "read_only",
            "mutation_authorized": False,
            "items": ["not-an-object"],
        }
        with self.assertRaisesRegex(OperationsDashboardError, "item\[0\] must be an object"):
            _read_only(model, "source")


if __name__ == "__main__":
    unittest.main()
