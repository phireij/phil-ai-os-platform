import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools_working_catalog_draft_plan.py"
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"


class WorkingCatalogDraftPlanCliTests(unittest.TestCase):
    def test_current_fixture_renders_confirmed_draft_plan(self):
        completed = subprocess.run(
            [sys.executable, str(TOOL), "--input", str(FIXTURE)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["network_call_performed"])
        self.assertFalse(payload["mutation_authorized"])
        self.assertFalse(payload["production_publish_authorized"])
        by_key = {item["key"]: item for item in payload["products"]}
        self.assertEqual(by_key["RCD-BRD-ENS-1"]["price_jpy"], 300)
        self.assertEqual(by_key["RCD-BAR-FMB"]["price_jpy"], 250)
        moist = by_key["RCD-MCH-RD"]
        self.assertEqual(moist["status"], "draft")
        self.assertEqual(moist["catalog_visibility"], "hidden")
        variants = {item["sku"]: item for item in moist["variations"]}
        self.assertEqual(variants["RCD-MCH-RD-15"]["price_jpy"], 3500)
        self.assertEqual(variants["RCD-MCH-RD-21"]["price_jpy"], 5500)
        self.assertIn("japanese_name", moist["unresolved_fields"])
        self.assertIn("network_call=false", completed.stderr)

    def test_output_file_keeps_authority_false(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "draft-plan.json"
            completed = subprocess.run(
                [sys.executable, str(TOOL), "--input", str(FIXTURE), "--output", str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(payload["mutation_authorized"])
            self.assertFalse(payload["production_publish_authorized"])

    def test_invalid_json_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "bad.json"
            bad.write_text("{", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(TOOL), "--input", str(bad)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("PHIL_AI_OS_WORKING_CATALOG_DRAFT_PLAN_FAILED", completed.stderr)


if __name__ == "__main__":
    unittest.main()
