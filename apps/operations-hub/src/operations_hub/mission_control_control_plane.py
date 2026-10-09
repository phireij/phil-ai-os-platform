"""Authenticated Mission Control adapter for the governed Control API.

The adapter intentionally keeps reads available while requiring an explicit
``allow_mutation`` opt-in for task planning and assignment. It does not call
providers, execute tasks, send channel replies, or grant authority.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class MissionControlControlPlaneError(RuntimeError):
    """Raised when the governed Control API cannot satisfy an adapter call."""


@dataclass(frozen=True)
class MissionControlControlPlane:
    base_url: str = os.getenv("PHIL_AI_OS_CONTROL_API_URL", "http://phil-ai-os-core-control-api-1:4870")
    token_file: str = os.getenv(
        "PHIL_AI_OS_CONTROL_API_TOKEN_FILE",
        "/run/philaios/hermes_control_api_token",
    )
    timeout_seconds: float = 10.0

    def _token(self) -> str:
        try:
            with open(self.token_file, "r", encoding="utf-8") as handle:
                token = handle.read().strip()
        except OSError as exc:
            raise MissionControlControlPlaneError("control_api_token_unavailable") from exc
        if not token:
            raise MissionControlControlPlaneError("control_api_token_empty")
        return token

    def _call(self, path: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None
        headers = {"Authorization": "Bearer " + self._token()}
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url.rstrip("/") + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except (OSError, urllib.error.HTTPError) as exc:
            raise MissionControlControlPlaneError(f"control_api_request_failed:{path}") from exc
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise MissionControlControlPlaneError("control_api_invalid_json") from exc
        if not isinstance(parsed, dict):
            raise MissionControlControlPlaneError("control_api_response_not_object")
        return parsed

    def snapshot(self) -> dict[str, Any]:
        return self._call("/v1/mission-control/snapshot")

    def recent_approvals(self) -> dict[str, Any]:
        return self._call("/v1/approvals/recent")

    def recent_executions(self) -> dict[str, Any]:
        return self._call("/v1/execution/recent")

    def agent_posture(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        return {
            "status": snapshot.get("status", "unknown"),
            "multi_agent": snapshot.get("multi_agent") or snapshot.get("agent_posture") or {},
            "agent_runtime": snapshot.get("agent_runtime"),
            "worker_readiness": snapshot.get("worker_readiness"),
            "handoffs": snapshot.get("handoffs", []),
            "governance": snapshot.get("governance", {}),
            "authority_effect": "none",
        }

    def request_ceo_decision(self, task_text: str, conversation_id: str) -> dict[str, Any]:
        if not task_text.strip() or not conversation_id.strip():
            raise MissionControlControlPlaneError("task_text_and_conversation_id_required")
        return self._call(
            "/v1/approvals/request",
            method="POST",
            payload={
                "task_text": task_text.strip(),
                "source": "mission-control",
                "requester": "mission-control",
                "requested_by": "ceo",
                "conversation_id": conversation_id.strip(),
            },
        )

    def assign_task(self, task_id: str, agent_id: str, *, allow_mutation: bool = False) -> dict[str, Any]:
        self._require_mutation_opt_in(allow_mutation)
        return self._call(
            "/v1/tasks/assign",
            method="POST",
            payload={"task_id": task_id, "agent_id": agent_id, "requested_by": "chief-of-staff"},
        )

    def plan_task(self, task_id: str, *, allow_mutation: bool = False) -> dict[str, Any]:
        self._require_mutation_opt_in(allow_mutation)
        return self._call(
            "/v1/tasks/plan",
            method="POST",
            payload={"task_id": task_id, "plan_kind": "bounded", "requested_by": "chief-of-staff"},
        )

    @staticmethod
    def _require_mutation_opt_in(allow_mutation: bool) -> None:
        if allow_mutation is not True:
            raise MissionControlControlPlaneError("mutation_requires_explicit_authorization")

