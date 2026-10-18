import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub.mission_control_cto_mcp_fixture import OfflineMcpFixtureResource  # noqa: E402
from operations_hub.mission_control_cto_tool import CEO_SUBJECT, SCOPE, TOOL_NAME, VerifiedContext  # noqa: E402


RESOURCE_URI = "https://mcp.example.test/cto-proof"  # Synthetic only; not a deployable endpoint.
ISSUER = "https://identity.example.test/"
NOW = datetime(2026, 10, 18, 3, 0, tzinfo=timezone.utc)


def fixture():
    workspace = json.loads((ROOT / "mission-control" / "project-readiness.json").read_text(encoding="utf-8"))
    return workspace, None


def allowed(**changes):
    values = dict(subject=CEO_SUBJECT, audience=RESOURCE_URI, scopes=frozenset({SCOPE}),
                  expires_at=NOW + timedelta(minutes=5))
    values.update(changes)
    return VerifiedContext(**values)


class OfflineMcpFixtureTests(unittest.TestCase):
    def setUp(self):
        self.resource = OfflineMcpFixtureResource(RESOURCE_URI, ISSUER)

    def test_metadata_uses_exact_injected_https_resource_and_issuer(self):
        self.assertEqual(self.resource.protected_resource_metadata(), {
            "resource": RESOURCE_URI,
            "authorization_servers": [ISSUER],
            "scopes_supported": [SCOPE],
        })
        self.assertEqual(self.resource.metadata_uri,
                         "https://mcp.example.test/.well-known/oauth-protected-resource")

    def test_no_implicit_or_unsafe_resource_identifier(self):
        for value in ("", "mission-control-cto-read", "http://mcp.example.test",
                      "https://user@mcp.example.test", "https://mcp.example.test?x=1",
                      "https://mcp.example.test/#part", 'https://mcp.example.test/"x',
                      " https://mcp.example.test", "https://mcp.example.test\\bad"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                OfflineMcpFixtureResource(value, ISSUER)
        with self.assertRaises(ValueError):
            OfflineMcpFixtureResource(RESOURCE_URI, "http://identity.example.test/")

    def test_exactly_one_closed_read_only_oauth_tool(self):
        tools = self.resource.list_tools()["tools"]
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], TOOL_NAME)
        self.assertEqual(tools[0]["inputSchema"],
                         {"type": "object", "properties": {}, "additionalProperties": False})
        self.assertEqual(tools[0]["securitySchemes"], [{"type": "oauth2", "scopes": [SCOPE]}])
        self.assertEqual(tools[0]["annotations"],
                         {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False})

    def test_authorized_fixture_only_result(self):
        result = self.resource.call_tool(
            TOOL_NAME, {}, "synthetic", verifier=lambda _: allowed(),
            fixture_loader=fixture, now=NOW,
        )
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["project_id"], "phil-ai-os")
        self.assertEqual(result["structuredContent"]["authority_effect"], "none")
        self.assertEqual(json.loads(result["content"][0]["text"]), result["structuredContent"])

    def test_no_verifier_or_bad_authorization_never_loads_fixture(self):
        reads = []
        def loader():
            reads.append("read")
            return fixture()
        for verifier in (None, lambda _: allowed(audience="another-resource"),
                         lambda _: allowed(scopes=frozenset()),
                         lambda _: allowed(subject="other-owner"),
                         lambda _: allowed(expires_at=NOW),
                         lambda _: allowed(revoked=True)):
            with self.subTest(verifier=verifier):
                result = self.resource.call_tool(
                    TOOL_NAME, {}, "synthetic-secret", verifier=verifier,
                    fixture_loader=loader, now=NOW,
                )
                self.assertTrue(result["isError"])
                self.assertEqual(result["content"][0]["text"], "authentication_required")
                self.assertIn(self.resource.metadata_uri,
                              result["_meta"]["mcp/www_authenticate"][0])
                self.assertNotIn("synthetic-secret", json.dumps(result))
        self.assertEqual(reads, [])

    def test_unknown_tool_or_arguments_rejected_before_verification(self):
        calls = []
        def verifier(_):
            calls.append("verify")
            return allowed()
        for name, arguments in (("other", {}), (TOOL_NAME, {"url": "https://example.org"})):
            result = self.resource.call_tool(name, arguments, "synthetic", verifier=verifier,
                                             fixture_loader=fixture, now=NOW)
            self.assertEqual(result["content"][0]["text"], "tool_denied")
            self.assertNotIn("_meta", result)
        self.assertEqual(calls, [])

    def test_no_network_transport_or_live_secret_source(self):
        source = (ROOT / "src" / "operations_hub" / "mission_control_cto_mcp_fixture.py").read_text(encoding="utf-8")
        for forbidden in ("http.server", "requests", "urllib.request", "socket", "getenv",
                          "OPENAI_API_KEY", "MISSION_CONTROL_CEO_TOKEN", "FastAPI", "subprocess"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
