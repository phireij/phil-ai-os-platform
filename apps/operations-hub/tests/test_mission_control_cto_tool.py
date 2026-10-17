import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub.mission_control_cto_tool import (  # noqa: E402
    CEO_SUBJECT, RESOURCE, SCOPE, TOOL_DESCRIPTOR, TOOL_NAME,
    ToolDenied, VerifiedContext, invoke_fixture_tool,
)


NOW = datetime(2026, 10, 17, 3, 0, tzinfo=timezone.utc)


def fixture():
    return json.loads((ROOT / "mission-control" / "project-readiness.json").read_text(encoding="utf-8")), None


def allowed(**changes):
    values = dict(subject=CEO_SUBJECT, audience=RESOURCE, scopes=frozenset({SCOPE}), expires_at=NOW + timedelta(minutes=5))
    values.update(changes)
    return VerifiedContext(**values)


class OfflineCtoToolTests(unittest.TestCase):
    def invoke(self, *, name=TOOL_NAME, arguments=None, credential="synthetic", verifier=None, loader=fixture):
        return invoke_fixture_tool(name, {} if arguments is None else arguments, credential,
                                   verifier=verifier, fixture_loader=loader, now=NOW)

    def test_one_read_only_closed_tool(self):
        self.assertEqual(TOOL_DESCRIPTOR["name"], TOOL_NAME)
        self.assertEqual(TOOL_DESCRIPTOR["inputSchema"], {"type": "object", "properties": {}, "additionalProperties": False})
        self.assertEqual(TOOL_DESCRIPTOR["annotations"]["readOnlyHint"], True)
        self.assertEqual(TOOL_DESCRIPTOR["annotations"]["destructiveHint"], False)

    def test_authorized_synthetic_fixture_projection(self):
        result = self.invoke(verifier=lambda _: allowed())
        self.assertEqual(result["project_id"], "phil-ai-os")
        self.assertEqual(result["authority_effect"], "none")
        self.assertEqual(result["overall_status"], "unknown")
        self.assertEqual(result["agent_posture"]["availability"], "unavailable")

    def test_missing_verifier_and_credentials_fail_closed_without_source_read(self):
        calls = []
        def loader():
            calls.append("read")
            return fixture()
        for credential, verifier in (("synthetic", None), (None, lambda _: allowed()), ("", lambda _: allowed())):
            with self.subTest(credential=credential), self.assertRaises(ToolDenied):
                self.invoke(credential=credential, verifier=verifier, loader=loader)
        self.assertEqual(calls, [])

    def test_wrong_tool_and_caller_selected_inputs_fail_before_verification(self):
        calls = []
        def verifier(_):
            calls.append("verify")
            return allowed()
        for name, arguments in (("other", {}), (TOOL_NAME, {"project_id": "other"}),
                                (TOOL_NAME, {"url": "https://example.org"})):
            with self.subTest(name=name, arguments=arguments), self.assertRaises(ToolDenied):
                self.invoke(name=name, arguments=arguments, verifier=verifier)
        self.assertEqual(calls, [])

    def test_invalid_identity_and_scope_fail_before_source_read(self):
        cases = (
            allowed(subject="another-owner"), allowed(audience="another-resource"),
            allowed(scopes=frozenset()), allowed(expires_at=NOW),
            allowed(revoked=True), allowed(expires_at=NOW.replace(tzinfo=None)),
        )
        calls = []
        def loader():
            calls.append("read")
            return fixture()
        for context in cases:
            with self.subTest(context=context), self.assertRaises(ToolDenied):
                self.invoke(verifier=lambda _: context, loader=loader)
        self.assertEqual(calls, [])

    def test_verifier_error_and_bad_result_fail_closed(self):
        for verifier in (lambda _: None, lambda _: {"subject": CEO_SUBJECT},
                         lambda _: (_ for _ in ()).throw(RuntimeError("secret"))):
            with self.assertRaisesRegex(ToolDenied, "^tool_denied$"):
                self.invoke(verifier=verifier)

    def test_no_implicit_fixture_loader(self):
        with self.assertRaises(ToolDenied):
            self.invoke(verifier=lambda _: allowed(), loader=None)

    def test_offline_module_has_no_network_or_live_secret_dependency(self):
        source = (ROOT / "src" / "operations_hub" / "mission_control_cto_tool.py").read_text(encoding="utf-8")
        for forbidden in ("http.server", "requests", "urllib.request", "socket", "OPENAI_API_KEY",
                          "MISSION_CONTROL_CEO_TOKEN", "getenv", "subprocess", "FastAPI"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
