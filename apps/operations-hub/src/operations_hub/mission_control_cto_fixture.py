"""Offline-only MC-021 CTO status projection.

This module has no I/O, HTTP handler, OAuth verifier, or provider integration. It
must not be wired to a tool/server until the separate auth and connection gates
are reviewed. Callers supply synthetic fixture dictionaries and a retrieval time.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any


PROJECT_ID = "phil-ai-os"
PROJECT_NAME = "Phil AI OS Platform"
SOURCE_ID = re.compile(r"^phil-ai-os\.[a-z0-9-]{1,64}$")
AGENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
FRESHNESS = {"fresh", "stale", "unknown"}
SOURCE_STATUS = {"unknown", "available", "not_available", "not_configured"}
POLICY_STATUS = {"approved", "proposed", "not_defined"}
PRESENCE_STATE = {"fresh", "stale", "offline", "unknown"}
READINESS_STATE = {"unassignable", "busy", "ready", "stale", "offline", "indeterminate"}


def _timestamp(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("invalid_timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("invalid_timestamp")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _optional_timestamp(value: Any) -> str | None:
    return None if value is None else _timestamp(value)


def _not_future(value: str | None, retrieved: str) -> str | None:
    if value is not None and value > retrieved:
        raise ValueError("future_observation")
    return value


def _enum(value: Any, allowed: set[str], error: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(error)
    return value


def _coverage(project: dict[str, Any], retrieved: str) -> list[dict[str, Any]]:
    rows = project.get("domain_status")
    if not isinstance(rows, list) or len(rows) > 12:
        raise ValueError("invalid_source_coverage")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid_source_coverage")
        source_id = row.get("source_id")
        if not isinstance(source_id, str) or not SOURCE_ID.fullmatch(source_id) or source_id in seen:
            raise ValueError("invalid_source_coverage")
        seen.add(source_id)
        policy = _enum(row.get("freshness_policy_status"), POLICY_STATUS, "invalid_source_coverage")
        freshness = _enum(row.get("freshness"), FRESHNESS, "invalid_source_coverage")
        if policy != "approved":
            freshness = "unknown"
        result.append(
            {
                "source_id": source_id,
                "source_status": _enum(row.get("status"), SOURCE_STATUS, "invalid_source_coverage"),
                "freshness": freshness,
                "freshness_policy_status": policy,
                "observed_at": _not_future(_optional_timestamp(row.get("observed_at")), retrieved),
            }
        )
    return result


def _posture(value: dict[str, Any] | None, retrieved: str) -> dict[str, Any]:
    unavailable = {"availability": "unavailable", "observed_at": None, "agents": []}
    if value is None:
        return unavailable
    try:
        if not isinstance(value, dict) or value.get("contract_version") != 2 or value.get("authority_effect") != "none":
            raise ValueError("invalid_posture")
        if value.get("agents_available") is not True or value.get("agents_truncated") is not False:
            raise ValueError("invalid_posture")
        observed_at = _not_future(_timestamp(value.get("source_generated_at")), retrieved)
        agents = value.get("multi_agent", {}).get("agents")
        if not isinstance(agents, list) or len(agents) > 32:
            raise ValueError("invalid_posture")
        projected = []
        seen: set[str] = set()
        for item in agents:
            agent_id = item.get("agent_id")
            if not isinstance(agent_id, str) or not AGENT_ID.fullmatch(agent_id) or agent_id in seen:
                raise ValueError("invalid_posture")
            seen.add(agent_id)
            ceiling = item.get("authority_ceiling")
            if not isinstance(ceiling, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", ceiling):
                raise ValueError("invalid_posture")
            projected.append(
                {
                    "agent_id": agent_id,
                    "presence_state": _enum(item.get("presence", {}).get("state"), PRESENCE_STATE, "invalid_posture"),
                    "readiness_state": _enum(item.get("readiness", {}).get("state"), READINESS_STATE, "invalid_posture"),
                    "authority_ceiling": ceiling,
                }
            )
        return {"availability": "available", "observed_at": observed_at, "agents": projected}
    except (AttributeError, TypeError, ValueError):
        return unavailable


def project_fixture_status(
    workspace_snapshot: dict[str, Any],
    agent_posture: dict[str, Any] | None,
    *,
    retrieved_at: str,
) -> dict[str, Any]:
    """Project synthetic inputs into the approved first-pilot field allowlist.

    Raises ValueError for malformed workspace input. A malformed optional bridge
    projection is explicitly unavailable; no partial agent data is returned.
    This is not an authorization boundary or a live source reader.
    """
    retrieved = _timestamp(retrieved_at)
    if not isinstance(workspace_snapshot, dict) or (
        workspace_snapshot.get("schema") != "phil-ai-os-mission-control-project-readiness"
        or workspace_snapshot.get("version") != 1
        or workspace_snapshot.get("status") != "read_only"
        or workspace_snapshot.get("authority_effect") != "none"
    ):
        raise ValueError("invalid_workspace_snapshot")
    projects = workspace_snapshot.get("projects")
    if not isinstance(projects, list) or len(projects) > 32:
        raise ValueError("invalid_workspace_snapshot")
    selected = [item for item in projects if isinstance(item, dict) and item.get("project_id") == PROJECT_ID]
    if len(selected) != 1:
        raise ValueError("invalid_project_selection")
    project = selected[0]
    if (
        project.get("mode") != "read_only"
        or project.get("mutation_authorized") is not False
        or project.get("production_cutover_authorized") is not False
        or project.get("customer_data_exposed") is not False
    ):
        raise ValueError("invalid_project_boundary")
    return {
        "project_id": PROJECT_ID,
        "project_name": PROJECT_NAME,
        "projection_kind": "workspace_snapshot",
        "source_observed_at": _not_future(_timestamp(workspace_snapshot.get("observed_at")), retrieved),
        "retrieved_at": retrieved,
        "source_revision": None,
        "overall_status": "unknown",
        "freshness": "unknown",
        "source_coverage": _coverage(project, retrieved),
        "agent_posture": _posture(agent_posture, retrieved),
        "authority_effect": "none",
    }
