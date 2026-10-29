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
            "google_ceo_session_upgrade_phase=prior_rollback_legacy_archive",
            "google_ceo_session_upgrade_phase=prior_rollback_route_less_legacy_archive",
            "pre-route storage rollback has no restart policy or Traefik labels",
            "legacy_rollback_archive_unavailable",
            "LEGACY_ROLLBACK=\"${ROLLBACK}-legacy\"",
            "docker rename \"$ROLLBACK\" \"$LEGACY_ROLLBACK\"",
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
            "PathPrefix(\\`/api/conversations\\`)",
            "PathPrefix(\\`/api/notifications\\`)",
            "PathPrefix(\\`/api/task-proposals\\`)",
        ):
            self.assertIn(marker, script)
        for prohibited in (
            "docker volume create",
            "docker rm -f \"$PREFLIGHT\" -v",
            "docker rm -f \"$ROLLBACK\"",
            "PathPrefix(\\`/api\\`)",
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
            "mission-control-google-ceo-session-recovery\\.yml",
            "mission-control-google-ceo-session-route-cutover\\.yml",
            "mission-control-google-ceo-session-ci\\.yml",
            "test_upgrade_google_ceo_session\\.py",
            "allowed_safety_only_delta=true",
        ):
            self.assertIn(marker, workflow)
        for prohibited in ("docker volume create", "MISSION_CONTROL_CONVERSATION_ENABLED=true"):
            self.assertNotIn(prohibited, workflow)

    def test_openai_configuration_and_dispatch_are_separate_gates(self) -> None:
        script = (Path(__file__).parent / "upgrade-google-ceo-session.sh").read_text(encoding="utf-8")
        workflow = (Path(__file__).parents[2] / ".github" / "workflows" /
                    "mission-control-google-ceo-session-upgrade.yml").read_text(encoding="utf-8")
        for marker in ("configure_openai:", "MISSION_CONTROL_ALLOW_OPENAI_CONFIGURATION",
                       "openai_configuration_guard_required", "openai_secret_volume_preflight_failed",
                       "openai_configuration_validation_failed", "openai_dispatch_enabled=false",
                       "MISSION_CONTROL_OPENAI_API_KEY_FILE=/run/secrets/openai/api_key"):
            self.assertIn(marker, script + workflow)
        self.assertNotIn("--env 'MISSION_CONTROL_OPENAI_DISPATCH_ENABLED=true'", script)
        self.assertNotIn("MISSION_CONTROL_OPENAI_DISPATCH_ENABLED=true", workflow)

    def test_stopped_session_recovery_restarts_only_the_verified_existing_container(self) -> None:
        workflow = (
            Path(__file__).parents[2] / ".github" / "workflows" /
            "mission-control-google-ceo-session-recovery.yml"
        ).read_text(encoding="utf-8")
        for marker in (
            "workflow_dispatch:",
            "current_image_digest:",
            "docker inspect '$SESSION' --format '{{.State.Running}}'",
            "docker start '$SESSION'",
            "existing_container_restarted=true",
            "secrets_unchanged=true",
            "storage_unchanged=true",
            "session_ready;conversation_authority=enabled",
        ):
            self.assertIn(marker, workflow)
        for prohibited in (
            "docker rm",
            "docker run",
            "docker pull",
            "docker volume create",
            "MISSION_CONTROL_OPENAI_DISPATCH_ENABLED=true",
        ):
            self.assertNotIn(prohibited, workflow)

    def test_route_cutover_restores_the_legacy_probe_when_session_boundary_fails(self) -> None:
        workflow = (
            Path(__file__).parents[2] / ".github" / "workflows" /
            "mission-control-google-ceo-session-route-cutover.yml"
        ).read_text(encoding="utf-8")
        for marker in (
            "workflow_dispatch:",
            "current_session_image_digest:",
            "docker stop '$PROBE'",
            "docker start '$PROBE' >/dev/null",
            "probe_restore_attempted=$probe_stopped",
            "session_ready;conversation_authority=enabled",
            "legacy_probe_stopped=true",
            "session_unchanged=true",
            "secrets_unchanged=true",
            "storage_unchanged=true",
        ):
            self.assertIn(marker, workflow)
        for prohibited in (
            "docker rm",
            "docker run",
            "docker pull",
            "docker volume create",
            "MISSION_CONTROL_OPENAI_DISPATCH_ENABLED=true",
        ):
            self.assertNotIn(prohibited, workflow)

    def test_rollback_inventory_is_read_only_and_does_not_expose_mount_names(self) -> None:
        workflow = (
            Path(__file__).parents[2] / ".github" / "workflows" /
            "mission-control-google-ceo-session-rollback-inventory.yml"
        ).read_text(encoding="utf-8")
        for marker in (
            "workflow_dispatch:",
            "secret_volume_matches_current=",
            "state_volume_matches_current=",
            "content_accessed=false",
            "authority_effect=none",
        ):
            self.assertIn(marker, workflow)
        for prohibited in ("docker start", "docker stop", "docker rm", "docker run", "docker pull"):
            self.assertNotIn(prohibited, workflow)

    def test_session_image_includes_conversation_store_dependency(self) -> None:
        dockerfile = (Path(__file__).parents[2] / "Dockerfile.mission-control-google-ceo-session").read_text(encoding="utf-8")
        self.assertIn("COPY ops/mission-control-identity/proposal_evidence.py /srv/proposal_evidence.py", dockerfile)

    def test_same_image_restart_requires_the_explicit_reconfiguration_guard(self) -> None:
        script = (Path(__file__).parent / "upgrade-google-ceo-session.sh").read_text(encoding="utf-8")
        self.assertIn("MISSION_CONTROL_ALLOW_SAME_IMAGE_RECONFIGURATION", script)
        self.assertIn("same_image_without_reconfiguration_guard", script)
        self.assertIn("reconfiguration_guard_requires_same_image", script)
        self.assertIn("SAME_IMAGE_RECONFIGURATION=true", script)
        self.assertIn("MISSION_CONTROL_TELEGRAM_DELIVERY_ENABLED=true", script)
        self.assertIn("ACTIVE_TELEGRAM_DELIVERY=false", script)
        self.assertIn("MISSION_CONTROL_ALLOW_TELEGRAM_ENABLEMENT", script)
        self.assertIn("telegram_enablement_guard_required", script)
        self.assertIn("telegram_delivery_enabled=$TELEGRAM_DELIVERY_ENABLED", script)
        self.assertIn("same_image_reconfiguration=${MISSION_CONTROL_ALLOW_SAME_IMAGE_RECONFIGURATION:-false}", script)

    def test_activation_reenables_delivery_with_an_explicit_same_image_guard(self) -> None:
        workflow = (
            Path(__file__).parents[2]
            / ".github"
            / "workflows"
            / "mission-control-telegram-delivery-activate.yml"
        ).read_text(encoding="utf-8")
        for marker in (
            'confirmation:',
            'ENABLE_DEDICATED_TELEGRAM_TEST',
            'MISSION_CONTROL_ALLOW_TELEGRAM_ENABLEMENT=true',
            'if [[ "$IMAGE_DIGEST" == "$CURRENT_IMAGE_DIGEST" ]]',
            'MISSION_CONTROL_ALLOW_SAME_IMAGE_RECONFIGURATION=true',
            'test "$IMAGE_DIGEST" = "$CURRENT_IMAGE_DIGEST"',
            'git merge-base --is-ancestor "$SOURCE_REVISION" HEAD',
            'allowed_safety_only_delta=true',
            'mission-control-google-ceo-session-rollback-inventory\\.yml',
            'upgrade-google-ceo-session\\.sh',
            'controlled_test_pending=true',
        ):
            self.assertIn(marker, workflow)
        self.assertNotIn("sendMessage", workflow)

    def test_destination_rotation_is_limited_to_an_existing_chat_id_file(self) -> None:
        installer = (Path(__file__).parent / "install-telegram-delivery-secrets.sh").read_text(encoding="utf-8")
        for marker in (
            "MISSION_CONTROL_TELEGRAM_SECRET_ROTATION",
            "--env \"MISSION_CONTROL_TELEGRAM_SECRET_ROTATION=${MISSION_CONTROL_TELEGRAM_SECRET_ROTATION:-}\"",
            'rotation not in {"", "chat_id"}',
            "token_mismatch",
            "rotation_requires_existing",
            "os.replace(replacement, f\"{secret_dir}/chat_id\")",
            "chat_id_rotated=true",
        ):
            self.assertIn(marker, installer)
        self.assertNotIn("print(token", installer)
        self.assertNotIn("print(chat", installer)

    def test_destination_reconfiguration_is_manual_and_does_not_send(self) -> None:
        workflow = (
            Path(__file__).parents[2]
            / ".github"
            / "workflows"
            / "mission-control-telegram-destination-reconfigure.yml"
        ).read_text(encoding="utf-8")
        for marker in (
            "workflow_dispatch:",
            "RECONFIGURE_TELEGRAM_DESTINATION",
            "MISSION_CONTROL_TELEGRAM_SECRET_ROTATION=chat_id",
            "MISSION_CONTROL_ALLOW_SAME_IMAGE_RECONFIGURATION=true",
            "CURRENT_IMAGE_DIGEST='$CURRENT_IMAGE_DIGEST'",
            "controlled_test_not_dispatched=true",
        ):
            self.assertIn(marker, workflow)
        self.assertNotIn("sendMessage", workflow)


if __name__ == "__main__":
    unittest.main()
