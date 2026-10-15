from pathlib import Path
import unittest


class ConversationKeyBootstrapChecks(unittest.TestCase):
    def test_bootstrap_generates_once_and_keeps_storage_inactive(self) -> None:
        script = (Path(__file__).parent / "bootstrap-conversation-key.sh").read_text(encoding="utf-8")
        for marker in (
            "--network none",
            "--read-only",
            "--cap-drop ALL",
            "--cap-add CHOWN",
            "--cap-add DAC_OVERRIDE",
            "conversation_key_bootstrap_completed=true",
            "recovery_package_pending_offline_retrieval=true",
            "storage_initialized=false",
            "conversation-key-recovery.v1.json",
            "recovery_package_already_exists",
            "recovery_package_verification_failed",
            "recovery_package_repaired=",
            "os.O_EXCL",
            "os.chmod(key_path, 0o400)\n        os.chown(key_path, 10003, 10003)",
            "os.chown(key_path, 10003, 10003)",
        ):
            self.assertIn(marker, script)
        for prohibited in (
            "docker start",
            "--privileged",
            "docker volume create",
            "docker volume rm",
            "MISSION_CONTROL_CONVERSATION_ENABLED=true",
            "print(master_key",
            "print(passphrase",
        ):
            self.assertNotIn(prohibited, script)

    def test_workflow_is_manual_and_uses_secret_stdin_only(self) -> None:
        workflow = (
            Path(__file__).parents[2]
            / ".github"
            / "workflows"
            / "mission-control-conversation-key-bootstrap.yml"
        ).read_text(encoding="utf-8")
        for marker in (
            "workflow_dispatch:",
            "MISSION_CONTROL_CONVERSATION_RECOVERY_PASSPHRASE",
            "printf '%s\\n' \"$RECOVERY_PASSPHRASE\" | ssh",
            "recovery_package_pending_offline_retrieval=true",
            "storage_initialized=false",
        ):
            self.assertIn(marker, workflow)
        for prohibited in (
            "actions/upload-artifact",
            "docker volume create",
            "docker volume rm",
            "docker start",
            "docker pull",
            "echo \"$RECOVERY_PASSPHRASE\"",
        ):
            self.assertNotIn(prohibited, workflow)


if __name__ == "__main__":
    unittest.main()
