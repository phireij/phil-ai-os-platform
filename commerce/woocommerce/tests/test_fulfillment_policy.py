import unittest

from phil_ai_os_woocommerce.fulfillment_policy import (
    CartFulfillmentDecision,
    CartLine,
    CartPackingFacts,
    FulfillmentPolicyError,
    ProductFulfillmentRule,
    RubyCarDeliveryPolicy,
    RubyCarRouteFacts,
    RubyCartFulfillmentPolicy,
)


def product(
    sku: str,
    temperature: str,
    *,
    cool_eligible: bool = False,
    is_cake: bool = False,
    yamato_allowed: bool = True,
    ruby_car_allowed: bool = False,
    pickup_allowed: bool = True,
) -> ProductFulfillmentRule:
    return ProductFulfillmentRule(
        sku=sku,
        temperature_class=temperature,
        cool_eligible=cool_eligible,
        is_cake=is_cake,
        yamato_allowed=yamato_allowed,
        ruby_car_allowed=ruby_car_allowed,
        pickup_allowed=pickup_allowed,
    )


class MixedCartFulfillmentTests(unittest.TestCase):
    def test_ambient_cart_defaults_to_regular_yamato_and_can_upgrade_when_all_eligible(self):
        decision = RubyCartFulfillmentPolicy.evaluate(
            [
                CartLine(product("BREAD", "ambient", cool_eligible=True)),
                CartLine(product("CARAMEL", "ambient", cool_eligible=True)),
            ]
        )
        self.assertEqual(decision.default_yamato_method, "yamato_ambient")
        self.assertIn("yamato_ambient", decision.allowed_methods)
        self.assertIn("yamato_chilled", decision.allowed_methods)
        self.assertTrue(decision.chilled_upgrade_available)
        self.assertFalse(decision.yamato_time_window_required)
        self.assertTrue(decision.yamato_no_preference_allowed)

    def test_chilled_cake_makes_compatible_ambient_items_chilled(self):
        decision = RubyCartFulfillmentPolicy.evaluate(
            [
                CartLine(product("CAKE", "chilled", is_cake=True, ruby_car_allowed=True)),
                CartLine(product("BREAD", "ambient", cool_eligible=True, ruby_car_allowed=True)),
            ]
        )
        self.assertEqual(decision.default_yamato_method, "yamato_chilled")
        self.assertIn("yamato_chilled", decision.allowed_methods)
        self.assertIn("ruby_car", decision.allowed_methods)
        self.assertTrue(decision.yamato_time_window_required)
        self.assertFalse(decision.yamato_no_preference_allowed)
        self.assertFalse(decision.requires_split_or_alternate)

    def test_chilled_cake_plus_non_cool_eligible_ambient_item_fails_to_single_yamato_parcel(self):
        decision = RubyCartFulfillmentPolicy.evaluate(
            [
                CartLine(product("CAKE", "chilled", is_cake=True)),
                CartLine(product("AMBIENT", "ambient", cool_eligible=False)),
            ]
        )
        self.assertIsNone(decision.default_yamato_method)
        self.assertTrue(decision.requires_manual_review)
        self.assertTrue(decision.requires_split_or_alternate)
        self.assertIn("ambient_item_not_chilled_compatible", decision.reasons)

    def test_frozen_and_nonfrozen_mix_requires_split_or_alternate(self):
        decision = RubyCartFulfillmentPolicy.evaluate(
            [
                CartLine(product("FROZEN", "frozen")),
                CartLine(product("BREAD", "ambient", cool_eligible=True)),
            ]
        )
        self.assertIsNone(decision.default_yamato_method)
        self.assertTrue(decision.requires_split_or_alternate)
        self.assertIn("mixed_frozen_nonfrozen_requires_split_or_alternate", decision.reasons)

    def test_all_frozen_cart_can_use_yamato_frozen(self):
        decision = RubyCartFulfillmentPolicy.evaluate(
            [CartLine(product("F1", "frozen")), CartLine(product("F2", "frozen"))]
        )
        self.assertEqual(decision.default_yamato_method, "yamato_frozen")
        self.assertFalse(decision.chilled_upgrade_available)

    def test_cool_size_over_120_fails_closed(self):
        decision = RubyCartFulfillmentPolicy.evaluate(
            [CartLine(product("CAKE", "chilled", is_cake=True))],
            packing=CartPackingFacts(yamato_size=140, weight_kg=10),
        )
        self.assertIsNone(decision.default_yamato_method)
        self.assertTrue(decision.requires_manual_review)
        self.assertTrue(decision.requires_split_or_alternate)
        self.assertIn("yamato_cool_size_exceeds_120", decision.reasons)

    def test_cool_weight_over_15kg_fails_closed(self):
        decision = RubyCartFulfillmentPolicy.evaluate(
            [CartLine(product("CAKE", "chilled", is_cake=True))],
            packing=CartPackingFacts(yamato_size=120, weight_kg=15.1),
        )
        self.assertTrue(decision.requires_split_or_alternate)
        self.assertIn("yamato_cool_weight_exceeds_15kg", decision.reasons)

    def test_sensitive_cake_can_be_pickup_and_car_only(self):
        decision = RubyCartFulfillmentPolicy.evaluate(
            [
                CartLine(
                    product(
                        "TIER3",
                        "chilled",
                        is_cake=True,
                        yamato_allowed=False,
                        ruby_car_allowed=True,
                    )
                )
            ]
        )
        self.assertEqual(decision.allowed_methods, ("shop_pickup", "ruby_car"))
        self.assertIsNone(decision.default_yamato_method)
        self.assertIn("one_or_more_products_disallow_yamato", decision.reasons)

    def test_empty_cart_rejected(self):
        with self.assertRaises(FulfillmentPolicyError):
            RubyCartFulfillmentPolicy.evaluate([])


