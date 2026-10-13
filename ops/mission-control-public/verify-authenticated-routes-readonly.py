#!/usr/bin/env python3
"""Verify bounded CEO reads inside the isolated bridge container; emit no payloads."""

from __future__ import annotations

import json
import ssl
from pathlib import Path
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener


BASE = "https://miscon.phireij.cloud"
TOKEN_FILE = Path("/run/secrets/mission_control_ceo_token")
MAX_RESPONSE_BYTES = 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def main() -> None:
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("empty_ceo_token")
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), NoRedirect())

    def read(path: str) -> dict:
        request = Request(BASE + path, headers={"Authorization": "Bearer " + token, "Accept": "application/json"}, method="GET")
        with opener.open(request, timeout=15) as response:
            if response.status != 200 or response.headers.get_content_type() != "application/json":
                raise ValueError("unexpected_authenticated_response")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("authenticated_response_too_large")
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("authenticated_response_not_object")
        return value

    snapshot = read("/api/snapshot")
    posture = read("/api/agent-posture")
    agents = posture.get("multi_agent", {}).get("agents")
    handoffs = posture.get("handoffs")
    if not isinstance(snapshot.get("status"), str):
        raise ValueError("snapshot_status_missing")
    if posture.get("contract_version") != 2 or posture.get("authority_effect") != "none":
        raise ValueError("posture_contract_mismatch")
    if not isinstance(agents, list) or len(agents) > 32 or not isinstance(handoffs, list) or len(handoffs) > 100:
        raise ValueError("posture_lists_invalid")
    if any(not isinstance(agent, dict) or agent.get("readiness", {}).get("grants_authority") is not False for agent in agents):
        raise ValueError("posture_authority_claim")
    if any(record != {"record_present": True} for record in handoffs):
        raise ValueError("handoff_payload_exposed")
    print("authenticated_snapshot=200 authenticated_posture_v2=200 authority_effect=none")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"authenticated_route_verification_failed={type(error).__name__}")
        raise SystemExit(1)
