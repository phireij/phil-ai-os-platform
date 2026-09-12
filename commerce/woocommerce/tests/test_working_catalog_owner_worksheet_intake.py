import csv
import io
import json
from pathlib import Path
import unittest

from phil_ai_os_woocommerce.working_catalog_owner_worksheet import (
    build_working_catalog_owner_worksheet,
)
from phil_ai_os_woocommerce.working_catalog_owner_worksheet_intake import (
    parse_owner_worksheet_csv,
    review_owner_worksheet_intake,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"


def render_csv(worksheet) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=worksheet.columns, extrasaction="raise")
    writer.writeheader()
    writer.writerows(worksheet.rows)
    return buffer.getvalue()


class WorkingCatalogOwnerWorksheetIntakeTests(unittest.TestCase):
    def load(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def rows(self):
        worksheet = build_working_catalog_owner_worksheet(self.load())
        return [dict(row) for row in worksheet.rows]

    def test_untouched_generated_worksheet_round_trips_without_changes(self):
        payload = self.load()
        worksheet = build_working_catalog_owner_worksheet(payload)
        rows = parse_owner_worksheet_csv("\ufeff" + render_csv(worksheet))
        review = review_owner_worksheet_intake(payload, rows)

        self.assertTrue(review.structurally_valid)
        self.assertTrue(review.ready_for_owner_fact_review)
        self.assertEqual(5, review.row_count)
        self.assertEqual(5, review.unchanged_row_count)
        self.assertEqual((), review.proposed_changes)
        self.assertEqual((), review.blockers)

    def test_owner_fields_become_non_authorizing_proposals(self):
        payload = self.load()
        rows = self.rows()
        moist = next(row for row in rows if row["sku"] == "RCD-MCH-RD")
        moist["japanese_name"] = "オーナー確認用名称"
        moist["japanese_description"] = "オーナー確認用説明"
        moist["approved_category_key"] = "cake"
        moist["primary_media_ref"] = "owner-media-ref-001"
        moist["final_temperature_mode"] = "frozen"
        moist["shipping_class"] = "cool-80"

        review = review_owner_worksheet_intake(payload, rows)
        self.assertTrue(review.structurally_valid)
        self.assertTrue(review.ready_for_owner_fact_review)
        changes = {(change.sku, change.field): change for change in review.proposed_changes}
        self.assertEqual("owner_input", changes[("RCD-MCH-RD", "japanese_name")].classification)
        self.assertFalse(changes[("RCD-MCH-RD", "japanese_name")].evidence_required)
        self.assertEqual("cool-80", changes[("RCD-MCH-RD", "shipping_class")].proposed_value)
        self.assertFalse(review.network_call_performed)
        self.assertFalse(review.mutation_authorized)
        self.assertFalse(review.production_publish_authorized)
        self.assertFalse(review.automatic_apply_authorized)

    def test_source_backed_change_is_preserved_but_requires_fresh_evidence(self):
        payload = self.load()
        rows = self.rows()
        bar = next(row for row in rows if row["sku"] == "RCD-BAR-FMB")
        bar["price_jpy"] = "275"

        review = review_owner_worksheet_intake(payload, rows)
        self.assertTrue(review.structurally_valid)
        self.assertEqual(1, len(review.proposed_changes))
        change = review.proposed_changes[0]
        self.assertEqual("price_jpy", change.field)
        self.assertEqual("250", change.previous_value)
        self.assertEqual("275", change.proposed_value)
        self.assertEqual("source_backed_change_requires_evidence", change.classification)
        self.assertTrue(change.evidence_required)

    def test_parent_variation_identity_tampering_fails_closed(self):
        payload = self.load()
        rows = self.rows()
        variation = next(row for row in rows if row["sku"] == "RCD-MCH-RD-15")
        variation["parent_sku"] = "RCD-OTHER"

        review = review_owner_worksheet_intake(payload, rows)
        self.assertFalse(review.structurally_valid)
        self.assertFalse(review.ready_for_owner_fact_review)
        self.assertTrue(any("structural field parent_sku" in blocker for blocker in review.blockers))

    def test_missing_or_extra_sku_fails_closed(self):
        payload = self.load()
        rows = self.rows()
        rows = [row for row in rows if row["sku"] != "RCD-BRD-ENS-1"]
        extra = dict(rows[0])
        extra["sku"] = "RCD-FAKE-ROW"
        rows.append(extra)

        review = review_owner_worksheet_intake(payload, rows)
        self.assertFalse(review.structurally_valid)
        self.assertTrue(any("missing expected SKU: RCD-BRD-ENS-1" in blocker for blocker in review.blockers))
        self.assertTrue(any("unexpected SKU: RCD-FAKE-ROW" in blocker for blocker in review.blockers))

    def test_variation_product_level_owner_input_is_rejected(self):
        payload = self.load()
        rows = self.rows()
        variation = next(row for row in rows if row["sku"] == "RCD-MCH-RD-21")
        variation["japanese_name"] = "誤入力"

        review = review_owner_worksheet_intake(payload, rows)
        self.assertFalse(review.structurally_valid)
        self.assertTrue(any("variation row cannot carry product-level owner field japanese_name" in blocker for blocker in review.blockers))

    def test_invalid_owner_enums_fail_closed(self):
        payload = self.load()
        rows = self.rows()
        ensaymada = next(row for row in rows if row["sku"] == "RCD-BRD-ENS-1")
        ensaymada["final_temperature_mode"] = "hot"
        ensaymada["shipping_class"] = "box-999"

        review = review_owner_worksheet_intake(payload, rows)
        self.assertFalse(review.structurally_valid)
        self.assertTrue(any("unsupported final_temperature_mode" in blocker for blocker in review.blockers))
        self.assertTrue(any("unsupported shipping_class" in blocker for blocker in review.blockers))

    def test_csv_parser_rejects_contract_column_drift(self):
        worksheet = build_working_catalog_owner_worksheet(self.load())
        rendered = render_csv(worksheet).replace("record_type,", "wrong_column,", 1)
        with self.assertRaisesRegex(ValueError, "columns do not match"):
            parse_owner_worksheet_csv(rendered)


if __name__ == "__main__":
    unittest.main()
