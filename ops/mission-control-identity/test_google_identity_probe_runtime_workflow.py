"""Static checks for the manual-only Google identity-probe runtime workflow."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/mission-control-google-identity-probe-deploy.yml"
STAGER = ROOT / "ops/mission-control-identity/stage-google-identity-probe-host-secret.sh"


class ProbeRuntimeWorkflowChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.stager = STAGER.read_text(encoding="utf-8")

    def test_runtime_workflow_is_manual_only_and_activation_is_exactly_acknowledged(self) -> None:
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("  push:", self.workflow)
        self.assertNotIn("  pull_request:", self.workflow)
        self.assertIn("activation_acknowledgement:", self.workflow)
        self.assertIn("approve-google-identity-probe-route", self.workflow)
        self.assertIn("inputs.mode == 'activate'", self.workflow)

    def test_preflight_is_explicitly_non_mutating(self) -> None:
        self.assertIn("VPS preflight passed; no route, volume, secret, or container was created.", self.workflow)
        self.assertIn("Inspect the VPS without creating a route, secret, or container", self.workflow)
        self.assertIn("google_probe_route_collision=none", self.workflow)
        self.assertIn("concurrency:", self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)

    def test_activation_uses_immutable_image_and_recovers_after_public_check_failure(self) -> None:
        self.assertIn("[[ \"$digest\" =~ ^sha256:[0-9a-f]{64}$ ]]", self.workflow)
        self.assertIn("--platform linux/amd64", self.workflow)
        self.assertIn("Run the separately acknowledged remote activation script", self.workflow)
        self.assertIn("Restore the prior runtime after failed public verification", self.workflow)
        self.assertIn("docker rename \"$ROLLBACK\" \"$CONTAINER\"", self.workflow)

    def test_read_only_audit_and_emergency_stop_require_distinct_exact_acknowledgements(self) -> None:
        self.assertIn("approve-read-only-google-route-audit", self.workflow)
        self.assertIn("approve-emergency-stop-google-ceo-session", self.workflow)
        self.assertIn("Audit route-claiming and exact temporary probe containers", self.workflow)
        self.assertIn('"${CONTAINER}-preflight" "${CONTAINER}-rollback"', self.workflow)
        self.assertIn("audit.probe_temporary_containers_present", self.workflow)
        self.assertIn("audit.public_health_status", self.workflow)
        self.assertIn("docker update --restart=no \"$CONTAINER\"", self.workflow)
        self.assertIn("docker stop --time 20 \"$CONTAINER\"", self.workflow)
        self.assertIn("volumes_preserved=true rollback_containers_preserved=true", self.workflow)

    def test_cleanup_is_limited_to_named_stopped_rollbacks_and_preserves_volumes(self) -> None:
        self.assertIn("approve-cleanup-stopped-mission-control-rollbacks", self.workflow)
        self.assertIn("cleanup-stopped-rollbacks", self.workflow)
        self.assertIn("phil-ai-os-mission-control-google-ceo-session-storage-rollback", self.workflow)
        self.assertIn("phil-ai-os-mission-control-google-ceo-session-rollback-legacy", self.workflow)
        self.assertIn("phil-ai-os-mission-control-google-identity-probe-rollback", self.workflow)
        self.assertIn("test \"$(docker inspect \"$container\" --format '{{.State.Running}}')\" = false", self.workflow)
        self.assertIn("volumes_preserved=true images_preserved=true contained_ceo_session_preserved=true", self.workflow)

    def test_secret_stager_accepts_secret_only_on_stdin_and_sets_strict_permissions(self) -> None:
        self.assertIn('cat > "$temporary"', self.stager)
        self.assertNotIn("MISSION_CONTROL_GOOGLE_CLIENT_SECRET", self.stager)
        self.assertIn("chown root:10002 \"$temporary\"", self.stager)
        self.assertIn("chmod 640 \"$temporary\"", self.stager)
        self.assertIn("BACKUP_FILE=\"${SECRET_FILE}.rollback\"", self.stager)
        self.assertIn("mv -- \"$SECRET_FILE\" \"$BACKUP_FILE\"", self.stager)
        self.assertIn("mv -f -- \"$temporary\" \"$SECRET_FILE\"", self.stager)
        self.assertIn("trap restore EXIT HUP INT TERM", self.stager)

    def test_workflow_uses_host_secret_lifecycle_without_deleting_volumes(self) -> None:
        self.assertIn("Stage the client secret in the protected host file", self.workflow)
        self.assertIn("protected_secret_backup_removed=true", self.workflow)
        self.assertNotIn("prior_secret_volume_removed", self.workflow)
        self.assertNotIn("docker volume rm \"$previous_volume\"", self.workflow)


if __name__ == "__main__":
    unittest.main()
