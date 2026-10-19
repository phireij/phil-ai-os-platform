"""Transportless, offline MC-021 MCP-facing fixture contract.

This is not a network server or a JWT verifier. A future approved transport must
provide the canonical HTTPS resource URI, the protected-resource metadata URI,
and a trusted per-call verifier. There is deliberately no fixture default URI,
fixture loader, credential, or network access.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from urllib.parse import urlsplit

from .mission_control_cto_tool import (
    SCOPE, TOOL_DESCRIPTOR, TOOL_NAME, ToolDenied, VerifiedContext,
    invoke_fixture_tool,
)


CANONICAL_RESOURCE_URI = "https://miscon.phireij.cloud/mcp"


def _https_url(value: str) -> bool:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or any(ord(char) < 33 or char in {'"', "\\"} for char in value)
        or "#" in value
        or "?" in value
    ):
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


def _metadata_uri_for_resource(metadata_uri: str, resource_uri: str) -> bool:
    if not _https_url(metadata_uri):
        return False
    metadata = urlsplit(metadata_uri)
    resource = urlsplit(resource_uri)
    metadata_path = "/.well-known/oauth-protected-resource"
    return (
        metadata.scheme == resource.scheme
        and metadata.netloc == resource.netloc
        and (metadata.path == metadata_path or metadata.path.startswith(f"{metadata_path}/"))
    )


def _loopback_mcp_url(value: str) -> bool:
    if not isinstance(value, str) or value != value.strip():
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "http"
            and parsed.hostname == "127.0.0.1"
            and parsed.port is not None
            and 0 < parsed.port < 65536
            and parsed.path == "/mcp"
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


@dataclass(frozen=True)
class OfflineMcpFixtureResource:
    """Pure response builder; no listener, HTTP route, OAuth flow, or live source."""

    resource_uri: str
    authorization_issuer: str
    protected_resource_metadata_uri: str

    def __post_init__(self) -> None:
        if (
            not _https_url(self.resource_uri)
            or not _https_url(self.authorization_issuer)
            or not _metadata_uri_for_resource(
                self.protected_resource_metadata_uri, self.resource_uri
            )
        ):
            raise ValueError("https_resource_and_issuer_required")

    @property
    def metadata_uri(self) -> str:
        """Explicit metadata location; never infer a path from the resource URI."""

        return self.protected_resource_metadata_uri

    def protected_resource_metadata(self) -> dict[str, Any]:
        return {
            "resource": self.resource_uri,
            "authorization_servers": [self.authorization_issuer],
            "scopes_supported": [SCOPE],
        }

    def list_tools(self) -> dict[str, Any]:
        descriptor = {
            **TOOL_DESCRIPTOR,
            "inputSchema": {**TOOL_DESCRIPTOR["inputSchema"]},
            "annotations": {**TOOL_DESCRIPTOR["annotations"]},
            "securitySchemes": [{"type": "oauth2", "scopes": [SCOPE]}],
        }
        return {"tools": [descriptor]}

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        credential: str | None,
        *,
        verifier: Callable[[str], VerifiedContext] | None = None,
        fixture_loader: Callable[[], tuple[dict[str, Any], dict[str, Any] | None]] | None = None,
        now: datetime,
    ) -> dict[str, Any]:
        if name != TOOL_NAME or not isinstance(arguments, dict) or arguments:
            return {"isError": True, "content": [{"type": "text", "text": "tool_denied"}]}
        try:
            result = invoke_fixture_tool(
                name, arguments, credential, verifier=verifier,
                fixture_loader=fixture_loader, expected_audience=self.resource_uri,
                now=now,
            )
        except ToolDenied:
            challenge = (
                f'Bearer resource_metadata="{self.metadata_uri}", '
                'error="invalid_token", error_description="Authentication required"'
            )
            return {
                "isError": True,
                "content": [{"type": "text", "text": "authentication_required"}],
                "_meta": {"mcp/www_authenticate": [challenge]},
            }
        return {
            "isError": False,
            "structuredContent": result,
            "content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}],
        }


@dataclass(frozen=True)
class OfflineApprovedLoopbackMcpPlan:
    """Offline design contract for the owner-approved future Hostinger layout.

    This object does not start a server, read a secret, or configure a tunnel.
    It only pins the approved external resource identity to a private loopback
    target that a future separately approved tunnel-client may reach locally.
    """

    authorization_issuer: str
    protected_resource_metadata_uri: str
    loopback_mcp_uri: str

    def __post_init__(self) -> None:
        if not _https_url(self.authorization_issuer):
            raise ValueError("https_authorization_issuer_required")
        if not _metadata_uri_for_resource(
            self.protected_resource_metadata_uri, CANONICAL_RESOURCE_URI
        ):
            raise ValueError("canonical_protected_resource_metadata_uri_required")
        if not _loopback_mcp_url(self.loopback_mcp_uri):
            raise ValueError("loopback_mcp_uri_required")

    def resource_contract(self) -> OfflineMcpFixtureResource:
        return OfflineMcpFixtureResource(
            CANONICAL_RESOURCE_URI,
            self.authorization_issuer,
            self.protected_resource_metadata_uri,
        )

    def transport_boundary(self) -> dict[str, Any]:
        return {
            "canonical_resource_uri": CANONICAL_RESOURCE_URI,
            "loopback_mcp_uri": self.loopback_mcp_uri,
            "public_mcp_listener": False,
            "future_tunnel_client_colocated": True,
        }
