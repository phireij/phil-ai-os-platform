from pathlib import Path
import unittest


class HostingerConversationStoragePreflightWorkflowChecks(unittest.TestCase):
    def test_workflow_only_uses_existing_session_and_streams_read_only_script(self) -> None:
        workflow = (
            Path(__file__).parents[2]
            / ".github"
            / "workflows"
            / "mission-control-conversation-storage-preflight.yml"
        ).read_text(encoding="utf-8")
        for marker in (
            "workflow_dispatch:",
            "VPS_SSH_KEY",
            "docker inspect",
            "SECRET_VOLUME",
            "preflight-conversation-storage.sh",
            "authority_effect=none",
            "existing_workloads_unchanged=true",
            "session_missing",
            "session_not_running",
            "session_image_digest_mismatch",
            "session_secret_volume_unavailable",
        ):
            self.assertIn(marker, workflow)
        for prohibited in (
            "docker volume create",
            "docker volume rm",
            "docker pull",
            "docker login",
            "docker start",
            "docker rm",
            "activate-google-ceo-session.sh",
        ):
            self.assertNotIn(prohibited, workflow)


if __name__ == "__main__":
    unittest.main()
