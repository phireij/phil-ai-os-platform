"""Static checks for the no-content CEO-session boundary monitor."""

from __future__ import annotations

import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "mission-control-conversation-storage-monitor.yml"


class CioSessionBoundaryMonitorWorkflowTests(unittest.TestCase):
    def test_keeps_a_bounded_cadence_and_read_only_workflow_permissions(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("schedule:\n    - cron: '17,47 * * * *'", content)
        self.assertIn("permissions:\n  contents: read", content)
        self.assertNotIn("contents: write", content)
        self.assertNotIn("packages: write", content)

    def test_never_loads_application_or_client_secret_material(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("Check active CEO-session boundary without secret or content access", content)
        self.assertIn("VPS_SSH_KEY", content)
        self.assertNotIn("MISSION_CONTROL_GOOGLE_CLIENT_SECRET", content)
        self.assertNotIn("CLIENT_SECRET", content)
        self.assertNotIn("/auth/google/start", content)

    def test_remote_and_public_checks_remain_inspection_only(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("docker inspect", content)
        for command in (
            "docker run",
            "docker start",
            "docker stop",
            "docker restart",
            "docker rm",
            "docker rename",
            "docker volume",
        ):
            self.assertNotIn(command, content)
        self.assertNotIn("--data", content)
        self.assertNotRegex(content, r"curl[^\n]*(?:\s-d(?:\s|=)|\s--data(?:\s|=))")
        self.assertIn('test "$post_status" = 405', content)

    def test_monitors_only_the_active_session_boundary(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("phil-ai-os-mission-control-google-ceo-session", content)
        self.assertIn("session_ready;conversation_authority=enabled", content)
        self.assertIn("session_status", content)
        self.assertIn("test \"$session_status\" = 401", content)
        self.assertIn("{{range .Mounts}}{{if .RW}}{{.Destination}}{{end}}{{end}}", content)
        self.assertIn("/var/lib/mission-control", content)


if __name__ == "__main__":
    unittest.main()
