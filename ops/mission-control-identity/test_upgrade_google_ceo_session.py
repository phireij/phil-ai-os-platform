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
            "replacement_image_pull_failed",
            "existing_secret_volume_preflight_failed",
            "candidate_container_start_failed",
            "candidate_container_not_running",
            "google_ceo_session_upgrade_phase=candidate_container_health",
            "google_ceo_session_upgrade_phase=stage_old_session",
            "google_ceo_session_upgrade_phase=initial_container_guard",
            "google_ceo_session_upgrade_phase=prior_rollback_identity",
            "google_ceo_session_upgrade_phase=prior_rollback_replacement",
            "prior_rollback_identity_mismatch",
            "google_ceo_session_upgrade_phase=stale_preflight_identity",
            "google_ceo_session_upgrade_phase=stale_preflight_cleanup",
            "stale_preflight_identity_mismatch",
            "google_ceo_session_upgrade_phase=existing_session_secret_volume",
            "google_ceo_session_upgrade_phase=existing_session_storage_mount",
            "google_ceo_session_upgrade_phase=existing_session_storage_configuration",
            "google_ceo_session_upgrade_phase=existing_state_volume_preflight",
            "existing_state_volume_preflight_failed",
            "STATE_VOLUME=phil-ai-os-mission-control-conversation-state-v1",
            "MISSION_CONTROL_CONVERSATION_ENABLED=true",
            "MISSION_CONTROL_CONVERSATION_KEY_FILE=/run/secrets/conversation_key",
            "MISSION_CONTROL_CONVERSATION_READONLY_PREFLIGHT=true",
            "type=volume,src=$STATE_VOLUME,dst=$STATE_DIR,readonly",
            "state_volume=$STATE_VOLUME",
            "google_ceo_session_upgrade_phase=route_collision_guard",
        ):
            self.assertIn(marker, script)
        for prohibited in (
            "docker volume create",
            "docker rm -f \"$PREFLIGHT\" -v",
            "docker rm -f \"$ROLLBACK\"",
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
            "encrypted_storage_preserved=true",
            "conversation_authority=enabled",
        ):
            self.assertIn(marker, workflow)
        for prohibited in ("docker volume create", "MISSION_CONTROL_CONVERSATION_ENABLED=true"):
            self.assertNotIn(prohibited, workflow)

    def test_session_image_includes_conversation_store_dependency(self) -> None:
        dockerfile = (Path(__file__).parents[2] / "Dockerfile.mission-control-google-ceo-session").read_text(encoding="utf-8")
        self.assertIn("COPY ops/mission-control-identity/proposal_evidence.py /srv/proposal_evidence.py", dockerfile)


if __name__ == "__main__":
    unittest.main()
