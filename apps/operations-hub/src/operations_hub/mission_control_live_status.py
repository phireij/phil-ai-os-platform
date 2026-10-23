"""Fail-closed collectors for the approved Mission Control live status sources.

The module permits only the two process-health resources named in the checked-in
manifest.  It never accepts a caller-supplied URL, sends credentials, follows a
redirect, persists a response, or makes a non-GET request.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


MANIFEST_SCHEMA = "phil-ai-os-mc021-live-status-manifest"
MANIFEST_VERSION = 1
MAX_RESPONSE_BYTES = 16 * 1024
MAX_TIMEOUT_SECONDS = 10
ALLOWED_SOURCES = {
    "mission-control-ui-health": "https://miscon.phireij.cloud/healthz",
    "mission-control-gateway-health": "https://miscon.phireij.cloud/api/healthz",
}


class LiveStatusError(ValueError):
    """A malformed manifest or disallowed live-status operation."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise LiveStatusError("redirect_denied")


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load and validate a manifest before any source request is made."""

    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LiveStatusError("manifest_unreadable") from exc
    if not isinstance(manifest, dict):
        raise LiveStatusError("manifest_object_required")
    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("version") != MANIFEST_VERSION:
        raise LiveStatusError("manifest_schema_required")
    if manifest.get("authority_effect") != "none" or manifest.get("mutation_authorized") is not False:
        raise LiveStatusError("read_only_authority_required")
    if manifest.get("response_persistence") is not False:
        raise LiveStatusError("response_persistence_denied")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise LiveStatusError("nonempty_sources_required")
    identifiers: set[str] = set()
    for source in sources:
        _validate_source(source, identifiers)
    return manifest


def _validate_source(source: Any, identifiers: set[str]) -> None:
    if not isinstance(source, dict):
        raise LiveStatusError("source_object_required")
    source_id = source.get("source_id")
    if not isinstance(source_id, str) or source_id in identifiers or source_id not in ALLOWED_SOURCES:
        raise LiveStatusError("source_id_not_allowlisted")
    identifiers.add(source_id)
    if source.get("url") != ALLOWED_SOURCES[source_id] or source.get("method") != "GET":
        raise LiveStatusError("source_url_or_method_denied")
    if source.get("authentication") != "none" or source.get("allow_redirects") is not False:
        raise LiveStatusError("source_auth_or_redirect_denied")
    if source.get("max_response_bytes") != MAX_RESPONSE_BYTES:
        raise LiveStatusError("response_bound_required")
    timeout = source.get("timeout_seconds")
    if not isinstance(timeout, int) or not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise LiveStatusError("timeout_bound_required")
    parsed = urlsplit(source["url"])
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise LiveStatusError("safe_https_url_required")


def collect_live_status(
    manifest: dict[str, Any], *, now: Callable[[], datetime] | None = None,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Collect bounded health facts only, returning no response bodies or headers."""

    # Revalidate even when the caller already used load_manifest().
    manifest = _validated_copy(manifest)
    observed_at = (now or _utc_now)().astimezone(timezone.utc).isoformat()
    open_request = opener or build_opener(_NoRedirect()).open
    observations = [_collect_one(source, open_request, observed_at) for source in manifest["sources"]]
    return {
        "schema": MANIFEST_SCHEMA,
        "version": MANIFEST_VERSION,
        "mode": "live_status_read_only",
        "authority_effect": "none",
        "mutation_authorized": False,
        "response_persistence": False,
        "observed_at": observed_at,
        "sources": observations,
    }


def _validated_copy(manifest: dict[str, Any]) -> dict[str, Any]:
    try:
        encoded = json.dumps(manifest, sort_keys=True)
        return load_manifest_from_object(json.loads(encoded))
    except (TypeError, json.JSONDecodeError) as exc:
        raise LiveStatusError("manifest_not_json_safe") from exc


def load_manifest_from_object(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise LiveStatusError("manifest_object_required")
    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("version") != MANIFEST_VERSION:
        raise LiveStatusError("manifest_schema_required")
    if manifest.get("authority_effect") != "none" or manifest.get("mutation_authorized") is not False:
        raise LiveStatusError("read_only_authority_required")
    if manifest.get("response_persistence") is not False:
        raise LiveStatusError("response_persistence_denied")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise LiveStatusError("nonempty_sources_required")
    identifiers: set[str] = set()
    for source in sources:
        _validate_source(source, identifiers)
    return manifest


def _collect_one(source: dict[str, Any], open_request: Callable[..., Any], observed_at: str) -> dict[str, Any]:
    request = Request(source["url"], method="GET", headers={"Accept": "application/json"})
    base = {"source_id": source["source_id"], "observed_at": observed_at, "method": "GET"}
    try:
        with open_request(request, timeout=source["timeout_seconds"]) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            body = response.read(MAX_RESPONSE_BYTES + 1)
            # The collector intentionally discards bodies.  A response exceeding
            # the declared limit cannot become a healthy observation.
            if len(body) > MAX_RESPONSE_BYTES:
                return {**base, "state": "unavailable", "http_status": None}
    except HTTPError as exc:
        return {**base, "state": "unhealthy", "http_status": exc.code}
    except (LiveStatusError, URLError, TimeoutError, OSError):
        return {**base, "state": "unavailable", "http_status": None}
    return {**base, "state": "healthy" if status == 200 else "unhealthy", "http_status": status}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
