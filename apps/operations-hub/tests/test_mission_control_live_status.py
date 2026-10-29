import json
import os
import re
import sys
import unittest
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub.mission_control_live_status import (  # noqa: E402
    ALLOWED_SOURCES,
    LiveStatusError,
    collect_live_status,
    load_manifest,
)
from operations_hub.mission_control_cto_tool import CEO_SUBJECT, SCOPE, VerifiedContext  # noqa: E402
from operations_hub.mission_control_cto_auth0_verifier import CredentialRejected  # noqa: E402
from operations_hub.mission_control_live_status_mcp import (  # noqa: E402
    CANONICAL_RESOURCE_URI,
    TOOL_NAME,
    LiveStatusMcpResource,
)
from operations_hub.mission_control_live_status_mcp_server import (  # noqa: E402
    LOOPBACK_HOST,
    PUBLIC_CONTAINER_HOST,
    PROTECTED_RESOURCE_METADATA_PATHS,
    SERVER_INFO,
    _verification_result,
    initialize_result,
    listen_host,
    mcp_method_category,
    mcp_tool_outcome,
    protected_resource_metadata_for_path,
)


MANIFEST = ROOT.parents[1] / "ops" / "mission-control-identity" / "mc021-live-status-manifest.v1.json"
BASE_COMPOSE = ROOT.parents[1] / "ops" / "mission-control-identity" / "compose.mcp-live-status.nonprod.yml"
TUNNEL_COMPOSE = ROOT.parents[1] / "ops" / "mission-control-identity" / "compose.mcp-live-status.tunnel.nonprod.yml"
SERVER_DOCKERFILE = ROOT.parents[1] / "Dockerfile.mission-control-cto-mcp-live-status"
TUNNEL_DOCKERFILE = ROOT.parents[1] / "Dockerfile.mission-control-cto-mcp-live-status-tunnel"
TUNNEL_ENTRYPOINT = ROOT.parents[1] / "ops" / "mission-control-identity" / "mc021-live-status-tunnel-entrypoint.sh"
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


