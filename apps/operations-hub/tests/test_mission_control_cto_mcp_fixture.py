import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub.mission_control_cto_mcp_fixture import (  # noqa: E402
    CANONICAL_RESOURCE_URI,
    OfflineApprovedLoopbackMcpPlan,
    OfflineMcpFixtureResource,
)
from operations_hub.mission_control_cto_tool import CEO_SUBJECT, SCOPE, TOOL_NAME, VerifiedContext  # noqa: E402
from operations_hub.mission_control_cto_auth0_verifier import (  # noqa: E402
    Auth0JwtVerifier,
    ISSUER_ENV,
    JWKS_ENV,
    OWNER_SUBJECT_FILE_ENV,
    verifier_from_environment,
)


RESOURCE_URI = "https://mcp.example.test/cto-proof"  # Synthetic only; not a deployable endpoint.
ISSUER = "https://identity.example.test/"
METADATA_URI = "https://mcp.example.test/.well-known/oauth-protected-resource/cto-proof"
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
        self.resource = OfflineMcpFixtureResource(RESOURCE_URI, ISSUER, METADATA_URI)

    def test_metadata_uses_exact_injected_https_resource_and_issuer(self):
        self.assertEqual(self.resource.protected_resource_metadata(), {
            "resource": RESOURCE_URI,
            "authorization_servers": [ISSUER],
            "scopes_supported": [SCOPE],
        })
        self.assertEqual(self.resource.metadata_uri,
                         METADATA_URI)

    def test_no_implicit_or_unsafe_resource_identifier(self):
        for value in ("", "mission-control-cto-read", "http://mcp.example.test",
                      "https://user@mcp.example.test", "https://mcp.example.test?x=1",
                      "https://mcp.example.test/#part", 'https://mcp.example.test/"x',
                      " https://mcp.example.test", "https://mcp.example.test\\bad"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                OfflineMcpFixtureResource(value, ISSUER, METADATA_URI)
        with self.assertRaises(ValueError):
            OfflineMcpFixtureResource(RESOURCE_URI, "http://identity.example.test/", METADATA_URI)
        for metadata_uri in (
            "http://mcp.example.test/.well-known/oauth-protected-resource",
            "https://other.example.test/.well-known/oauth-protected-resource",
            "https://mcp.example.test/not-well-known",
            "https://mcp.example.test/.well-known/oauth-protected-resource-unrelated",
        ):
            with self.subTest(metadata_uri=metadata_uri), self.assertRaises(ValueError):
                OfflineMcpFixtureResource(RESOURCE_URI, ISSUER, metadata_uri)

    def test_approved_plan_pins_external_identity_to_private_loopback_transport(self):
        plan = OfflineApprovedLoopbackMcpPlan(
            ISSUER,
            "https://miscon.phireij.cloud/.well-known/oauth-protected-resource/mcp",
            "http://127.0.0.1:8787/mcp",
        )
        self.assertEqual(plan.resource_contract().resource_uri, CANONICAL_RESOURCE_URI)
        self.assertEqual(plan.resource_contract().metadata_uri,
                         "https://miscon.phireij.cloud/.well-known/oauth-protected-resource/mcp")
        self.assertEqual(plan.transport_boundary(), {
            "canonical_resource_uri": CANONICAL_RESOURCE_URI,
            "loopback_mcp_uri": "http://127.0.0.1:8787/mcp",
            "public_mcp_listener": False,
            "future_tunnel_client_colocated": True,
        })

    def test_approved_plan_rejects_non_loopback_or_noncanonical_metadata(self):
        baseline = (ISSUER, "https://miscon.phireij.cloud/.well-known/oauth-protected-resource/mcp",
                    "http://127.0.0.1:8787/mcp")
        for changes in (
            {"loopback_mcp_uri": "http://0.0.0.0:8787/mcp"},
            {"loopback_mcp_uri": "https://127.0.0.1:8787/mcp"},
            {"loopback_mcp_uri": "http://127.0.0.1:0/mcp"},
            {"loopback_mcp_uri": "http://127.0.0.1:8787/other"},
            {"protected_resource_metadata_uri": "https://other.example/.well-known/oauth-protected-resource/mcp"},
        ):
            values = dict(zip(("authorization_issuer", "protected_resource_metadata_uri", "loopback_mcp_uri"), baseline))
            values.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                OfflineApprovedLoopbackMcpPlan(**values)

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


class Auth0VerifierTests(unittest.TestCase):
    def test_verifier_accepts_only_the_configured_owner_and_auth0_claims(self):
        now = NOW + timedelta(minutes=5)
        verifier = Auth0JwtVerifier(
            "https://dev.example.test/", CANONICAL_RESOURCE_URI,
            "https://dev.example.test/.well-known/jwks.json", "auth0|owner",
            _decode=lambda *_args, **_kwargs: {
                "sub": "auth0|owner", "scope": SCOPE, "exp": now.timestamp(),
            },
            _signing_key=lambda _token: object(),
        )
        context = verifier("synthetic.jwt.value")
        self.assertEqual(context.subject, CEO_SUBJECT)
        self.assertEqual(context.audience, CANONICAL_RESOURCE_URI)
        self.assertEqual(context.scopes, frozenset({SCOPE}))

    def test_verifier_rejects_blank_or_wrong_owner_before_fixture_load(self):
        verifier = Auth0JwtVerifier(
            "https://dev.example.test/", CANONICAL_RESOURCE_URI,
            "https://dev.example.test/.well-known/jwks.json", "",
            _decode=lambda *_args, **_kwargs: {}, _signing_key=lambda _token: object(),
        )
        with self.assertRaises(ValueError):
            verifier("synthetic.jwt.value")

    def test_verifier_reads_owner_only_from_the_credential_mount(self):
        environment = {
            ISSUER_ENV: "https://dev.example.test/",
            JWKS_ENV: "https://dev.example.test/.well-known/jwks.json",
            OWNER_SUBJECT_FILE_ENV: "/run/secrets/mcp_owner_subject",
            "MCP_OWNER_SUBJECT": "must-not-be-read",
        }
        with patch.dict(os.environ, environment, clear=True), patch(
            "operations_hub.mission_control_cto_auth0_verifier.Path.read_text",
            return_value="auth0|owner\n",
        ) as read_credential:
            verifier = verifier_from_environment(CANONICAL_RESOURCE_URI)
        self.assertEqual(verifier.owner_subject, "auth0|owner")
        read_credential.assert_called_once_with(encoding="utf-8")

    def test_verifier_fails_closed_without_a_credential_file_path(self):
        environment = {
            ISSUER_ENV: "https://dev.example.test/",
            JWKS_ENV: "https://dev.example.test/.well-known/jwks.json",
            "MCP_OWNER_SUBJECT": "must-not-be-read",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ValueError, "credential_path_required"):
                verifier_from_environment(CANONICAL_RESOURCE_URI)


if __name__ == "__main__":
    unittest.main()
