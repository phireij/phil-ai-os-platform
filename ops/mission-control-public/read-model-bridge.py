#!/usr/bin/env python3
"""Bearer-authenticated, read-only bridge to the host-local A7 read model."""

from __future__ import annotations

import hmac
import json
import os
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

HOST = os.getenv("MISSION_CONTROL_BRIDGE_HOST", "0.0.0.0")
PORT = int(os.getenv("MISSION_CONTROL_BRIDGE_PORT", "8091"))
CEO_TOKEN_FILE = os.getenv("MISSION_CONTROL_CEO_TOKEN_FILE", "/run/secrets/mission_control_ceo_token")
UPSTREAM = os.getenv("MISSION_CONTROL_READ_MODEL_URL", "http://127.0.0.1:4881/api/read-model")
MAX_UPSTREAM_RESPONSE_BYTES = 1024 * 1024
MAX_AGENTS = 32
MAX_HANDOFFS = 100
MAX_TEXT_CHARS = 200
PRESENCE_STATES = {"fresh", "stale", "offline", "unknown"}
READINESS_STATES = {"unassignable", "busy", "ready", "stale", "offline", "indeterminate"}
RFC3339_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


def _token() -> str:
    try:
        return Path(CEO_TOKEN_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _constant_time_text_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _json(value: dict) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def source_generated_at(source: dict) -> str | None:
    value = source.get("generated_at")
    if not isinstance(value, str) or not RFC3339_TIMESTAMP.fullmatch(value):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if parsed.tzinfo is not None else None


def _object(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _text(value: object, default: str = "unknown") -> str:
    if not isinstance(value, str) or not value:
        return default
    return value[:MAX_TEXT_CHARS]


def _bounded_text(value: object, maximum: int) -> str | None:
    return value if isinstance(value, str) and 0 < len(value) <= maximum else None


def _state(value: object, allowed: set[str]) -> str | None:
    return value if isinstance(value, str) and value in allowed else None


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 2_147_483_647 else None


def _flag(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _timestamp(value: object) -> str | None:
    if not isinstance(value, str) or not RFC3339_TIMESTAMP.fullmatch(value):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if parsed.tzinfo is not None else None


def _agent_projection(source: dict, snapshot_generated_at: str | None) -> tuple[dict, bool, bool]:
    multi_agent = _object(source.get("multi_agent"))
    raw_agents = multi_agent.get("agents")
    available = isinstance(raw_agents, list)
    if not available:
        raw_agents = []
    agents = []
    for agent in raw_agents[:MAX_AGENTS]:
        agent = _object(agent)
        registry = _object(agent.get("registry"))
        presence = _object(agent.get("presence"))
        workload = _object(agent.get("workload"))
        readiness = _object(agent.get("readiness"))
        readiness_state = readiness.get("state")
        readiness_reason = _bounded_text(readiness.get("reason"), 120)
        if readiness.get("grants_authority") is True:
            readiness_state = "indeterminate"
            readiness_reason = "authority_claim_rejected"
        if readiness_state == "ready":
            presence_time = _timestamp(presence.get("observed_at"))
            presence_precedes_snapshot = False
            if presence_time is not None and snapshot_generated_at is not None:
                presence_precedes_snapshot = datetime.fromisoformat(presence_time.replace("Z", "+00:00")) <= datetime.fromisoformat(snapshot_generated_at.replace("Z", "+00:00"))
            ready_evidence = (
                presence_precedes_snapshot
                and snapshot_generated_at is not None
                and agent.get("evidence_complete") is True
                and registry.get("enabled") is True
                and registry.get("assignable") is True
                and registry.get("evidence_complete") is True
                and presence.get("state") == "fresh"
                and _timestamp(presence.get("observed_at")) is not None
                and _count(presence.get("age_seconds")) is not None
                and _count(presence.get("age_seconds")) <= 120
                and presence.get("identity_verified") is True
                and presence.get("evidence_complete") is True
                and workload.get("evidence_complete") is True
                and _count(workload.get("active_task_count")) == 0
                and readiness.get("grants_authority") is False
            )
            if not ready_evidence:
                readiness_state = "indeterminate"
                readiness_reason = "evidence_incomplete_or_conflicting"
        agents.append({
            "agent_id": _bounded_text(agent.get("agent_id"), 80),
            "authority_ceiling": _bounded_text(agent.get("authority_ceiling"), 40),
            "evidence_complete": _flag(agent.get("evidence_complete")),
            "registry": {
                "enabled": _flag(registry.get("enabled")),
                "assignable": _flag(registry.get("assignable")),
                "evidence_complete": _flag(registry.get("evidence_complete")),
            },
            "presence": {
                "state": _state(presence.get("state"), PRESENCE_STATES),
                "identity_verified": _flag(presence.get("identity_verified")),
                "evidence_complete": _flag(presence.get("evidence_complete")),
                "observed_at": _timestamp(presence.get("observed_at")),
                "age_seconds": _count(presence.get("age_seconds")),
            },
            "workload": {
                "evidence_complete": _flag(workload.get("evidence_complete")),
                "active_task_count": _count(workload.get("active_task_count")),
            },
            "readiness": {
                "state": _state(readiness_state, READINESS_STATES),
                "reason": readiness_reason,
                "grants_authority": False,
            },
        })
    return {"agents": agents}, available, len(raw_agents) > MAX_AGENTS


def _runtime_projection(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    presence = _object(value.get("presence"))
    workload = _object(value.get("workload"))
    runtime = _object(value.get("runtime"))
    governance = _object(value.get("governance"))
    heartbeat = _object(presence.get("heartbeat"))
    running = runtime.get("running")
    return {
        "presence": {
            "logical_presence": _text(presence.get("logical_presence")),
            "heartbeat_age_seconds": _count(presence.get("heartbeat_age_seconds")),
            "observation_type": _text(heartbeat.get("observation_type"), "none"),
        },
        "workload": {
            "active_task_count": _count(workload.get("active_task_count")),
            "source": _text(workload.get("source"), "unavailable"),
        },
        "runtime": {
            "running": running if isinstance(running, bool) else None,
            "restart_count": _count(runtime.get("restart_count")),
        },
        "governance": {
            "presence_authority_effect": _text(governance.get("presence_authority_effect"), "none"),
        },
    }


def _readiness_projection(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    return {
        "agent_id": _text(value.get("agent_id")),
        "task_class_scope": _text(value.get("task_class_scope")),
        "readiness": _text(value.get("readiness"), "indeterminate"),
        "reason_code": _text(value.get("reason_code")),
        "authority_effect": _text(value.get("authority_effect"), "none"),
        "automatic_assignment": False,
        "automatic_retry": False,
        "automatic_reroute": False,
        "automatic_execution": False,
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def _open_local_read_model(request: Request):
    parsed = urlsplit(UPSTREAM)
    if (
        request.full_url != UPSTREAM
        or request.get_method() != "GET"
        or parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port != 4881
        or parsed.path != "/api/read-model"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("read_model_upstream_not_allowed")
    return build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=10)


class Handler(BaseHTTPRequestHandler):
    server_version = "PhilAIOSMissionControlReadModelBridge/0.1"

    def _send(self, status: int, body: dict) -> None:
        payload = _json(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path != "/api/agent-posture":
            self._send(404, {"status": "not_found"})
            return
        expected = _token()
        supplied = self.headers.get("Authorization", "")
        if not expected or not _constant_time_text_equal(supplied, "Bearer " + expected):
            self._send(401, {"status": "unauthorized"})
            return
        try:
            with _open_local_read_model(Request(UPSTREAM, headers={"Accept": "application/json"})) as response:
                raw = response.read(MAX_UPSTREAM_RESPONSE_BYTES + 1)
            if len(raw) > MAX_UPSTREAM_RESPONSE_BYTES:
                raise ValueError("read_model_too_large")
            source = json.loads(raw.decode("utf-8"))
            if not isinstance(source, dict):
                raise ValueError("read_model_not_object")
            generated_at = source_generated_at(source)
            multi_agent, agents_available, agents_truncated = _agent_projection(source, generated_at)
            raw_handoffs = source.get("handoffs")
            handoffs_available = isinstance(raw_handoffs, list)
            if not handoffs_available:
                raw_handoffs = []
            handoffs_truncated = len(raw_handoffs) > MAX_HANDOFFS
            self._send(200, {
                "contract_version": 2,
                "status": _text(source.get("status")),
                "source_generated_at": generated_at,
                "multi_agent": multi_agent,
                "agents_available": agents_available,
                "agents_truncated": agents_truncated,
                "agent_runtime": _runtime_projection(source.get("agent_runtime")),
                "worker_readiness": _readiness_projection(source.get("worker_readiness")),
                "handoffs": [{"record_present": True} for _ in raw_handoffs[:MAX_HANDOFFS]],
                "handoffs_available": handoffs_available,
                "handoffs_truncated": handoffs_truncated,
                "governance": {
                    key: _text(_object(source.get("governance")).get(key), "none")
                    for key in ("presence_authority_effect", "worker_readiness_authority_effect")
                },
                "authority_effect": "none",
            })
        except (OSError, ValueError, RecursionError, HTTPError, URLError):
            self._send(502, {"status": "read_model_unavailable"})

    def do_POST(self) -> None:
        self._send(405, {"status": "mutation_not_available"})

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST

    def log_message(self, _format: str, *_args) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
