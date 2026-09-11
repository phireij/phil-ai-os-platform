import unittest

from phil_ai_os_woocommerce.ambient_packaging import (
    AMBIENT_PACKAGE_100,
    AMBIENT_PACKAGE_60,
    AMBIENT_PACKAGE_80,
    AMBIENT_PACKAGE_COMPACT,
    AmbientPackageLine,
    AmbientPackagingError,
    AmbientPackingEvidence,
    AmbientShippingPackagingPolicy,
)


class AmbientShippingPackagingPolicyTests(unittest.TestCase):
    def test_single_verified_compact_sku_uses_takkyubin_compact(self):
        decision = AmbientShippingPackagingPolicy.select(
            [
                AmbientPackageLine(
                    sku="BROWNIE-BOX",
                    minimum_package_class=AMBIENT_PACKAGE_COMPACT,
                )
            ]
        )
        self.assertEqual(decision.package_class, AMBIENT_PACKAGE_COMPACT)
        self.assertEqual(decision.yamato_service, "takkyubin_compact")
        self.assertFalse(decision.requires_manual_review)
        self.assertFalse(decision.production_mutation_authorized)

    def test_multiple_compact_units_fallback_to_size_60_without_packing_confirmation(self):
        decision = AmbientShippingPackagingPolicy.select(
            [
                AmbientPackageLine(
                    sku="CARAMEL-BAR-BOX",
                    quantity=2,
                    minimum_package_class=AMBIENT_PACKAGE_COMPACT,
                )
            ]
        )
        self.assertEqual(decision.package_class, AMBIENT_PACKAGE_60)
        self.assertEqual(decision.yamato_service, "takkyubin")
        self.assertIn(
            "compact_multi_unit_or_mixed_fit_unconfirmed_fallback_60",
            decision.reasons,
        )

    def test_multiple_compact_units_can_use_compact_when_fit_is_confirmed(self):
        decision = AmbientShippingPackagingPolicy.select(
            [
                AmbientPackageLine(
                    sku="BROWNIE-BOX",
                    quantity=2,
                    minimum_package_class=AMBIENT_PACKAGE_COMPACT,
                )
            ],
            packing=AmbientPackingEvidence(AMBIENT_PACKAGE_COMPACT),
        )
        self.assertEqual(decision.package_class, AMBIENT_PACKAGE_COMPACT)
        self.assertEqual(decision.yamato_service, "takkyubin_compact")
        self.assertIn("compact_multi_unit_or_mixed_fit_confirmed", decision.reasons)

    def test_mixed_compact_and_size_60_cart_uses_size_60(self):
        decision = AmbientShippingPackagingPolicy.select(
            [
                AmbientPackageLine(
                    sku="BROWNIE-BOX",
                    minimum_package_class=AMBIENT_PACKAGE_COMPACT,
                ),
                AmbientPackageLine(
                    sku="BANANA-CAKE",
                    minimum_package_class=AMBIENT_PACKAGE_60,
                ),
            ]
        )
        self.assertEqual(decision.package_class, AMBIENT_PACKAGE_60)
        self.assertEqual(decision.yamato_service, "takkyubin")

    def test_catalog_size_80_requirement_is_never_downgraded(self):
        decision = AmbientShippingPackagingPolicy.select(
            [AmbientPackageLine("LARGE-GIFT", minimum_package_class=AMBIENT_PACKAGE_80)]
        )
        self.assertEqual(decision.package_class, AMBIENT_PACKAGE_80)

    def test_packing_evidence_can_upgrade_package_class(self):
        decision = AmbientShippingPackagingPolicy.select(
            [AmbientPackageLine("GIFT", minimum_package_class=AMBIENT_PACKAGE_60)],
            packing=AmbientPackingEvidence(AMBIENT_PACKAGE_100),
        )
        self.assertEqual(decision.package_class, AMBIENT_PACKAGE_100)
        self.assertIn("packing_evidence_upgraded_package_class", decision.reasons)

    def test_packing_evidence_cannot_downgrade_below_catalog_minimum(self):
        decision = AmbientShippingPackagingPolicy.select(
            [AmbientPackageLine("GIFT", minimum_package_class=AMBIENT_PACKAGE_80)],
            packing=AmbientPackingEvidence(AMBIENT_PACKAGE_60),
        )
        self.assertIsNone(decision.package_class)
        self.assertIsNone(decision.yamato_service)
        self.assertTrue(decision.requires_manual_review)
        self.assertIn("confirmed_package_below_catalog_minimum", decision.reasons)

    def test_empty_cart_is_rejected(self):
        with self.assertRaises(AmbientPackagingError):
            AmbientShippingPackagingPolicy.select([])

    def test_invalid_package_class_is_rejected(self):
        with self.assertRaises(AmbientPackagingError):
            AmbientPackageLine("BAD", minimum_package_class="ambient_50")


if __name__ == "__main__":
    unittest.main()
