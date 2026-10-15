from pathlib import Path
import unittest


class RecoveryPackageRemovalChecks(unittest.TestCase):
    def test_removal_is_single_file_guarded_and_keeps_live_key(self) -> None:
        script = (Path(__file__).parent / "remove-conversation-recovery-package.sh").read_text(encoding="utf-8")
        for marker in (
            "conversation-key-recovery.v1.json",
            "conversation_key",
            "--network none",
            "--read-only",
            "--cap-drop ALL",
            "--cap-add DAC_OVERRIDE",
            "--cap-add FOWNER",
            "lstat()",
            "os.unlink(package)",
            "live_key_retained=true",
            "state_unchanged=true",
        ):
            self.assertIn(marker, script)
        for prohibited in (
            "os.unlink(key)",
            "docker stop",
            "docker start",
            "docker rm",
            "docker volume rm",
            "docker pull",
            "--privileged",
        ):
            self.assertNotIn(prohibited, script)

    def test_workflow_requires_typed_confirmation_and_checks_health(self) -> None:
        workflow = (
            Path(__file__).parents[2]
            / ".github"
            / "workflows"
            / "mission-control-conversation-recovery-package-removal.yml"
        ).read_text(encoding="utf-8")
        for marker in (
            "workflow_dispatch:",
            "REMOVE_HOSTINGER_RECOVERY_PACKAGE",
            "remove-conversation-recovery-package.sh",
            "healthz",
            "live_key_retained=true",
            "state_unchanged=true",
        ):
            self.assertIn(marker, workflow)
        for prohibited in (
            "docker volume rm",
            "docker pull",
            "actions/upload-artifact",
            "MISSION_CONTROL_CONVERSATION_RECOVERY_PASSPHRASE",
        ):
            self.assertNotIn(prohibited, workflow)


if __name__ == "__main__":
    unittest.main()
