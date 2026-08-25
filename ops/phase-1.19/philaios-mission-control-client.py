#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request

TOKEN_FILE = os.getenv(
    "PHIL_AI_OS_CONTROL_API_TOKEN_FILE",
    "/run/philaios/hermes_control_api_token",
)
BASE_URL = os.getenv(
    "PHIL_AI_OS_CONTROL_API_URL",
    "http://phil-ai-os-core-control-api-1:4870",
)
READ_COMMANDS = {
    "snapshot": "/v1/mission-control/snapshot",
    "approvals": "/v1/approvals/recent",
    "executions": "/v1/execution/recent",
}


def read_token():
    with open(TOKEN_FILE, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def call(path, method="GET", payload=None):
    data = None
    headers = {"Authorization": "Bearer " + read_token()}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read().decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body, "http_status": response.status}


def usage():
    print(
        "usage: philaios-mission-control "
        "<snapshot|approvals|executions|request> [task text]",
        file=sys.stderr,
    )


def main():
    if len(sys.argv) < 2:
        usage()
        return 2

    command = sys.argv[1]

    if command in READ_COMMANDS and len(sys.argv) == 2:
        print(json.dumps(call(READ_COMMANDS[command]), indent=2, sort_keys=True))
        return 0

    if command == "request" and len(sys.argv) >= 3:
        task_text = " ".join(sys.argv[2:]).strip()
        if not task_text:
            print("task text is required", file=sys.stderr)
            return 2
        payload = {
            "task_text": task_text,
            "source": "hermes",
            "requester": "hermes-mission-control-client",
            "requested_by": "hermes",
        }
        result = call(
            "/v1/approvals/request",
            method="POST",
            payload=payload,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    usage()
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        print(
            exc.read().decode("utf-8", errors="replace"),
            file=sys.stderr,
        )
        raise SystemExit(1)
