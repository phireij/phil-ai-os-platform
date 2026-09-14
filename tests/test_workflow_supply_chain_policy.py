import tempfile
import unittest
from pathlib import Path

from scripts.validate_workflow_supply_chain import validate_repository, validate_workflow


PINNED_CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"


class WorkflowSupplyChainPolicyTests(unittest.TestCase):
    def write_workflow(self, body: str) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "workflow.yml"
        path.write_text(body, encoding="utf-8")
        return path

    def test_accepts_pinned_action_and_local_action(self):
        path = self.write_workflow(
            f"jobs:\n  test:\n    steps:\n      - uses: {PINNED_CHECKOUT} # v7.0.1\n      - uses: ./local-action\n"
        )
        self.assertEqual(validate_workflow(path), [])

    def test_rejects_mutable_action_tag(self):
        path = self.write_workflow("jobs:\n  test:\n    steps:\n      - uses: actions/checkout@v7\n")
        errors = validate_workflow(path)
        self.assertEqual(len(errors), 1)
        self.assertIn("immutable 40-character commit SHA", errors[0])

    def test_rejects_pull_request_target(self):
        path = self.write_workflow("on:\n  pull_request_target:\n")
        errors = validate_workflow(path)
        self.assertEqual(len(errors), 1)
        self.assertIn("pull_request_target is prohibited", errors[0])

    def test_rejects_write_all_permissions(self):
        path = self.write_workflow("permissions: write-all\n")
        errors = validate_workflow(path)
        self.assertEqual(len(errors), 1)
        self.assertIn("permissions: write-all is prohibited", errors[0])

    def test_repository_requires_workflows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            errors = validate_repository(Path(temp_dir))
        self.assertEqual(len(errors), 1)
        self.assertIn("no GitHub Actions workflow files found", errors[0])


if __name__ == "__main__":
    unittest.main()
