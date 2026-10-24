"""Read-only MCP contract for the separately deployed MC-021 live-status probe."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from .mission_control_cto_tool import CEO_SUBJECT, SCOPE, ToolDenied, VerifiedContext
from .mission_control_live_status import LiveStatusError


# The live-status connector has its own Auth0 API.  Keep this identifier exact:
# Auth0 places it in the access-token aud claim, and ChatGPT sends it unchanged
# as the OAuth `resource` parameter.  Accepting the broader shared MCP audience
# would weaken the connector boundary and rejects valid dedicated API tokens.
CANONICAL_RESOURCE_URI = "https://miscon.phireij.cloud/mcp/live-status"
TOOL_NAME = "get_mission_control_live_status"
TOOL_DESCRIPTOR = {
    "name": TOOL_NAME,
    "description": "Read bounded Mission Control health facts from the approved live-source manifest.",
    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
}


class ScopeDenied(ToolDenied):
    """A verified credential lacks the one required read-only scope."""


def _https_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return (
        isinstance(value, str)
        and value == value.strip()
        and parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
    )


def _metadata_uri_for_resource(metadata_uri: str, resource_uri: str) -> bool:
    if not _https_url(metadata_uri):
        return False
    metadata, resource = urlsplit(metadata_uri), urlsplit(resource_uri)
    return (
        metadata.scheme == resource.scheme
        and metadata.netloc == resource.netloc
        and metadata.path.startswith("/.well-known/oauth-protected-resource/")
    )


@dataclass(frozen=True)
class LiveStatusMcpResource:
    resource_uri: str
    authorization_issuer: str
    protected_resource_metadata_uri: str

    def __post_init__(self) -> None:
        if (
            not _https_url(self.resource_uri)
            or not _https_url(self.authorization_issuer)
            or not _metadata_uri_for_resource(self.protected_resource_metadata_uri, self.resource_uri)
        ):
            raise ValueError("https_resource_and_issuer_required")

    def protected_resource_metadata(self) -> dict[str, Any]:
        return {
            "resource": self.resource_uri,
            "authorization_servers": [self.authorization_issuer],
            "scopes_supported": [SCOPE],
        }

    def list_tools(self) -> dict[str, Any]:
        return {"tools": [{
            **TOOL_DESCRIPTOR,
            "inputSchema": {**TOOL_DESCRIPTOR["inputSchema"]},
            "annotations": {**TOOL_DESCRIPTOR["annotations"]},
            "securitySchemes": [{"type": "oauth2", "scopes": [SCOPE]}],
        }]}

    def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
        credential: str | None,
        *,
        verifier: Callable[[str], VerifiedContext] | None,
        manifest_loader: Callable[[], dict[str, Any]],
        collector: Callable[[dict[str, Any]], dict[str, Any]],
        now: datetime,
    ) -> dict[str, Any]:
        if name != TOOL_NAME or not isinstance(arguments, dict) or arguments:
            return {"isError": True, "content": [{"type": "text", "text": "tool_denied"}]}
        try:
            _authorize(credential, verifier, self.resource_uri, now)
        except ScopeDenied:
            return _authentication_required(
                self.protected_resource_metadata_uri,
                error="insufficient_scope",
                description="Required read-only scope is missing",
            )
        except ToolDenied:
            return _authentication_required(self.protected_resource_metadata_uri)
        try:
            result = collector(manifest_loader())
        except (LiveStatusError, OSError, ValueError, TypeError):
            return {"isError": True, "content": [{"type": "text", "text": "live_status_unavailable"}]}
        return {
            "isError": False,
            "structuredContent": result,
            "content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}],
        }


def _authorize(
    credential: str | None, verifier: Callable[[str], VerifiedContext] | None,
    audience: str, now: datetime,
) -> None:
    if not credential or verifier is None or now.tzinfo is None or now.utcoffset() is None:
        raise ToolDenied("tool_denied")
    try:
        context = verifier(credential)
    except Exception as exc:
        raise ToolDenied("tool_denied") from exc
    expiry = getattr(context, "expires_at", None)
    if (
        not isinstance(context, VerifiedContext)
        or context.revoked
        or context.subject != CEO_SUBJECT
        or context.audience != audience
        or not isinstance(expiry, datetime)
        or expiry.tzinfo is None
        or expiry.utcoffset() is None
        or expiry <= now
    ):
        raise ToolDenied("tool_denied")
    if SCOPE not in context.scopes:
        raise ScopeDenied("scope_missing")


def _authentication_required(
    metadata_uri: str,
    *,
    error: str = "invalid_token",
    description: str = "Authentication required",
) -> dict[str, Any]:
    if error not in {"invalid_token", "insufficient_scope"}:
        raise ValueError("invalid_oauth_challenge_error")
    challenge = (
        f'Bearer resource_metadata="{metadata_uri}", scope="{SCOPE}", '
        f'error="{error}", error_description="{description}"'
    )
    return {
        "isError": True,
        "content": [{"type": "text", "text": "authentication_required"}],
        "_meta": {"mcp/www_authenticate": [challenge]},
    }
