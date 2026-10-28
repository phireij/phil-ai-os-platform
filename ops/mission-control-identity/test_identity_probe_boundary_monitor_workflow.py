"""Static checks for the no-authority identity-probe monitor."""

from __future__ import annotations

import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "mission-control-conversation-storage-monitor.yml"


class IdentityProbeBoundaryMonitorWorkflowTests(unittest.TestCase):
    def test_monitors_only_the_replacement_no_authority_probe(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("phil-ai-os-mission-control-google-identity-probe", content)
        self.assertIn("probe_ready;authority_effect=none", content)
        self.assertIn("session_status", content)
        self.assertIn("test \"$session_status\" = 404", content)
        self.assertIn("{{range .Mounts}}{{if .RW}}{{.Destination}}{{end}}{{end}}", content)
        self.assertNotIn("conversation_authority=enabled", content)
        self.assertNotIn("google-ceo-session", content)


if __name__ == "__main__":
    unittest.main()
