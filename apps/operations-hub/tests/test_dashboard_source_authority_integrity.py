import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub.dashboard import OperationsDashboardError, _read_only  # noqa: E402


class OperationsDashboardSourceAuthorityIntegrityTests(unittest.TestCase):
    def test_accepts_read_only_source_when_all_declared_authority_is_false(self):
        model = {
            "status": "read_only",
            "execution_authorized": False,
            "channel_reply_authorized": False,
            "quote_authorized": False,
            "customer_notification_authorized": False,
            "order_creation_authorized": False,
            "payment_execution_authorized": False,
            "mutation_authorized": False,
        }
        self.assertIs(model, _read_only(model, "source"))

    def test_rejects_any_declared_authority_expansion(self):
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
                model = {"status": "read_only", "mutation_authorized": False, field: True}
                with self.assertRaisesRegex(OperationsDashboardError, field):
                    _read_only(model, "source")

    def test_rejects_future_authorized_capability_fail_closed(self):
        model = {
            "status": "read_only",
            "mutation_authorized": False,
            "future_capability_authorized": True,
        }
        with self.assertRaisesRegex(OperationsDashboardError, "future_capability_authorized"):
            _read_only(model, "source")

    def test_rejects_non_boolean_or_missing_false_authority_value(self):
        for value in (None, 0, 1, "false"):
            with self.subTest(value=value):
                model = {
                    "status": "read_only",
                    "mutation_authorized": False,
                    "quote_authorized": value,
                }
                with self.assertRaisesRegex(OperationsDashboardError, "quote_authorized"):
                    _read_only(model, "source")


if __name__ == "__main__":
    unittest.main()
