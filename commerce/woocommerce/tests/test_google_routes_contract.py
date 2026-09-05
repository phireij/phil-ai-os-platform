import unittest

from phil_ai_os_woocommerce.google_routes_contract import (
    GOOGLE_ROUTES_COMPUTE_URL,
    GOOGLE_ROUTES_FIELD_MASK,
    GoogleRoutesComputeContract,
    GoogleRoutesContractError,
    GoogleRoutesResponseNormalizer,
)


class GoogleRoutesComputeContractTests(unittest.TestCase):
    def test_request_builder_is_network_inert_and_requests_only_driving_route_facts(self):
        contract = GoogleRoutesComputeContract(
            origin_address="Ruby shop configured address",
            destination_address="Customer destination",
        )
        body = contract.request_body()

        self.assertEqual(contract.endpoint(), GOOGLE_ROUTES_COMPUTE_URL)
        self.assertEqual(body["travelMode"], "DRIVE")
        self.assertEqual(body["routingPreference"], "TRAFFIC_AWARE")
        self.assertFalse(body["computeAlternativeRoutes"])
        self.assertEqual(body["units"], "METRIC")
        self.assertEqual(body["extraComputations"], ["TOLLS"])
        self.assertFalse(body["routeModifiers"]["avoidTolls"])
        self.assertNotIn("apiKey", body)
        self.assertNotIn("X-Goog-Api-Key", body)

    def test_field_mask_is_explicit_and_has_no_wildcard(self):
        self.assertEqual(
            GOOGLE_ROUTES_FIELD_MASK,
            "routes.distanceMeters,routes.duration,routes.travelAdvisory.tollInfo",
        )
        self.assertNotIn("*", GOOGLE_ROUTES_FIELD_MASK)

    def test_normalizes_distance_duration_and_no_toll_route(self):
        result = GoogleRoutesResponseNormalizer.normalize(
            {"routes": [{"distanceMeters": 9876, "duration": "1234s"}]}
        )
        self.assertEqual(result["distance_meters"], 9876)
        self.assertEqual(result["duration_seconds"], 1234)
        self.assertFalse(result["tolls_expected"])
        self.assertIsNone(result["toll_yen"])
        self.assertFalse(result["exceptional_parking_expected"])

    def test_fractional_duration_rounds_up_conservatively(self):
        result = GoogleRoutesResponseNormalizer.normalize(
            {"routes": [{"distanceMeters": 1000, "duration": "60.1s"}]}
        )
        self.assertEqual(result["duration_seconds"], 61)

    def test_jpy_toll_price_is_normalized_to_whole_yen(self):
        result = GoogleRoutesResponseNormalizer.normalize(
            {
                "routes": [
                    {
                        "distanceMeters": 12_000,
                        "duration": "1800s",
                        "travelAdvisory": {
                            "tollInfo": {
                                "estimatedPrice": [
                                    {"currencyCode": "JPY", "units": "599", "nanos": 1}
                                ]
                            }
                        },
                    }
                ]
            }
        )
        self.assertTrue(result["tolls_expected"])
        self.assertEqual(result["toll_yen"], 600)

    def test_toll_info_without_usable_price_fails_closed_to_manual_price_state(self):
        for toll_info in ({}, {"estimatedPrice": []}, {"estimatedPrice": [{"currencyCode": "USD", "units": "5"}]}):
            with self.subTest(toll_info=toll_info):
                result = GoogleRoutesResponseNormalizer.normalize(
                    {
                        "routes": [
                            {
                                "distanceMeters": 12_000,
                                "duration": "1800s",
                                "travelAdvisory": {"tollInfo": toll_info},
                            }
                        ]
                    }
                )
                self.assertTrue(result["tolls_expected"])
                self.assertIsNone(result["toll_yen"])

    def test_multiple_routes_are_rejected_to_avoid_implicit_route_choice(self):
        with self.assertRaisesRegex(GoogleRoutesContractError, "exactly one"):
            GoogleRoutesResponseNormalizer.normalize(
                {
                    "routes": [
                        {"distanceMeters": 1000, "duration": "100s"},
                        {"distanceMeters": 1100, "duration": "90s"},
                    ]
                }
            )

    def test_invalid_route_values_fail_closed(self):
        bad_payloads = [
            {"routes": []},
            {"routes": [{"distanceMeters": -1, "duration": "10s"}]},
            {"routes": [{"distanceMeters": 1, "duration": "ten seconds"}]},
            {"routes": [{"distanceMeters": 1, "duration": "10s", "travelAdvisory": []}]},
        ]
        for payload in bad_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(GoogleRoutesContractError):
                    GoogleRoutesResponseNormalizer.normalize(payload)

    def test_normalized_observation_contains_no_address_or_authority(self):
        result = GoogleRoutesResponseNormalizer.normalize(
            {"routes": [{"distanceMeters": 1000, "duration": "100s"}]}
        )
        rendered = repr(result)
        self.assertNotIn("address", rendered.lower())
        self.assertNotIn("payment", rendered.lower())
        self.assertNotIn("dispatch", rendered.lower())


if __name__ == "__main__":
    unittest.main()
