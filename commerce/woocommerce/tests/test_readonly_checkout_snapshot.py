import unittest

from phil_ai_os_woocommerce.adapter import ProductionConnectivityBlocked
from phil_ai_os_woocommerce.readonly_checkout_snapshot import collect_checkout_snapshot


class RecordingTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def request(self, method, path, *, params=None, json_body=None):
        self.calls.append({"method": method, "path": path, "params": params, "json_body": json_body})
        return self.payload


class ReadOnlyCheckoutSnapshotTests(unittest.TestCase):
    def test_snapshot_uses_get_only_and_strips_gateway_settings(self):
        transport = RecordingTransport(
            [
                {
                    "id": "komoju",
                    "title": "KOMOJU",
                    "enabled": True,
                    "order": 2,
                    "method_title": "KOMOJU",
                    "method_supports": ["products", "refunds"],
                    "settings": {
                        "secret_key": {"value": "must-not-leak"},
                        "webhook_secret": {"value": "must-not-leak-either"},
                    },
                },
                {
                    "id": "bacs",
                    "title": "Direct bank transfer",
                    "enabled": False,
                    "order": 1,
                    "method_title": "BACS",
                    "method_supports": ["products"],
                },
            ]
        )

        snapshot = collect_checkout_snapshot(transport, captured_at="2026-09-04T00:00:00Z").as_dict()

        self.assertTrue(snapshot["network_read_only"])
        self.assertFalse(snapshot["mutation_authorized"])
        self.assertFalse(snapshot["payment_execution_authorized"])
        self.assertFalse(snapshot["production_publish_authorized"])
        self.assertEqual(snapshot["scope"], "woocommerce_payment_gateway_metadata_read_only")
        self.assertEqual([item["id"] for item in snapshot["gateways"]], ["bacs", "komoju"])
        self.assertNotIn("settings", snapshot["gateways"][1])
        self.assertNotIn("must-not-leak", repr(snapshot))
        self.assertEqual(transport.calls, [{"method": "GET", "path": "/payment_gateways", "params": None, "json_body": None}])

    def test_snapshot_rejects_non_list_payload(self):
        with self.assertRaises(ProductionConnectivityBlocked):
            collect_checkout_snapshot(RecordingTransport({"id": "komoju"}))

    def test_snapshot_rejects_missing_gateway_id(self):
        with self.assertRaises(ProductionConnectivityBlocked):
            collect_checkout_snapshot(RecordingTransport([{"enabled": True}]))

    def test_snapshot_rejects_invalid_supports_shape(self):
        with self.assertRaises(ProductionConnectivityBlocked):
            collect_checkout_snapshot(RecordingTransport([{"id": "komoju", "method_supports": "refunds"}]))


if __name__ == "__main__":
    unittest.main()
