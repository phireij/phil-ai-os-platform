from pathlib import Path
import unittest


class ConversationRecoveryPreflightChecks(unittest.TestCase):
    def test_preflight_is_networkless_read_only_and_does_not_exercise_recovery(self) -> None:
        script = (Path(__file__).parent / "preflight-conversation-recovery.sh").read_text(encoding="utf-8")
        for marker in (
            "--network none",
            "--read-only",
            "--cap-drop ALL",
            "--user 10003:10003",
            "conversations.enc",
            "deletion-ledger.enc",
            "conversation_recovery_preflight=green",
            "recovery_exercise=false",
            "state_content_exposed=false",
            "lstat()",
            "MAGIC",
        ):
            self.assertIn(marker, script)
        for prohibited in (
            "conversation_recovery.py backup",
            "conversation_recovery.py restore",
            "docker start",
            "docker stop",
            "docker rm",
            "docker volume create",
            "docker volume rm",
            "docker pull",
            "--privileged",
        ):
            self.assertNotIn(prohibited, script)

    def test_workflow_is_manual_and_preserves_existing_session(self) -> None:
        workflow = (
            Path(__file__).parents[2]
            / ".github"
            / "workflows"
            / "mission-control-conversation-recovery-preflight.yml"
        ).read_text(encoding="utf-8")
        for marker in (
            "workflow_dispatch:",
            "mission-control-conversation-recovery-preflight",
            "preflight-conversation-recovery.sh",
            "recovery_exercise=false",
            "existing_workloads_unchanged=true",
            "session_state_volume_unavailable",
            "phil-ai-os-mission-control-conversation-backup-v1",
        ):
            self.assertIn(marker, workflow)
        for prohibited in (
            "docker start",
            "docker stop",
            "docker rm",
            "docker volume create",
            "docker volume rm",
            "docker pull",
            "actions/upload-artifact",
        ):
            self.assertNotIn(prohibited, workflow)


if __name__ == "__main__":
    unittest.main()
