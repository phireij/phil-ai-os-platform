import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "working-catalog-subset-2026-09-11.json"
TOOL = ROOT / "tools_working_catalog_media_evidence.py"


class WorkingCatalogMediaEvidenceCliTests(unittest.TestCase):
    def test_current_fixture_renders_non_authorizing_media_evidence(self):
        result = subprocess.run(
            [sys.executable, str(TOOL), "--input", str(FIXTURE)],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ready_for_media_ingestion_review"])
        self.assertFalse(payload["network_call_performed"])
        self.assertFalse(payload["mutation_authorized"])
        self.assertFalse(payload["production_publish_authorized"])
        by_key = {item["product_key"]: item for item in payload["items"]}
        self.assertEqual(by_key["RCD-BAR-FMB"]["source_state"], "attached_in_owner_source")
        self.assertIsNone(by_key["RCD-BAR-FMB"]["verified_media_reference"])

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
        self.assertIn("PHIL_AI_OS_WORKING_CATALOG_MEDIA_EVIDENCE_FAILED", result.stderr)

    def test_output_file_keeps_authority_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "media.json"
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
