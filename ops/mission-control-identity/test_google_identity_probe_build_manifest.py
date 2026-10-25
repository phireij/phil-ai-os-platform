"""Static checks for the inactive Google identity-probe build manifests."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "Dockerfile.mission-control-google-identity-probe"
CI_WORKFLOW = ROOT / ".github/workflows/mission-control-google-identity-probe-ci.yml"
IMAGE_WORKFLOW = ROOT / ".github/workflows/mission-control-google-identity-probe-image.yml"

PINNED_DEPENDENCIES = (
    "cryptography==47.0.0",
    "google-auth==2.50.0",
    "requests==2.32.4",
)


class ProbeBuildManifestChecks(unittest.TestCase):
    def test_runtime_and_ci_use_the_tested_dependency_set(self) -> None:
        for manifest in (DOCKERFILE, CI_WORKFLOW, IMAGE_WORKFLOW):
            with self.subTest(manifest=manifest.name):
                content = manifest.read_text(encoding="utf-8")
                for dependency in PINNED_DEPENDENCIES:
                    self.assertIn(dependency, content)
                self.assertNotIn("google-auth==2.62.0", content)
                self.assertNotIn("requests==2.34.2", content)

    def test_runtime_remains_nonroot_and_does_not_activate_the_probe(self) -> None:
        content = DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("USER app", content)
        self.assertIn('ENTRYPOINT ["python3", "/srv/google_identity_probe.py"]', content)
        self.assertNotIn("MISSION_CONTROL_GOOGLE_PROBE_ENABLED=true", content)

    def test_ci_runs_offline_security_checks_before_build_or_publish(self) -> None:
        for workflow in (CI_WORKFLOW, IMAGE_WORKFLOW):
            with self.subTest(workflow=workflow.name):
                content = workflow.read_text(encoding="utf-8")
                self.assertIn("test_google_identity_probe.py", content)
                self.assertIn("bash -n ops/mission-control-identity/activate-google-identity-probe.sh", content)
        self.assertIn("docker build", CI_WORKFLOW.read_text(encoding="utf-8"))
        self.assertIn("docker buildx build", IMAGE_WORKFLOW.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
