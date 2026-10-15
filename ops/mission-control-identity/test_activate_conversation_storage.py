from pathlib import Path
import unittest


class ConversationStorageActivationChecks(unittest.TestCase):
    def test_activation_is_guarded_and_rollback_capable(self) -> None:
        script = (Path(__file__).parent / "activate-conversation-storage.sh").read_text(encoding="utf-8")
        for marker in (
            "--network none",
            "--read-only",
            "--cap-drop ALL",
            "--cap-add CHOWN",
            "no-new-privileges:true",
            "conversation_storage_activation_phase=initial_container_guard",
            "conversation_volume_already_exists",
            "MISSION_CONTROL_CONVERSATION_KEY_FILE=/run/secrets/conversation_key",
            "STATE_VOLUME=phil-ai-os-mission-control-conversation-state-v1",
            "BACKUP_VOLUME=phil-ai-os-mission-control-conversation-backup-v1",
            "MISSION_CONTROL_CONVERSATION_ENABLED=true",
            "conversation_storage_activated=true",
            "rollback_retained=true",
            "conversation_authority=enabled",
            "provider_authority=none",
            "task_authority=none",
        ):
            self.assertIn(marker, script)
        for prohibited in (
            "docker volume rm",
            "--privileged",
            "docker pull",
            "OPENAI_API_KEY",
            "MISSION_CONTROL_PROVIDER",
        ):
            self.assertNotIn(prohibited, script)

    def test_workflow_is_manual_and_checks_public_boundary(self) -> None:
        workflow = (
            Path(__file__).parents[2]
            / ".github"
            / "workflows"
            / "mission-control-conversation-storage-activate.yml"
        ).read_text(encoding="utf-8")
        for marker in (
            "workflow_dispatch:",
            "mission-control-conversation-storage-activate",
            "activate-conversation-storage.sh",
            "conversation_authority=enabled",
            "healthz",
            "auth/google/start",
            "storage_activation_workflow_completed=true",
        ):
            self.assertIn(marker, workflow)
        for prohibited in (
            "docker volume rm",
            "docker pull",
            "actions/upload-artifact",
            "OPENAI_API_KEY",
        ):
            self.assertNotIn(prohibited, workflow)


if __name__ == "__main__":
    unittest.main()
