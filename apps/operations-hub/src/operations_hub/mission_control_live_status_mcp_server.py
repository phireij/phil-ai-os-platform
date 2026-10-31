"""Loopback-only server for the separately authorized read-only live-status MCP tool."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .mission_control_cto_auth0_verifier import CredentialRejected, verifier_from_environment
from .mission_control_live_status import collect_live_status, load_manifest
from .mission_control_live_status_mcp import CANONICAL_RESOURCE_URI, LiveStatusMcpResource
from .mission_control_cto_tool import SCOPE, VerifiedContext


LOOPBACK_HOST = "127.0.0.1"
PUBLIC_CONTAINER_HOST = "0.0.0.0"
PORT = 8788
MAX_REQUEST_BYTES = 16 * 1024
METADATA_URI = "https://miscon.phireij.cloud/.well-known/oauth-protected-resource/mcp/live-status"
PROTECTED_RESOURCE_METADATA_PATHS = frozenset({
    "/.well-known/oauth-protected-resource/mcp/live-status",
    # tunnel-client derives this standard path from the loopback /mcp endpoint.
    # It remains an alias for discovery only; both paths advertise the dedicated
    # live-status Auth0 resource and the same bounded read scope.
    "/.well-known/oauth-protected-resource/mcp",
})
ISSUER_ENV = "MCP_AUTHORIZATION_ISSUER"
MANIFEST_PATH_ENV = "MCP_LIVE_STATUS_MANIFEST_PATH"
DEFAULT_MANIFEST_PATH = "/srv/mission-control/live-status-manifest.json"
SERVER_INFO = {
    "name": "phil-ai-os-mission-control-live-status",
    "version": "1.0.0",
}
LOGGER = logging.getLogger(__name__)
MCP_METHODS = frozenset({"initialize", "tools/list", "tools/call"})
VERIFICATION_OUTCOMES = frozenset({
    "token_missing",
    "owner_mapping_invalid",
    "owner_mismatch",
    "scope_missing",
    "token_expired",
    "audience_mismatch",
    "issuer_mismatch",
    "signature_invalid",
    "signature_unavailable",
    "required_claim_missing",
    "token_verification_failed",
    "token_accepted",
})


def _resource() -> LiveStatusMcpResource:
    return LiveStatusMcpResource(CANONICAL_RESOURCE_URI, os.environ.get(ISSUER_ENV, ""), METADATA_URI)


def _manifest_loader() -> dict[str, object]:
    return load_manifest(Path(os.environ.get(MANIFEST_PATH_ENV, DEFAULT_MANIFEST_PATH)))


def _verify_owner_credential(credential: str):
    return verifier_from_environment(CANONICAL_RESOURCE_URI)(credential)


def _verification_result(credential: str | None) -> tuple[VerifiedContext | None, str]:
    """Verify once and retain only a fixed outcome label for diagnostics."""

    if credential is None:
        return None, "token_missing"
    try:
        context = _verify_owner_credential(credential)
    except CredentialRejected as exc:
        return None, exc.category if exc.category in VERIFICATION_OUTCOMES else "token_verification_failed"
    except Exception:
        return None, "token_verification_failed"
    if SCOPE not in context.scopes:
        return context, "scope_missing"
    return context, "token_accepted"


def _bearer_credential(value: str | None) -> str | None:
    if not isinstance(value, str) or not value.startswith("Bearer "):
        return None
    token = value.removeprefix("Bearer ")
    return token if token and token == token.strip() and " " not in token else None


def _request_content_length(headers: object) -> int | None:
    """Return one canonical content length, or reject unsupported framing.

    This server does not decode transfer-encoded requests. Refusing them and
    requiring one decimal Content-Length prevents proxy/server framing
    disagreement before an OAuth-protected request is parsed.
    """

    get = getattr(headers, "get", None)
    get_all = getattr(headers, "get_all", None)
    if not callable(get) or not callable(get_all) or get("Transfer-Encoding") is not None:
        return None
    values = get_all("Content-Length", [])
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], str):
        return None
    value = values[0]
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)", value):
        return None
    return int(value)


def _json_request_content_type(headers: object) -> bool:
    """Accept exactly one JSON media type before parsing a public request."""

    get_all = getattr(headers, "get_all", None)
    if not callable(get_all):
        return False
    values = get_all("Content-Type", [])
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], str):
        return False
    media_type = values[0].split(";", 1)[0].strip().lower()
    return media_type == "application/json"


def _json_object_without_duplicate_keys(pairs: list[tuple[object, object]]) -> dict[object, object]:
    """Build a JSON object only when each key appears once."""

    result: dict[object, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _deny_json_constant(_value: str) -> object:
    """Reject non-standard numeric constants accepted by Python's decoder."""

    raise ValueError("non_standard_json_constant")


def _parse_json_rpc_request(payload: bytes) -> dict[str, object] | None:
    """Parse only the bounded JSON-RPC request shape the server supports."""

    try:
        request = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_json_object_without_duplicate_keys,
            parse_constant=_deny_json_constant,
        )
    except (UnicodeDecodeError, ValueError, TypeError, RecursionError):
        return None
    if (
        not isinstance(request, dict)
        or request.get("jsonrpc") != "2.0"
        or not isinstance(request.get("method"), str)
        or ("params" in request and not isinstance(request["params"], dict))
    ):
        return None
    if "id" in request:
        request_id = request["id"]
        if isinstance(request_id, bool) or not isinstance(request_id, (str, int, float, type(None))):
            return None
    return request


