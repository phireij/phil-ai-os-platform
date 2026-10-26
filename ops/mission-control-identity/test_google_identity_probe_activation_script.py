"""Static safety checks for the separately approved Google identity-probe activation."""

from __future__ import annotations

import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "activate-google-identity-probe.sh"


class ProbeActivationScriptChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.content = SCRIPT.read_text(encoding="utf-8")

    def test_requires_an_explicit_operator_acknowledgement(self) -> None:
        self.assertIn("MISSION_CONTROL_GOOGLE_PROBE_ACTIVATION_ACKNOWLEDGEMENT", self.content)
        self.assertIn("approve-google-identity-probe-route", self.content)

    def test_requires_an_immutable_image_and_protected_host_secret_file(self) -> None:
        self.assertIn('[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]', self.content)
        self.assertIn('test "$SECRET_FILE" = /opt/phil-ai-os-platform/mission-control/secrets/google-identity-probe-client-secret', self.content)
        self.assertIn("'0:10002:640'", self.content)
        self.assertIn('type=bind,src=$SECRET_FILE,dst=/run/secrets/client_secret,readonly', self.content)
        self.assertIn('test "$(stat -c "%u:%g:%a" /run/secrets/client_secret)" = "0:10002:640"', self.content)

    def test_preflight_has_no_network_and_requires_the_inert_health_response(self) -> None:
        self.assertIn('docker run -d --name "$PREFLIGHT" --network none', self.content)
        self.assertIn('b"probe_ready;authority_effect=none"', self.content)

    def test_only_a_verified_stopped_inert_preflight_can_be_removed(self) -> None:
        self.assertIn("google_probe_stale_preflight_contract_failed", self.content)
        self.assertIn("host.get('NetworkMode') == 'none'", self.content)
        self.assertIn("labels.get('traefik.enable') == 'false'", self.content)
        self.assertIn("('bind', '/run/secrets/client_secret', False, secret_file)", self.content)
        self.assertIn('docker rm "$PREFLIGHT"', self.content)
        self.assertIn("Refusing activation: rollback container already exists", self.content)

    def test_live_route_is_constrained_to_google_auth_on_the_canonical_host(self) -> None:
        self.assertIn('test "$HOSTNAME" = miscon.phireij.cloud', self.content)
        self.assertIn('PathPrefix(\\`/auth/google\\`)', self.content)
        self.assertIn('traefik.http.routers.mission-control-google-probe.tls=true', self.content)

    def test_preserves_rollback_and_never_claims_a_mission_control_session(self) -> None:
        self.assertIn('restore_and_exit()', self.content)
        self.assertIn('docker rename "$CONTAINER" "$ROLLBACK"', self.content)
        self.assertNotIn('mission_control:conversation', self.content)


if __name__ == "__main__":
    unittest.main()
