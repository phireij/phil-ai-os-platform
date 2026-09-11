import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools_working_catalog_gap_report.py"
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"


class WorkingCatalogGapReportCliTests(unittest.TestCase):
    def test_current_fixture_renders_non_authorizing_gap_report(self):
        completed = subprocess.run(
            [sys.executable, str(TOOL), "--input", str(FIXTURE)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["production_ready"])
        self.assertFalse(payload["network_call_performed"])
        self.assertFalse(payload["mutation_authorized"])
        self.assertFalse(payload["production_publish_authorized"])
        by_key = {item["key"]: item["missing"] for item in payload["product_gaps"]}
        self.assertNotIn("JPY price", by_key["RCD-BRD-ENS-1"])
        self.assertIn("Japanese product name", by_key["RCD-BRD-ENS-1"])
        self.assertIn("network_call=false", completed.stderr)

    def test_output_file_is_supported_without_changing_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "gap-report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--input",
                    str(FIXTURE),
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(payload["production_ready"])
            self.assertFalse(payload["mutation_authorized"])

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
            self.assertIn("PHIL_AI_OS_WORKING_CATALOG_GAP_REPORT_FAILED", completed.stderr)


if __name__ == "__main__":
    unittest.main()
