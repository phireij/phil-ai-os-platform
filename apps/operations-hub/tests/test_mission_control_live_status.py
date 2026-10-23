import json
import os
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
from operations_hub.mission_control_live_status_mcp import (  # noqa: E402
    TOOL_NAME,
    LiveStatusMcpResource,
)
from operations_hub.mission_control_live_status_mcp_server import (  # noqa: E402
    PROTECTED_RESOURCE_METADATA_PATHS,
    SERVER_INFO,
    initialize_result,
    mcp_method_category,
    mcp_tool_outcome,
    protected_resource_metadata_for_path,
)


MANIFEST = ROOT.parents[1] / "ops" / "mission-control-identity" / "mc021-live-status-manifest.v1.json"
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

    def test_standard_mcp_metadata_path_describes_only_live_status_resource(self):
        self.assertIn("/.well-known/oauth-protected-resource/mcp", PROTECTED_RESOURCE_METADATA_PATHS)
        with patch.dict(
            os.environ,
            {"MCP_AUTHORIZATION_ISSUER": "https://issuer.example.test/"},
        ):
            metadata = protected_resource_metadata_for_path(
                "/.well-known/oauth-protected-resource/mcp"
            )
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["resource"], "https://miscon.phireij.cloud/mcp/live-status")
        self.assertEqual(metadata["scopes_supported"], [SCOPE])
        self.assertIsNone(protected_resource_metadata_for_path("/.well-known/oauth-protected-resource"))

    def test_initialize_response_contains_required_server_info(self):
        result = initialize_result()
        self.assertEqual(result["protocolVersion"], "2025-03-26")
        self.assertEqual(result["capabilities"], {"tools": {}})
        self.assertEqual(result["serverInfo"], SERVER_INFO)
        self.assertEqual(SERVER_INFO["name"], "phil-ai-os-mission-control-live-status")
        self.assertEqual(SERVER_INFO["version"], "1.0.0")

    def test_diagnostics_redact_untrusted_methods_and_tool_contents(self):
        self.assertEqual(mcp_method_category("tools/call"), "tools/call")
        self.assertEqual(mcp_method_category("arbitrary caller text"), "unsupported")
        self.assertEqual(mcp_tool_outcome({"isError": False, "structuredContent": {"sensitive": "discarded"}}), "tool_completed")
        self.assertEqual(
            mcp_tool_outcome({"isError": True, "content": [{"type": "text", "text": "authentication_required"}]}),
            "authentication_required",
        )
        self.assertEqual(
            mcp_tool_outcome({"isError": True, "content": [{"type": "text", "text": "untrusted error text"}]}),
            "tool_error",
        )


if __name__ == "__main__":
    unittest.main()