class RubyCarDeliveryPolicyTests(unittest.TestCase):
    def route(
        self,
        km: float,
        *,
        minutes: int = 30,
        prefecture: str = "Chiba",
        tolls_expected: bool = False,
        toll_yen: int | None = None,
        parking: bool = False,
    ) -> RubyCarRouteFacts:
        return RubyCarRouteFacts(
            destination_prefecture=prefecture,
            distance_meters=round(km * 1000),
            duration_seconds=minutes * 60,
            tolls_expected=tolls_expected,
            toll_yen=toll_yen,
            exceptional_parking_expected=parking,
        )

    def test_minimum_fee_through_10km(self):
        quote = RubyCarDeliveryPolicy.quote(self.route(8))
        self.assertEqual(quote.status, "provisional_quote")
        self.assertEqual(quote.base_delivery_fee_yen, 2500)
        self.assertEqual(quote.provisional_total_yen, 2500)
        self.assertFalse(quote.payment_authorized)

    def test_15km_example_is_3250(self):
        quote = RubyCarDeliveryPolicy.quote(self.route(15))
        self.assertEqual(quote.base_delivery_fee_yen, 3250)

    def test_30km_example_is_5500(self):
        quote = RubyCarDeliveryPolicy.quote(self.route(30))
        self.assertEqual(quote.base_delivery_fee_yen, 5500)

    def test_40km_example_is_7500(self):
        quote = RubyCarDeliveryPolicy.quote(self.route(40))
        self.assertEqual(quote.base_delivery_fee_yen, 7500)

    def test_50km_example_is_9500(self):
        quote = RubyCarDeliveryPolicy.quote(self.route(50, minutes=60))
        self.assertEqual(quote.base_delivery_fee_yen, 9500)
        self.assertFalse(quote.requires_manual_review)

    def test_fractional_distance_rounds_up_to_started_km(self):
        quote = RubyCarDeliveryPolicy.quote(self.route(10.1))
        self.assertEqual(quote.billable_one_way_km, 11)
        self.assertEqual(quote.base_delivery_fee_yen, 2650)

    def test_over_50_to_80km_is_manual_quote(self):
        quote = RubyCarDeliveryPolicy.quote(self.route(60, minutes=70))
        self.assertEqual(quote.status, "manual_review")
        self.assertIsNone(quote.base_delivery_fee_yen)
        self.assertTrue(quote.requires_manual_review)
        self.assertIn("distance_over_50km_requires_manual_quote", quote.reasons)

    def test_over_80km_is_unavailable(self):
        quote = RubyCarDeliveryPolicy.quote(self.route(81))
        self.assertEqual(quote.status, "unavailable")
        self.assertIsNone(quote.provisional_total_yen)
        self.assertIn("distance_exceeds_80km", quote.reasons)

    def test_over_75_minutes_requires_manual_review_even_within_50km(self):
        quote = RubyCarDeliveryPolicy.quote(self.route(20, minutes=76))
        self.assertEqual(quote.status, "manual_review")
        self.assertEqual(quote.base_delivery_fee_yen, 4000)
        self.assertIn("one_way_duration_over_75_minutes", quote.reasons)

    def test_known_toll_is_added_to_provisional_total(self):
        quote = RubyCarDeliveryPolicy.quote(
            self.route(20, tolls_expected=True, toll_yen=1320)
        )
        self.assertEqual(quote.base_delivery_fee_yen, 4000)
        self.assertEqual(quote.provisional_total_yen, 5320)

    def test_unknown_toll_price_requires_manual_review(self):
        quote = RubyCarDeliveryPolicy.quote(self.route(20, tolls_expected=True))
        self.assertEqual(quote.status, "manual_review")
        self.assertIsNone(quote.provisional_total_yen)
        self.assertIn("toll_price_unavailable", quote.reasons)

    def test_exceptional_parking_requires_manual_review(self):
        quote = RubyCarDeliveryPolicy.quote(self.route(10, parking=True))
        self.assertEqual(quote.status, "manual_review")
        self.assertIn("exceptional_parking_requires_manual_review", quote.reasons)

    def test_outside_four_prefectures_is_unavailable(self):
        quote = RubyCarDeliveryPolicy.quote(self.route(20, prefecture="Ibaraki"))
        self.assertEqual(quote.status, "unavailable")
        self.assertIn("destination_prefecture_outside_service_area", quote.reasons)

    def test_origin_is_fixed_to_ruby_shop(self):
        with self.assertRaisesRegex(FulfillmentPolicyError, "origin"):
            RubyCarRouteFacts(
                destination_prefecture="Chiba",
                distance_meters=1000,
                duration_seconds=600,
                origin_ref="somewhere_else",
            )


if __name__ == "__main__":
    unittest.main()
