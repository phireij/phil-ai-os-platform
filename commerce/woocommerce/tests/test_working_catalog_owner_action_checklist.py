import json
from pathlib import Path
import unittest

from phil_ai_os_woocommerce.working_catalog_owner_action_checklist import (
    render_working_catalog_owner_action_checklist,
)
from phil_ai_os_woocommerce.working_catalog_owner_action_packet import (
    build_working_catalog_owner_action_packet,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"


class WorkingCatalogOwnerActionChecklistTests(unittest.TestCase):
    def load(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_current_fixture_renders_every_source_action_once(self):
        payload = self.load()
        packet = build_working_catalog_owner_action_packet(payload)
        rendered = render_working_catalog_owner_action_checklist(payload)

        self.assertIn("# Working Catalog Owner Checklist", rendered)
        self.assertIn("Production readiness: **BLOCKED**", rendered)
        self.assertIn(f"Remaining actions: **{len(packet.actions)}**", rendered)
        for action in packet.actions:
            self.assertEqual(rendered.count(f"`{action.action_key}`"), 1)
            self.assertIn(action.requirement, rendered)

    def test_variable_parent_context_uses_source_backed_worksheet_structure(self):
        rendered = render_working_catalog_owner_action_checklist(self.load())

        self.assertIn("### RCD-MCH-RD", rendered)
        self.assertIn("Owner worksheet row: `variable_parent` / `RCD-MCH-RD`", rendered)
        self.assertIn(
            "Related variation SKUs (source-backed): `RCD-MCH-RD-15`, `RCD-MCH-RD-21`",
            rendered,
        )
        self.assertIn(
            "Product-level owner fields belong on the `variable_parent` row",
            rendered,
        )

    def test_simple_product_context_keeps_exact_owner_worksheet_identity(self):
        rendered = render_working_catalog_owner_action_checklist(self.load())

        self.assertIn("### RCD-BAR-FMB", rendered)
        self.assertIn("Owner worksheet row: `simple_product` / `RCD-BAR-FMB`", rendered)
        self.assertIn("### RCD-BRD-ENS-1", rendered)
        self.assertIn("Owner worksheet row: `simple_product` / `RCD-BRD-ENS-1`", rendered)

    def test_checklist_is_explicitly_non_authorizing_and_does_not_supply_decisions(self):
        rendered = render_working_catalog_owner_action_checklist(self.load())

        self.assertIn("Network calls performed: **No**", rendered)
        self.assertIn("WooCommerce mutation authorized: **No**", rendered)
        self.assertIn("Production publication authorized: **No**", rendered)
        self.assertIn("does not supply decisions or change catalog facts", rendered)
        self.assertIn("does not itself approve Initial Launch Catalog V1", rendered)
        self.assertNotIn("decision_value", rendered)

    def test_rendering_is_deterministic(self):
        payload = self.load()
        self.assertEqual(
            render_working_catalog_owner_action_checklist(payload),
            render_working_catalog_owner_action_checklist(payload),
        )


if __name__ == "__main__":
    unittest.main()
