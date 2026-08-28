import unittest

from phil_ai_os_woocommerce import (
    CategoryHierarchyError,
    CategoryRecord,
    LocalizedText,
    MediaPlanError,
    MediaRecord,
    ProductRecord,
    build_product_media_plan,
    plan_category_hierarchy,
    plan_media_reconciliation,
    project_category_payload,
)


class PlanningTests(unittest.TestCase):
    def category(self, key, parent_key=None):
        return CategoryRecord(
            key=key,
            name=LocalizedText(en=key.title(), ja=f"{key}-ja"),
            slug=LocalizedText(en=key, ja=f"{key}-ja"),
            parent_key=parent_key,
        )

    def product(self, media_keys=()):
        return ProductRecord(
            sku="SKU-PLAN-1",
            name=LocalizedText(en="Cake", ja="ケーキ"),
            description=LocalizedText(en="Description", ja="説明"),
            slug=LocalizedText(en="cake-plan", ja="cake-plan-ja"),
            regular_price="500",
            currency="JPY",
            media_keys=tuple(media_keys),
        )

    def media(self, key, role, position, source_ref=None):
        return MediaRecord(
            key=key,
            source_ref=source_ref or f"fixture://{key}.jpg",
            alt=LocalizedText(en=f"{key} alt", ja=f"{key} 代替"),
            role=role,
            position=position,
        )

    def test_category_parent_precedes_child(self):
        plan = plan_category_hierarchy([
            self.category("cupcakes", "baked-goods"),
            self.category("baked-goods"),
        ])
        self.assertEqual([item.key for item in plan], ["baked-goods", "cupcakes"])
        self.assertEqual([item.depth for item in plan], [0, 1])

    def test_category_missing_parent_fails_closed(self):
        with self.assertRaises(CategoryHierarchyError):
            plan_category_hierarchy([self.category("cupcakes", "missing")])

    def test_category_cycle_fails_closed(self):
        with self.assertRaises(CategoryHierarchyError):
            plan_category_hierarchy([
                self.category("a", "b"),
                self.category("b", "a"),
            ])

    def test_category_duplicate_key_fails_closed(self):
        with self.assertRaises(CategoryHierarchyError):
            plan_category_hierarchy([self.category("a"), self.category("a")])

    def test_category_child_projection_requires_parent_remote_id(self):
        plan = plan_category_hierarchy([
            self.category("baked-goods"),
            self.category("cupcakes", "baked-goods"),
        ])
        child = next(item for item in plan if item.key == "cupcakes")
        with self.assertRaises(CategoryHierarchyError):
            project_category_payload(child)

    def test_category_child_projection_uses_parent_remote_id(self):
        plan = plan_category_hierarchy([
            self.category("baked-goods"),
            self.category("cupcakes", "baked-goods"),
        ])
        child = next(item for item in plan if item.key == "cupcakes")
        payload = project_category_payload(child, locale="ja", remote_ids={"baked-goods": 41})
        self.assertEqual(payload["parent"], 41)
        self.assertEqual(payload["name"], "cupcakes-ja")

    def test_media_primary_is_first_and_locale_is_projected(self):
        product = self.product(("gallery-1", "primary-1"))
        plan = build_product_media_plan(
            product,
            [self.media("gallery-1", "gallery", 1), self.media("primary-1", "primary", 0)],
            locale="ja",
        )
        self.assertEqual([item["key"] for item in plan], ["primary-1", "gallery-1"])
        self.assertEqual(plan[0]["alt"], "primary-1 代替")

    def test_media_missing_reference_fails_closed(self):
        with self.assertRaises(MediaPlanError):
            build_product_media_plan(self.product(("missing",)), [])

    def test_media_requires_exactly_one_primary(self):
        product = self.product(("gallery-1", "gallery-2"))
        with self.assertRaises(MediaPlanError):
            build_product_media_plan(
                product,
                [self.media("gallery-1", "gallery", 0), self.media("gallery-2", "gallery", 1)],
            )

    def test_media_duplicate_positions_fail_closed(self):
        product = self.product(("primary-1", "gallery-1"))
        with self.assertRaises(MediaPlanError):
            build_product_media_plan(
                product,
                [self.media("primary-1", "primary", 0), self.media("gallery-1", "gallery", 0)],
            )

    def desired_media_plan(self):
        product = self.product(("primary-1", "gallery-1"))
        return build_product_media_plan(
            product,
            [self.media("primary-1", "primary", 0), self.media("gallery-1", "gallery", 1)],
        )

    def test_media_reconciliation_noop(self):
        desired = self.desired_media_plan()
        diff = plan_media_reconciliation(desired, desired)
        self.assertEqual(diff.action, "noop")

    def test_media_reconciliation_detects_source_replacement(self):
        desired = self.desired_media_plan()
        observed = [dict(item) for item in desired]
        observed[1]["source_ref"] = "fixture://old-gallery.jpg"
        diff = plan_media_reconciliation(desired, observed)
        self.assertEqual(diff.action, "replace")
        self.assertEqual(diff.replacement_keys, ("gallery-1",))

    def test_media_reconciliation_detects_removal_and_addition(self):
        desired = self.desired_media_plan()
        observed = [dict(desired[0]), {
            "key": "old-gallery",
            "source_ref": "fixture://old-gallery.jpg",
            "alt": "old",
            "role": "gallery",
            "position": 1,
        }]
        diff = plan_media_reconciliation(desired, observed)
        self.assertEqual(diff.replacement_keys, ("gallery-1",))
        self.assertEqual(diff.removed_keys, ("old-gallery",))

    def test_media_reconciliation_detects_reorder(self):
        desired = self.desired_media_plan()
        observed = [dict(desired[1]), dict(desired[0])]
        diff = plan_media_reconciliation(desired, observed)
        self.assertTrue(diff.reordered)
        self.assertIn(diff.action, {"reorder", "metadata_and_reorder"})

    def test_media_reconciliation_detects_metadata_change(self):
        desired = self.desired_media_plan()
        observed = [dict(item) for item in desired]
        observed[1]["alt"] = "old alt"
        diff = plan_media_reconciliation(desired, observed)
        self.assertEqual(diff.action, "metadata")
        self.assertEqual(diff.metadata_update_keys, ("gallery-1",))

    def test_media_reconciliation_rejects_duplicate_observed_keys(self):
        desired = self.desired_media_plan()
        observed = [dict(desired[0]), dict(desired[0])]
        with self.assertRaises(MediaPlanError):
            plan_media_reconciliation(desired, observed)


if __name__ == "__main__":
    unittest.main()
