import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"
TOOL = ROOT / "tools_working_catalog_category_candidates.py"


class WorkingCatalogCategoryCandidateCliTests(unittest.TestCase):
    def test_current_fixture_renders_non_authorizing_candidates(self):
        result = subprocess.run(
            [sys.executable, str(TOOL), "--input", str(FIXTURE)],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ready_for_category_mapping_approval"])
        self.assertFalse(payload["network_call_performed"])
        self.assertFalse(payload["mutation_authorized"])
        self.assertFalse(payload["production_publish_authorized"])
        self.assertEqual(
            {candidate["source_label"] for candidate in payload["candidates"]},
            {"Bread", "Other"},
        )

    def test_invalid_json_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(TOOL), "--input", str(path)],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("PHIL_AI_OS_WORKING_CATALOG_CATEGORY_CANDIDATES_FAILED", result.stderr)

    def test_output_file_keeps_authority_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "categories.json"
            subprocess.run(
                [sys.executable, str(TOOL), "--input", str(FIXTURE), "--output", str(output)],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertFalse(payload["mutation_authorized"])
        self.assertFalse(payload["production_publish_authorized"])


if __name__ == "__main__":
    unittest.main()