class _Response(BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class LiveStatusTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest(MANIFEST)

    def test_manifest_is_explicitly_read_only_and_allowlisted(self):
        self.assertFalse(self.manifest["mutation_authorized"])
        self.assertFalse(self.manifest["response_persistence"])
        self.assertEqual({source["source_id"] for source in self.manifest["sources"]}, set(ALLOWED_SOURCES))
        self.assertTrue(all(source["method"] == "GET" for source in self.manifest["sources"]))
        self.assertTrue(all(source["authentication"] == "none" for source in self.manifest["sources"]))

    def test_rejects_caller_added_url_or_authentication(self):
        unsafe = json.loads(json.dumps(self.manifest))
        unsafe["sources"][0]["url"] = "https://example.invalid/status"
        with self.assertRaisesRegex(LiveStatusError, "source_url_or_method_denied"):
            collect_live_status(unsafe)
        unsafe = json.loads(json.dumps(self.manifest))
        unsafe["sources"][0]["authentication"] = "bearer"
        with self.assertRaisesRegex(LiveStatusError, "source_auth_or_redirect_denied"):
            collect_live_status(unsafe)

    def test_records_bounded_metadata_not_response_content(self):
        opener = Mock(return_value=_Response(b'{"status":"ok","secret":"discarded"}'))
        result = collect_live_status(self.manifest, now=lambda: NOW, opener=opener)
        self.assertEqual(result["authority_effect"], "none")
        self.assertFalse(result["mutation_authorized"])
        self.assertNotIn("secret", json.dumps(result))
        self.assertEqual([item["state"] for item in result["sources"]], ["healthy", "healthy"])
        requests = [call.args[0] for call in opener.call_args_list]
        self.assertEqual([request.method for request in requests], ["GET", "GET"])
        self.assertEqual([request.full_url for request in requests], list(ALLOWED_SOURCES.values()))

    def test_unavailable_source_remains_non_authorizing(self):
        result = collect_live_status(self.manifest, now=lambda: NOW, opener=Mock(side_effect=OSError("offline")))
        self.assertEqual([item["state"] for item in result["sources"]], ["unavailable", "unavailable"])
        self.assertTrue(all(item["http_status"] is None for item in result["sources"]))

    def test_mcp_tool_loads_manifest_only_after_owner_authentication(self):
        resource = LiveStatusMcpResource(
            "https://mcp.example.test/live-status",
            "https://issuer.example.test/",
            "https://mcp.example.test/.well-known/oauth-protected-resource/live-status",
        )
        load_manifest_mock = Mock(return_value=self.manifest)
        collector = Mock(return_value={"authority_effect": "none"})
        denied = resource.call_tool(
            TOOL_NAME, {}, None, verifier=None, manifest_loader=load_manifest_mock,
            collector=collector, now=NOW,
        )
        self.assertTrue(denied["isError"])
        load_manifest_mock.assert_not_called()
        authorized = resource.call_tool(
            TOOL_NAME, {}, "token",
            verifier=lambda _: VerifiedContext(
                subject=CEO_SUBJECT, audience="https://mcp.example.test/live-status",
                scopes=frozenset({SCOPE}), expires_at=NOW.replace(year=2027),
            ),
            manifest_loader=load_manifest_mock, collector=collector, now=NOW,
        )
        self.assertFalse(authorized["isError"])
        self.assertEqual(authorized["structuredContent"], {"authority_effect": "none"})
        load_manifest_mock.assert_called_once_with()
        collector.assert_called_once_with(self.manifest)

    def test_mcp_tool_uses_scope_upgrade_challenge_for_verified_token_without_scope(self):
        resource = LiveStatusMcpResource(
            "https://mcp.example.test/live-status",
            "https://issuer.example.test/",
            "https://mcp.example.test/.well-known/oauth-protected-resource/live-status",
        )
        denied = resource.call_tool(
            TOOL_NAME,
            {},
            "token",
            verifier=lambda _: VerifiedContext(
                subject=CEO_SUBJECT,
                audience="https://mcp.example.test/live-status",
                scopes=frozenset(),
                expires_at=NOW.replace(year=2027),
            ),
            manifest_loader=Mock(),
            collector=Mock(),
            now=NOW,
        )
        challenge = denied["_meta"]["mcp/www_authenticate"][0]
        self.assertIn('scope="mission_control:cto_read"', challenge)
        self.assertIn('error="insufficient_scope"', challenge)
        self.assertNotIn('error="invalid_token"', challenge)

    def test_metadata_paths_use_the_dedicated_live_status_auth0_resource(self):
        self.assertIn("/.well-known/oauth-protected-resource/mcp", PROTECTED_RESOURCE_METADATA_PATHS)
        with patch.dict(
            os.environ,
            {"MCP_AUTHORIZATION_ISSUER": "https://issuer.example.test/"},
        ):
            metadata = [
                protected_resource_metadata_for_path(path)
                for path in PROTECTED_RESOURCE_METADATA_PATHS
            ]
        self.assertTrue(all(item is not None for item in metadata))
        self.assertTrue(all(item["resource"] == CANONICAL_RESOURCE_URI for item in metadata))
        self.assertTrue(all(item["scopes_supported"] == [SCOPE] for item in metadata))
        self.assertIsNone(protected_resource_metadata_for_path("/.well-known/oauth-protected-resource"))

    def test_initialize_response_contains_required_server_info(self):
        result = initialize_result()
        self.assertEqual(result["protocolVersion"], "2025-03-26")
        self.assertEqual(result["capabilities"], {"tools": {}})
        self.assertEqual(result["serverInfo"], SERVER_INFO)
        self.assertEqual(SERVER_INFO["name"], "phil-ai-os-mission-control-live-status")
        self.assertEqual(SERVER_INFO["version"], "1.0.0")

    def test_listener_host_is_closed_to_private_or_traefik_container_shapes(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(listen_host(), LOOPBACK_HOST)
        with patch.dict(os.environ, {"MCP_LISTEN_HOST": PUBLIC_CONTAINER_HOST}, clear=True):
            self.assertEqual(listen_host(), PUBLIC_CONTAINER_HOST)
        with patch.dict(os.environ, {"MCP_LISTEN_HOST": "192.0.2.99"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "mcp_listener_host_denied"):
                listen_host()

    def test_compose_contract_allows_only_two_oauth_routes_without_host_exposure(self):
        compose = BASE_COMPOSE.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"^\s*ports\s*:", compose, flags=re.MULTILINE))
        self.assertIn("read_only: true", compose)
        self.assertIn("cap_drop:\n      - ALL", compose)
        self.assertIn("no-new-privileges:true", compose)
        self.assertIn("network_mode: bridge", compose)
        self.assertIn("MCP_LISTEN_HOST: 0.0.0.0", compose)
        self.assertNotIn("privileged:", compose)
        self.assertNotIn("cap_add:", compose)
        self.assertIn("source: /etc/phil-ai-os/secrets/mc021-owner-subject", compose)
        self.assertIn("target: /run/secrets/mc021_owner_subject", compose)
        self.assertIn("read_only: true", compose)

        router_rules = dict(re.findall(
            r'^\s+traefik\.http\.routers\.([^.]+)\.rule: "([^"]+)"$',
            compose,
            flags=re.MULTILINE,
        ))
        self.assertEqual(router_rules, {
            "mcp-live-status": "Host(`miscon.phireij.cloud`) && Path(`/mcp/live-status`)",
            "mcp-live-status-metadata": (
                "Host(`miscon.phireij.cloud`) && "
                "Path(`/.well-known/oauth-protected-resource/mcp/live-status`)"
            ),
        })

    def test_tunnel_overlay_cannot_add_an_ingress_route_or_embed_runtime_values(self):
        overlay = TUNNEL_COMPOSE.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"^\s*ports\s*:", overlay, flags=re.MULTILINE))
        self.assertIsNone(re.search(r"^\s+traefik\.http\.routers\..*\.rule:", overlay, flags=re.MULTILINE))
        self.assertNotIn("privileged:", overlay)
        self.assertNotIn("cap_add:", overlay)
        self.assertIn(
            "CONTROL_PLANE_API_KEY: ${CONTROL_PLANE_API_KEY:?root-owned VPS runtime key is required}",
            overlay,
        )
        self.assertIn(
            "CONTROL_PLANE_TUNNEL_ID: ${CONTROL_PLANE_TUNNEL_ID:?root-owned VPS tunnel identity is required}",
            overlay,
        )

    def test_container_images_are_pinned_nonroot_and_exclude_runtime_values(self):
        server_image = SERVER_DOCKERFILE.read_text(encoding="utf-8")
        tunnel_image = TUNNEL_DOCKERFILE.read_text(encoding="utf-8")
        for image in (server_image, tunnel_image):
            self.assertIsNotNone(re.search(
                r"^FROM docker\.io/library/python@sha256:[0-9a-f]{64}$",
                image,
                flags=re.MULTILINE,
            ))
            self.assertIn("USER app", image)
            self.assertNotIn("CONTROL_PLANE_API_KEY=", image)
            self.assertNotIn("CONTROL_PLANE_TUNNEL_ID=", image)
            self.assertNotIn("/etc/phil-ai-os/secrets/", image)
        self.assertIn("sha256sum -c -", tunnel_image)
        self.assertIn("curl --fail --location --proto '=https' --tlsv1.2", tunnel_image)

    def test_tunnel_entrypoint_uses_only_loopback_mcp_and_health_endpoints(self):
        entrypoint = TUNNEL_ENTRYPOINT.read_text(encoding="utf-8")
        self.assertIn("TUNNEL_CLIENT_PROFILE_DIR", entrypoint)
        self.assertIn("CONTROL_PLANE_TUNNEL_ID", entrypoint)
        self.assertIn('--mcp-server-url "http://127.0.0.1:8788/mcp"', entrypoint)
        self.assertIn('--health-listen-addr "127.0.0.1:18081"', entrypoint)
        self.assertNotIn("http://miscon.phireij.cloud", entrypoint)
        self.assertNotIn("https://miscon.phireij.cloud", entrypoint)
        self.assertNotIn("echo $CONTROL_PLANE_", entrypoint)

    def test_diagnostics_redact_untrusted_methods_and_tool_contents(self):
        self.assertEqual(mcp_method_category("tools/call"), "tools/call")
        self.assertEqual(mcp_method_category("arbitrary caller text"), "unsupported")
        self.assertEqual(mcp_tool_outcome({"isError": False, "structuredContent": {"sensitive": "discarded"}}), "tool_completed")
        authentication_required = {"isError": True, "content": [{"type": "text", "text": "authentication_required"}]}
        self.assertEqual(mcp_tool_outcome(authentication_required), "token_missing")
        self.assertEqual(mcp_tool_outcome(authentication_required, credential_present=True), "token_rejected")
        self.assertEqual(
            mcp_tool_outcome(authentication_required, verification_outcome="audience_mismatch"),
            "audience_mismatch",
        )
        self.assertEqual(
            mcp_tool_outcome({"isError": True, "content": [{"type": "text", "text": "untrusted error text"}]}),
            "tool_error",
        )

    @patch("operations_hub.mission_control_live_status_mcp_server._verify_owner_credential")
    def test_diagnostics_classify_owner_scope_and_generic_verification_without_credentials(self, verifier):
        verifier.side_effect = CredentialRejected("owner_mismatch")
        self.assertEqual(_verification_result("synthetic.jwt.value"), (None, "owner_mismatch"))
        verifier.side_effect = ValueError("opaque verifier detail")
        self.assertEqual(_verification_result("synthetic.jwt.value"), (None, "token_verification_failed"))
        verifier.side_effect = None
        verifier.return_value = VerifiedContext(
            subject=CEO_SUBJECT, audience="https://mcp.example.test", scopes=frozenset(),
            expires_at=NOW.replace(year=2027),
        )
        _context, outcome = _verification_result("synthetic.jwt.value")
        self.assertEqual(outcome, "scope_missing")
        self.assertEqual(_verification_result(None), (None, "token_missing"))


if __name__ == "__main__":
    unittest.main()
