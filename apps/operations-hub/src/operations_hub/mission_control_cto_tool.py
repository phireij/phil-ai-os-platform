"""Offline MC-021 tool contract; not an MCP server or OAuth implementation.

The verifier and fixture loader are injected for tests. No default verifier exists:
without a separately reviewed identity integration every invocation fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping, Any

from .mission_control_cto_fixture import project_fixture_status


TOOL_NAME = "get_phil_ai_os_status"
RESOURCE = "mission-control-cto-read"
SCOPE = "mission_control:cto_read"
CEO_SUBJECT = "phil-ai-os-ceo"  # Synthetic test subject; not a live identity mapping.
TOOL_DESCRIPTOR = {
    "name": TOOL_NAME,
    "description": "Read the fixed Phil AI OS fixture status; no authority or live data.",
    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
}


@dataclass(frozen=True)
class VerifiedContext:
    """Synthetic result of a trusted verifier, never parsed from a caller's claims."""

    subject: str
    audience: str
    scopes: frozenset[str]
    expires_at: datetime
    revoked: bool = False


class ToolDenied(Exception):
    """Intentionally content-free denial for offline boundary tests."""


def invoke_fixture_tool(
    name: str,
    arguments: Mapping[str, Any],
    credential: str | None,
    *,
    verifier: Callable[[str], VerifiedContext] | None = None,
    fixture_loader: Callable[[], tuple[dict[str, Any], dict[str, Any] | None]] | None = None,
    now: datetime,
) -> dict[str, Any]:
    """Authorize first, then project synthetic fixtures. Never reads a live source."""

    if name != TOOL_NAME or not isinstance(arguments, dict) or arguments or not credential or verifier is None:
        raise ToolDenied("tool_denied")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ToolDenied("tool_denied")
    try:
        context = verifier(credential)
    except Exception as exc:
        raise ToolDenied("tool_denied") from exc
    if not isinstance(context, VerifiedContext):
        raise ToolDenied("tool_denied")
    expiry = context.expires_at
    if (
        context.revoked
        or context.subject != CEO_SUBJECT
        or context.audience != RESOURCE
        or SCOPE not in context.scopes
        or not isinstance(expiry, datetime)
        or expiry.tzinfo is None
        or expiry.utcoffset() is None
        or expiry <= now
    ):
        raise ToolDenied("tool_denied")
    if fixture_loader is None:
        raise ToolDenied("tool_denied")
    workspace, posture = fixture_loader()
    return project_fixture_status(workspace, posture, retrieved_at=now.astimezone(timezone.utc).isoformat())
