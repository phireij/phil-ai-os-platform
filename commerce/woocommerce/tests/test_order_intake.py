import unittest

from phil_ai_os_woocommerce.order_intake import (
    AddonSkuDefinition,
    AddonSelection,
    CustomCakeQuote,
    CustomCakeRequest,
    DeliveryAlternative,
    DeliverySchedule,
    IcingPreference,
    OrderIntakeError,
    PrivateImageUploadRef,
    confirm_delivery,
    propose_delivery_alternatives,
)


class DeliveryScheduleTests(unittest.TestCase):
    def test_requested_date_is_not_payment_ready_until_confirmed(self):
        schedule = DeliverySchedule(
            requested_date="2026-09-20",
            requested_time_window_code="14-16",
            time_window_required=True,
        )
        self.assertEqual(schedule.state, "requested")
        self.assertFalse(schedule.delivery_confirmed)
        self.assertFalse(schedule.payment_request_allowed_by_delivery)

    def test_required_yamato_window_fails_closed_when_missing(self):
        with self.assertRaisesRegex(OrderIntakeError, "time window"):
            DeliverySchedule(requested_date="2026-09-20", time_window_required=True)

    def test_alternative_date_flow_requires_customer_acceptance(self):
        schedule = DeliverySchedule(
            requested_date="2026-09-20",
            requested_time_window_code="14-16",
            time_window_required=True,
        )
        proposed = propose_delivery_alternatives(
            schedule,
            [
                DeliveryAlternative("2026-09-19", "14-16"),
                DeliveryAlternative("2026-09-21", "16-18"),
            ],
        )
        self.assertEqual(proposed.state, "alternatives_proposed")
        self.assertFalse(proposed.payment_request_allowed_by_delivery)

        confirmed = confirm_delivery(
            proposed,
            accepted_date="2026-09-21",
            accepted_time_window_code="16-18",
        )
        self.assertEqual(confirmed.state, "confirmed")
        self.assertEqual(confirmed.confirmed_date, "2026-09-21")
        self.assertEqual(confirmed.confirmed_time_window_code, "16-18")
        self.assertTrue(confirmed.payment_request_allowed_by_delivery)

    def test_unproposed_date_cannot_be_confirmed(self):
        schedule = DeliverySchedule(requested_date="2026-09-20")
        with self.assertRaisesRegex(OrderIntakeError, "not requested or proposed"):
            confirm_delivery(
                schedule,
                accepted_date="2026-09-22",
                accepted_time_window_code=None,
            )

    def test_ambient_no_preference_can_confirm_without_window(self):
        schedule = DeliverySchedule(requested_date="2026-09-20", time_window_required=False)
        confirmed = confirm_delivery(
            schedule,
            accepted_date="2026-09-20",
            accepted_time_window_code=None,
        )
        self.assertTrue(confirmed.delivery_confirmed)


class CustomCakeIntakeTests(unittest.TestCase):
    def image(self) -> PrivateImageUploadRef:
        return PrivateImageUploadRef(
            storage_ref="orders/private/rq_123/image_01",
            media_type="image/jpeg",
            byte_size=123456,
        )

    def request(self) -> CustomCakeRequest:
        return CustomCakeRequest(
            request_id="rq_123",
            requested_delivery_date="2026-09-20",
            size_or_servings="18 cm / 8 servings",
            flavor="Chocolate",
            layers=2,
            theme_or_colors="Blue and gold",
            inscription="Happy Birthday",
            budget_yen=12000,
            reference_images=(self.image(),),
            photo_topper_requested=True,
        )

    def test_custom_cake_is_quote_required_and_topper_not_standalone(self):
        request = self.request()
        self.assertEqual(request.pricing_mode, "quote_required")
        self.assertFalse(request.standalone_topper_sale)
        self.assertEqual(len(request.reference_images), 1)

    def test_private_upload_rejects_public_url(self):
        with self.assertRaisesRegex(OrderIntakeError, "public URL"):
            PrivateImageUploadRef(
                storage_ref="https://example.com/public/photo.jpg",
                media_type="image/jpeg",
                byte_size=100,
            )

    def test_private_upload_rejects_unsupported_media(self):
        with self.assertRaisesRegex(OrderIntakeError, "media type"):
            PrivateImageUploadRef(
                storage_ref="orders/private/rq_123/file",
                media_type="application/pdf",
                byte_size=100,
            )

    def test_custom_request_limits_reference_images(self):
        images = tuple(
            PrivateImageUploadRef(
                storage_ref=f"orders/private/rq_123/image_{i}",
                media_type="image/jpeg",
                byte_size=100,
            )
            for i in range(9)
        )
        with self.assertRaisesRegex(OrderIntakeError, "at most 8"):
            CustomCakeRequest(
                request_id="rq_123",
                requested_delivery_date="2026-09-20",
                size_or_servings="8 servings",
                flavor="Chocolate",
                layers=1,
                reference_images=images,
            )

    def test_photo_and_edible_topper_definitions_cannot_be_standalone(self):
        for kind in ("photo_topper", "edible_topper"):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(OrderIntakeError, "standalone"):
                    AddonSkuDefinition(
                        sku=f"ADD-{kind}",
                        kind=kind,
                        unit_price_yen=500,
                        requires_cake_parent=True,
                        standalone_allowed=True,
                    )

    def test_hybrid_addon_selection_requires_cake_parent_sku(self):
        definition = AddonSkuDefinition(
            sku="ADD-CANDLE-01",
            kind="candle",
            unit_price_yen=200,
        )
        selection = AddonSelection(
            parent_cake_sku="CAKE-001",
            addon_sku=definition.sku,
            quantity=2,
        )
        self.assertEqual(selection.parent_cake_sku, "CAKE-001")
        self.assertEqual(selection.quantity, 2)

    def test_icing_defaults_to_white_without_activating_color_price(self):
        icing = IcingPreference(icing_requested=True)
        self.assertEqual(icing.colors, ("white",))
        self.assertEqual(icing.pricing_status, "pending_business_confirmation")
        self.assertIsNone(icing.price_delta_yen)

    def test_multiple_icing_colors_do_not_infer_unapproved_surcharge(self):
        icing = IcingPreference(icing_requested=True, colors=("white", "blue"))
        self.assertEqual(icing.colors, ("white", "blue"))
        self.assertIsNone(icing.price_delta_yen)

    def test_quote_can_change_while_draft_and_payment_remains_blocked(self):
        quote = CustomCakeQuote(
            request_id="rq_123",
            cake_price_yen=10000,
            addon_total_yen=500,
            delivery_fee_yen=2500,
            delivery_confirmed=False,
            status="draft",
        )
        self.assertEqual(quote.total_yen, 13000)
        self.assertFalse(quote.payment_request_allowed)

        revised = CustomCakeQuote(
            request_id="rq_123",
            cake_price_yen=12000,
            addon_total_yen=700,
            delivery_fee_yen=3250,
            delivery_confirmed=True,
            status="approved",
        )
        self.assertEqual(revised.total_yen, 15950)
        self.assertTrue(revised.payment_request_allowed)

    def test_quote_cannot_be_approved_before_delivery_confirmation(self):
        with self.assertRaisesRegex(OrderIntakeError, "delivery is confirmed"):
            CustomCakeQuote(
                request_id="rq_123",
                cake_price_yen=10000,
                addon_total_yen=0,
                delivery_fee_yen=2500,
                delivery_confirmed=False,
                status="approved",
            )


if __name__ == "__main__":
    unittest.main()
