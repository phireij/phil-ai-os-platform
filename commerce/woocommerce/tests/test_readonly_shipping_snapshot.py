import unittest

from phil_ai_os_woocommerce.adapter import ProductionConnectivityBlocked
from phil_ai_os_woocommerce.readonly_shipping_snapshot import collect_shipping_snapshot


class FakeTransport:
    def __init__(self):
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == "/shipping/zones":
            return [
                {"id": 1, "name": "Japan", "order": 1},
                {"id": 0, "name": "Locations not covered", "order": 99},
            ]
        if path == "/shipping/zones/1/methods":
            return [
                {
                    "instance_id": 11,
                    "method_id": "flat_rate",
                    "title": "Yamato Ambient",
                    "enabled": True,
                    "order": 2,
                    "method_title": "Flat rate",
                    "settings": {"cost": {"value": "SECRET-LIKE-OPERATIONAL-VALUE"}},
                },
                {
                    "instance_id": 10,
                    "method_id": "local_pickup",
                    "title": "Shop Pickup",
                    "enabled": True,
                    "order": 1,
                    "method_title": "Local pickup",
                    "settings": {"cost": {"value": "0"}},
                },
            ]
        if path == "/shipping/zones/0/methods":
            return []
        raise AssertionError(path)


class ReadOnlyShippingSnapshotTests(unittest.TestCase):
    def test_collects_zone_and_method_metadata_using_get_only(self):
        transport = FakeTransport()
        snapshot = collect_shipping_snapshot(
            transport,
            captured_at="2026-09-11T00:00:00Z",
        )
        payload = snapshot.as_dict()

        self.assertEqual(payload["scope"], "woocommerce_shipping_zone_method_metadata_read_only")
        self.assertTrue(payload["network_read_only"])
        self.assertFalse(payload["mutation_authorized"])
        self.assertFalse(payload["payment_execution_authorized"])
        self.assertFalse(payload["production_publish_authorized"])
        self.assertEqual([zone["id"] for zone in payload["zones"]], [1, 0])
        self.assertEqual(
            [method["instance_id"] for method in payload["zones"][0]["methods"]],
            [10, 11],
        )
        self.assertTrue(all(method == "GET" for method, _, _ in transport.calls))

    def test_excludes_shipping_method_settings_from_snapshot(self):
        payload = collect_shipping_snapshot(FakeTransport()).as_dict()
        for zone in payload["zones"]:
            for method in zone["methods"]:
                self.assertNotIn("settings", method)
        self.assertNotIn("SECRET-LIKE-OPERATIONAL-VALUE", str(payload))

    def test_invalid_zone_response_fails_closed(self):
        class BadTransport:
            def request(self, method, path, **kwargs):
                return {"not": "a list"}

        with self.assertRaises(ProductionConnectivityBlocked):
            collect_shipping_snapshot(BadTransport())

    def test_missing_method_id_fails_closed(self):
        class BadMethodTransport(FakeTransport):
            def request(self, method, path, **kwargs):
                if path == "/shipping/zones":
                    return [{"id": 1, "name": "Japan", "order": 1}]
                if path == "/shipping/zones/1/methods":
                    return [{"instance_id": 9, "enabled": True, "order": 1}]
                return super().request(method, path, **kwargs)

        with self.assertRaises(ProductionConnectivityBlocked):
            collect_shipping_snapshot(BadMethodTransport())


if __name__ == "__main__":
    unittest.main()
