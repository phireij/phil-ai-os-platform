from pathlib import Path
import unittest


class GoogleCeoSessionUpgradeChecks(unittest.TestCase):
    def test_upgrade_reuses_existing_secret_volume_and_retains_rollback(self) -> None:
        script = (Path(__file__).parent / "upgrade-google-ceo-session.sh").read_text(encoding="utf-8")
        for marker in (
            "CURRENT_IMAGE_DIGEST",
            "docker rename \"$SESSION\" \"$ROLLBACK\"",
            "rollback_retained=true",
            "existing_workloads_unchanged=true",
            "MISSION_CONTROL_GOOGLE_OIDC_ENABLED=true",
        ):
            self.assertIn(marker, script)
        for prohibited in (
            "docker volume create",
            "MISSION_CONTROL_CONVERSATION_ENABLED=true",
            "conversation_key",
        ):
            self.assertNotIn(prohibited, script)

    def test_upgrade_workflow_is_manual_and_conversation_storage_stays_disabled(self) -> None:
        workflow = (
            Path(__file__).parents[2]
            / ".github"
            / "workflows"
            / "mission-control-google-ceo-session-upgrade.yml"
        ).read_text(encoding="utf-8")
        for marker in (
            "workflow_dispatch:",
            "current_image_digest:",
            "upgrade-google-ceo-session.sh",
            "rollback",
            "conversation_authority=none",
        ):
            self.assertIn(marker, workflow)
        for prohibited in ("docker volume create", "MISSION_CONTROL_CONVERSATION_ENABLED=true"):
            self.assertNotIn(prohibited, workflow)


if __name__ == "__main__":
    unittest.main()
