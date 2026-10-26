import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub.github_sandbox_issue_pilot import (  # noqa: E402
    GitHubSandboxIssuePilotError,
    GitHubSandboxIssuePilotRequest,
    preview_issue_dispatch,
    request_from_record,
)


def valid_request(**overrides):
    request = {
        "target_repository": "phireij/mission-control-github-sandbox",
        "operation": "create_labelled_issue",
        "label": "mission-control-sandbox-pilot",
        "approval_id": "approval-preview-001",
        "plan_digest": "sha256:" + "a" * 64,
    }
    request.update(overrides)
    return GitHubSandboxIssuePilotRequest(**request)


class GitHubSandboxIssuePilotTests(unittest.TestCase):
    def test_allowlisted_request_returns_only_an_inert_preview(self):
        preview = preview_issue_dispatch(valid_request())
        self.assertEqual("blocked", preview.state)
        self.assertEqual("adapter_runtime_inactive", preview.reason)
        self.assertFalse(preview.network_authorized)
        self.assertFalse(preview.token_request_authorized)
        self.assertFalse(preview.dispatch_authorized)
        self.assertEqual("none", preview.authority_effect)

    def test_non_allowlisted_target_operation_or_label_fails_closed(self):
        for overrides, error in (
            ({"target_repository": "phireij/another-repository"}, "github_sandbox_target_not_allowlisted"),
            ({"operation": "create_issue"}, "github_sandbox_operation_not_allowlisted"),
            ({"label": "unreviewed"}, "github_sandbox_label_not_allowlisted"),
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(GitHubSandboxIssuePilotError, error):
                    preview_issue_dispatch(valid_request(**overrides))

    def test_request_record_rejects_credentials_and_unknown_fields(self):
        record = {
            "target_repository": "phireij/mission-control-github-sandbox",
            "operation": "create_labelled_issue",
            "label": "mission-control-sandbox-pilot",
            "approval_id": "approval-preview-001",
            "plan_digest": "sha256:" + "a" * 64,
        }
        self.assertEqual(valid_request(), request_from_record(record))
        for field, error in (
            ("private_key", "github_sandbox_credential_field_forbidden"),
            ("installation_token", "github_sandbox_credential_field_forbidden"),
            ("unexpected", "github_sandbox_request_fields_invalid"),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(GitHubSandboxIssuePilotError, error):
                    request_from_record({**record, field: "value"})

    def test_source_has_no_network_or_credential_loading_dependency(self):
        source = (ROOT / "src" / "operations_hub" / "github_sandbox_issue_pilot.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        forbidden_modules = {"requests", "urllib", "http.client", "socket", "subprocess", "os"}
        self.assertFalse(forbidden_modules & imported_modules)
        invoked_names = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertNotIn("open", invoked_names)


if __name__ == "__main__":
    unittest.main()
