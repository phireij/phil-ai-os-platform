from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools_working_catalog_owner_action_checklist.py"
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"


class WorkingCatalogOwnerActionChecklistCliTests(unittest.TestCase):
    def test_current_fixture_renders_human_readable_non_authorizing_checklist(self):
        completed = subprocess.run(
            [sys.executable, str(TOOL), "--input", str(FIXTURE)],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("# Working Catalog Owner Checklist", completed.stdout)
        self.assertIn("Owner worksheet row: `variable_parent` / `RCD-MCH-RD`", completed.stdout)
        self.assertIn("WooCommerce mutation authorized: **No**", completed.stdout)
        self.assertIn("network_call=false", completed.stderr)
        self.assertIn("mutation_authorized=false", completed.stderr)
        self.assertIn("production_publish_authorized=false", completed.stderr)

    def test_output_file_keeps_guardrail_text(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "owner-checklist.md"
            completed = subprocess.run(
                [sys.executable, str(TOOL), "--input", str(FIXTURE), "--output", str(output)],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            rendered = output.read_text(encoding="utf-8")
            self.assertIn("Production publication authorized: **No**", rendered)
            self.assertIn("does not itself approve Initial Launch Catalog V1", rendered)
            self.assertEqual(completed.stdout, "")

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
            self.assertIn("PHIL_AI_OS_CATALOG_OWNER_ACTION_CHECKLIST_FAILED", completed.stderr)


if __name__ == "__main__":
    unittest.main()
