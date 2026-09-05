import unittest

from phil_ai_os_woocommerce.fulfillment_policy import RubyCarDeliveryPolicy
from phil_ai_os_woocommerce.ruby_car_routing import (
    RubyCarRouteRequest,
    RubyCarRoutingAdapter,
    RubyCarRoutingConfig,
    RubyCarRoutingError,
)


class FakeRoutingTransport:
    def __init__(self, payload=None, error=None):
        self.payload = payload or {
            "distance_meters": 12_100,
            "duration_seconds": 1_800,
            "tolls_expected": False,
        }
        self.error = error
        self.calls = []

    def compute_route(self, *, destination_address, timeout_seconds):
        self.calls.append(
            {
                "destination_address": destination_address,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.error:
            raise self.error
        return self.payload


class RubyCarRoutingAdapterTests(unittest.TestCase):
    def request(self, *, prefecture="Chiba"):
        return RubyCarRouteRequest(
            destination_address="Customer address only for injected route computation",
            destination_prefecture=prefecture,
        )

    def enabled_adapter(self, transport):
        return RubyCarRoutingAdapter(
            RubyCarRoutingConfig(provider="google_routes_future", enabled=True, timeout_seconds=4.0),
            transport,
        )

    def test_disabled_by_default_and_never_calls_transport(self):
        transport = FakeRoutingTransport()
        result = RubyCarRoutingAdapter(transport=transport).compute(self.request())

        self.assertEqual(result.status, "disabled")
        self.assertFalse(result.route_request_attempted)
        self.assertTrue(result.requires_manual_review)
        self.assertEqual(transport.calls, [])
        self.assertFalse(result.payment_authorized)
        self.assertFalse(result.dispatch_authorized)
        self.assertFalse(result.order_mutation_authorized)

    def test_outside_service_area_short_circuits_without_route_call(self):
        transport = FakeRoutingTransport()
        result = self.enabled_adapter(transport).compute(self.request(prefecture="Ibaraki"))

        self.assertEqual(result.status, "not_routable")
        self.assertFalse(result.route_request_attempted)
        self.assertEqual(transport.calls, [])
        self.assertIn("destination_prefecture_outside_service_area", result.reasons)

    def test_enabled_injected_transport_maps_one_way_route_facts(self):
        transport = FakeRoutingTransport(
            {
                "distance_meters": 10_001,
                "duration_seconds": 2_100,
                "tolls_expected": True,
                "toll_yen": 600,
                "exceptional_parking_expected": False,
            }
        )
        result = self.enabled_adapter(transport).compute(self.request(prefecture="Tokyo"))

        self.assertEqual(result.status, "route_facts_ready")
        self.assertTrue(result.route_request_attempted)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(transport.calls[0]["timeout_seconds"], 4.0)
        self.assertEqual(result.route_facts.destination_prefecture, "Tokyo")
        self.assertEqual(result.route_facts.distance_meters, 10_001)
        self.assertEqual(result.route_facts.toll_yen, 600)
        self.assertEqual(result.route_facts.origin_ref, "ruby_shop_ichikawa")

        quote = RubyCarDeliveryPolicy.quote(result.route_facts)
        self.assertEqual(quote.status, "provisional_quote")
        self.assertEqual(quote.base_delivery_fee_yen, 2_650)
        self.assertEqual(quote.provisional_total_yen, 3_250)
        self.assertFalse(quote.payment_authorized)

    def test_missing_transport_fails_closed(self):
        adapter = RubyCarRoutingAdapter(
            RubyCarRoutingConfig(provider="google_routes_future", enabled=True)
        )
        with self.assertRaises(RubyCarRoutingError):
            adapter.compute(self.request())

    def test_transport_failure_has_no_retry(self):
        transport = FakeRoutingTransport(error=TimeoutError("simulated"))
        with self.assertRaisesRegex(RubyCarRoutingError, "failed safely"):
            self.enabled_adapter(transport).compute(self.request())
        self.assertEqual(len(transport.calls), 1)

    def test_malformed_provider_payload_fails_closed(self):
        transport = FakeRoutingTransport({"distance_meters": 1_000})
        with self.assertRaisesRegex(RubyCarRoutingError, "distance/duration"):
            self.enabled_adapter(transport).compute(self.request())
        self.assertEqual(len(transport.calls), 1)

    def test_boolean_toll_value_is_rejected(self):
        transport = FakeRoutingTransport(
            {
                "distance_meters": 1_000,
                "duration_seconds": 600,
                "tolls_expected": True,
                "toll_yen": True,
            }
        )
        with self.assertRaisesRegex(RubyCarRoutingError, "toll_yen"):
            self.enabled_adapter(transport).compute(self.request())

    def test_safe_audit_projection_does_not_include_customer_address(self):
        result = self.enabled_adapter(FakeRoutingTransport()).compute(self.request())
        audit = result.safe_audit_dict()
        rendered = repr(audit)

        self.assertNotIn("Customer address", rendered)
        self.assertNotIn("destination_address", audit)
        self.assertFalse(audit["payment_authorized"])
        self.assertFalse(audit["dispatch_authorized"])
        self.assertFalse(audit["order_mutation_authorized"])

    def test_request_rejects_non_shop_origin(self):
        with self.assertRaisesRegex(ValueError, "Ichikawa shop"):
            RubyCarRouteRequest(
                destination_address="x",
                destination_prefecture="Chiba",
                origin_ref="other_origin",
            )

    def test_config_requires_positive_timeout(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            RubyCarRoutingConfig(provider="future", timeout_seconds=0)


if __name__ == "__main__":
    unittest.main()