def protected_resource_metadata_for_path(path: str) -> dict[str, object] | None:
    """Serve the canonical metadata at both approved discovery paths."""

    if path not in PROTECTED_RESOURCE_METADATA_PATHS:
        return None
    return _resource().protected_resource_metadata()


def initialize_result() -> dict[str, object]:
    """Return the protocol-complete MCP initialization response."""

    return {
        "protocolVersion": "2025-03-26",
        "capabilities": {"tools": {}},
        "serverInfo": SERVER_INFO,
    }


def listen_host() -> str:
    """Return the explicitly approved listener shape for this deployment.

    The default preserves the private tunnel deployment.  The only public
    option is the all-interface container listener used behind Traefik; the
    Compose file never publishes a host port, so Traefik remains the sole
    HTTPS entry point.
    """

    configured = os.environ.get("MCP_LISTEN_HOST", LOOPBACK_HOST)
    if configured not in {LOOPBACK_HOST, PUBLIC_CONTAINER_HOST}:
        raise RuntimeError("mcp_listener_host_denied")
    return configured


def mcp_method_category(method: object) -> str:
    """Return a fixed, non-user-controlled method label for diagnostics."""

    return method if isinstance(method, str) and method in MCP_METHODS else "unsupported"


def mcp_tool_outcome(
    result: dict[str, object], *, credential_present: bool = False,
    verification_outcome: str | None = None,
) -> str:
    """Return a fixed result code without logging response or credential data."""

    if not result.get("isError"):
        return "tool_completed"
    content = result.get("content")
    if isinstance(content, list) and content and isinstance(content[0], dict):
        text = content[0].get("text")
        if text == "authentication_required":
            # The verifier emits only fixed category labels.  It never records
            # a header, token, claim value, subject, or verifier error detail.
            if verification_outcome in VERIFICATION_OUTCOMES:
                return verification_outcome
            return "token_rejected" if credential_present else "token_missing"
        if text in {"tool_denied", "live_status_unavailable"}:
            return text
    return "tool_error"


def log_mcp_outcome(method: object, outcome: str, http_status: int) -> None:
    """Emit only fixed diagnostic labels; never log request or response contents."""

    LOGGER.warning(
        "mcp_request method=%s outcome=%s http_status=%d",
        mcp_method_category(method), outcome, http_status,
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "PhilAiOsLiveStatusMcp/1"
    protocol_version = "HTTP/1.1"

    def _send(self, code: int, body: object, headers: dict[str, str] | None = None) -> None:
        payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send(200, {"status": "ok", "mode": "live_status_read_only", "authority_effect": "none", "live_data": "on_demand"})
        elif metadata := protected_resource_metadata_for_path(self.path):
            self._send(200, metadata)
        else:
            self._send(404, {"status": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/mcp":
            self._send(404, {"status": "not_found"})
            return
        if not _json_request_content_type(self.headers):
            self._send(415, {"error": "unsupported_media_type"})
            log_mcp_outcome(None, "unsupported_media_type", 415)
            return
        content_length = _request_content_length(self.headers)
        if content_length is None:
            self._send(400, {"error": "invalid_request"})
            log_mcp_outcome(None, "invalid_request", 400)
            return
        if content_length > MAX_REQUEST_BYTES:
            self._send(413, {"error": "request_too_large"})
            log_mcp_outcome(None, "request_too_large", 413)
            return
        request = _parse_json_rpc_request(self.rfile.read(content_length))
        if request is None:
            self._send(400, {"error": "invalid_request"})
            log_mcp_outcome(None, "invalid_request", 400)
            return
        method, request_id = request["method"], request.get("id")
        resource = _resource()
        if method == "initialize":
            result = initialize_result()
            outcome = "initialized"
        elif method == "tools/list":
            result = resource.list_tools()
            outcome = "tools_listed"
        elif method == "tools/call":
            params = request.get("params", {})
            assert isinstance(params, dict)
            credential = _bearer_credential(self.headers.get("Authorization"))
            context, verification_outcome = _verification_result(credential)
            result = resource.call_tool(
                params.get("name"), params.get("arguments"), credential,
                verifier=(lambda _credential: context) if context is not None else None,
                manifest_loader=_manifest_loader,
                collector=collect_live_status, now=datetime.now(timezone.utc),
            )
            challenge = result.get("_meta", {}).get("mcp/www_authenticate", ())
            if result.get("isError") and challenge:
                self._send(401, {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32001, "message": "authentication_required"}}, headers={"WWW-Authenticate": challenge[0]})
                log_mcp_outcome(
                    method,
                    mcp_tool_outcome(
                        result, credential_present=credential is not None,
                        verification_outcome=verification_outcome,
                    ),
                    401,
                )
                return
            outcome = mcp_tool_outcome(result)
        else:
            self._send(200, {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "method_not_found"}})
            log_mcp_outcome(method, "method_not_found", 200)
            return
        self._send(200, {"jsonrpc": "2.0", "id": request_id, "result": result})
        log_mcp_outcome(method, outcome, 200)

    def do_PUT(self) -> None:  # noqa: N802
        self._send(405, {"status": "read_only"})

    do_PATCH = do_PUT  # noqa: N815
    do_DELETE = do_PUT  # noqa: N815

    def log_message(self, format: str, *args: object) -> None:
        pass


def main() -> None:
    _resource()
    host = listen_host()
    server = ThreadingHTTPServer((host, PORT), Handler)
    print(f"live_status_mcp_listening={host}:{PORT} authority_effect=none", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
