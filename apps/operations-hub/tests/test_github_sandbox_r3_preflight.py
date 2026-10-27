import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub.github_sandbox_issue_pilot import GitHubSandboxIssuePilotRequest  # noqa: E402
from operations_hub.github_sandbox_r3_preflight import (  # noqa: E402
    GitHubSandboxR3PreflightError,
    PilotIdempotencyEvidence,
    PilotLimitEvidence,
    R3PilotApprovalEvidence,
    review_r3_preflight,
)


NOW = 2_000_000_000
PLAN_DIGEST = "sha256:" + "a" * 64


def request():
    return GitHubSandboxIssuePilotRequest(
        target_repository="phireij/mission-control-github-sandbox",
        operation="create_labelled_issue",
        label="mission-control-sandbox-pilot",
        approval_id="approval-r3-001",
        plan_digest=PLAN_DIGEST,
    )


def approval(**overrides):
    values = {
        "approval_id": "approval-r3-001",
        "plan_digest": PLAN_DIGEST,
        "risk_level": "R3",
        "typed_confirmation": "CREATE ONE LABELLED SANDBOX ISSUE in phireij/mission-control-github-sandbox",
        "ceo_reauthenticated_at_epoch": NOW - 60,
        "approved_at_epoch": NOW - 60,
        "expires_at_epoch": NOW + 840,
        "revoked": False,
        "consumed": False,
    }
    values.update(overrides)
    return R3PilotApprovalEvidence(**values)


def limits(**overrides):
    values = {
        "issues_created_in_last_24_hours": 0,
        "external_action_budget_usd": 0,
        "reserved_external_action_budget_usd": 0,
        "emergency_stop_active": False,
    }
    values.update(overrides)
    return PilotLimitEvidence(**values)


class GitHubSandboxR3PreflightTests(unittest.TestCase):
    def test_complete_evidence_still_returns_only_a_blocked_preview(self):
        preview = review_r3_preflight(request(), approval(), limits(), PilotIdempotencyEvidence("absent"), NOW)
        self.assertEqual("blocked", preview.state)
        self.assertEqual("adapter_runtime_inactive", preview.reason)
        self.assertFalse(preview.execution_lease_issued)
        self.assertFalse(preview.credential_read_authorized)
        self.assertFalse(preview.token_request_authorized)
        self.assertFalse(preview.dispatch_authorized)
        self.assertEqual("none", preview.authority_effect)

    def test_approval_drift_expiry_or_reuse_fails_closed(self):
        for overrides, error in (
            ({"plan_digest": "sha256:" + "b" * 64}, "github_sandbox_plan_digest_mismatch"),
            ({"typed_confirmation": "approve"}, "github_sandbox_typed_confirmation_invalid"),
            ({"expires_at_epoch": NOW + 1}, "github_sandbox_approval_ttl_invalid"),
            ({"revoked": True}, "github_sandbox_approval_revoked"),
            ({"consumed": True}, "github_sandbox_approval_already_consumed"),
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(GitHubSandboxR3PreflightError, error):
                    review_r3_preflight(request(), approval(**overrides), limits(), PilotIdempotencyEvidence("absent"), NOW)
        with self.assertRaisesRegex(GitHubSandboxR3PreflightError, "github_sandbox_ceo_reauthentication_stale"):
            review_r3_preflight(request(), approval(ceo_reauthenticated_at_epoch=NOW - 301), limits(), PilotIdempotencyEvidence("absent"), NOW)

    def test_stop_limit_budget_or_idempotency_evidence_fails_closed(self):
        for pilot_limits, idempotency, error in (
            (limits(emergency_stop_active=True), PilotIdempotencyEvidence("absent"), "github_sandbox_emergency_stop_active"),
            (limits(issues_created_in_last_24_hours=1), PilotIdempotencyEvidence("absent"), "github_sandbox_24_hour_limit_reached"),
            (limits(external_action_budget_usd=1), PilotIdempotencyEvidence("absent"), "github_sandbox_external_action_budget_invalid"),
            (limits(), PilotIdempotencyEvidence("completed"), "github_sandbox_idempotency_not_clear"),
        ):
            with self.subTest(error=error):
                with self.assertRaisesRegex(GitHubSandboxR3PreflightError, error):
                    review_r3_preflight(request(), approval(), pilot_limits, idempotency, NOW)

    def test_source_has_no_credential_or_execution_dependency(self):
        source = (ROOT / "src" / "operations_hub" / "github_sandbox_r3_preflight.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse({"requests", "urllib", "http.client", "socket", "subprocess", "os", "pathlib"} & imported_modules)
        invoked_names = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertNotIn("open", invoked_names)


if __name__ == "__main__":
    unittest.main()
