import ast
import sys
import unittest
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub.github_sandbox_credential_boundary import (  # noqa: E402
    EXPECTED_PRIVATE_KEY_PATH,
    GitHubSandboxCredentialBoundaryError,
    PrivateKeyFileMetadata,
    preview_installation_token_scope,
    preview_jwt_timing,
    validate_private_key_metadata,
)


def valid_metadata(**overrides):
    values = {
        "path": EXPECTED_PRIVATE_KEY_PATH,
        "is_regular_file": True,
        "file_owner_uid": 0,
        "file_mode": 0o400,
        "parent_owner_uid": 0,
        "parent_mode": 0o700,
    }
    values.update(overrides)
    return PrivateKeyFileMetadata(**values)


class GitHubSandboxCredentialBoundaryTests(unittest.TestCase):
    def test_valid_metadata_yields_only_an_inactive_preview(self):
        preview = validate_private_key_metadata(valid_metadata())
        self.assertEqual(str(EXPECTED_PRIVATE_KEY_PATH), preview.private_key_path)
        self.assertEqual("metadata_valid_runtime_inactive", preview.state)
        self.assertFalse(preview.key_read_authorized)
        self.assertFalse(preview.jwt_authorized)
        self.assertFalse(preview.token_request_authorized)
        self.assertFalse(preview.dispatch_authorized)
        self.assertEqual("none", preview.authority_effect)

    def test_key_metadata_rejects_path_owner_mode_and_file_type_drift(self):
        for overrides, error in (
            ({"path": PurePosixPath("/tmp/private-key.pem")}, "github_sandbox_key_path_not_allowlisted"),
            ({"is_regular_file": False}, "github_sandbox_key_not_regular_file"),
            ({"file_owner_uid": 1000}, "github_sandbox_key_owner_invalid"),
            ({"file_mode": 0o640}, "github_sandbox_key_mode_invalid"),
            ({"parent_mode": 0o755}, "github_sandbox_key_parent_mode_invalid"),
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(GitHubSandboxCredentialBoundaryError, error):
                    validate_private_key_metadata(valid_metadata(**overrides))

    def test_jwt_timing_is_short_lived_and_never_authorized(self):
        preview = preview_jwt_timing(2_000_000_000)
        self.assertEqual(1_999_999_940, preview.issued_at)
        self.assertEqual(2_000_000_540, preview.expires_at)
        self.assertLessEqual(preview.expires_at - 2_000_000_000, 600)
        self.assertFalse(preview.jwt_authorized)
        self.assertEqual("none", preview.authority_effect)
        for lifetime in (0, 601, True):
            with self.subTest(lifetime=lifetime):
                with self.assertRaisesRegex(GitHubSandboxCredentialBoundaryError, "github_sandbox_jwt_lifetime_invalid"):
                    preview_jwt_timing(2_000_000_000, lifetime)

    def test_installation_scope_is_one_repository_and_issue_write_only(self):
        preview = preview_installation_token_scope(98765, 123456)
        self.assertEqual(98765, preview.installation_id)
        self.assertEqual(123456, preview.repository_id)
        self.assertEqual(("issues:write",), preview.permissions)
        self.assertFalse(preview.token_request_authorized)
        for installation_id, repository_id, error in ((0, 1, "github_sandbox_installation_id_invalid"), (1, 0, "github_sandbox_repository_id_invalid")):
            with self.subTest(installation_id=installation_id, repository_id=repository_id):
                with self.assertRaisesRegex(GitHubSandboxCredentialBoundaryError, error):
                    preview_installation_token_scope(installation_id, repository_id)

    def test_source_cannot_read_key_or_use_network_client(self):
        source = (ROOT / "src" / "operations_hub" / "github_sandbox_credential_boundary.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse({"requests", "urllib", "http.client", "socket", "subprocess", "os"} & imported_modules)
        invoked_names = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertNotIn("open", invoked_names)


if __name__ == "__main__":
    unittest.main()
