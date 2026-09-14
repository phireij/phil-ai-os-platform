#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREVIEW = ROOT / "mission-control"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_MISSION_CONTROL_PREVIEW_VALIDATION_FAILED: {message}")


def main() -> None:
    html = (PREVIEW / "index.html").read_text(encoding="utf-8")
    js = (PREVIEW / "mission-control.mjs").read_text(encoding="utf-8")
    fixture = json.loads((PREVIEW / "fixture.json").read_text(encoding="utf-8"))

    if fixture.get("schema") != "phil-ai-os-mission-control-lifecycle-projection":
        fail("projection schema drift")
    if fixture.get("version") != 5:
        fail("Mission Control projection version must be 5")
    if fixture.get("status") != "read_only" or fixture.get("mission_control_mode") != "read_only":
        fail("Mission Control must remain read_only")
    if fixture.get("authority_effect") != "none":
        fail("authority_effect must remain none")
    if fixture.get("automation", {}).get("simulated_only") is not True:
        fail("automation must remain simulated-only")
    if fixture.get("attention", {}).get("read_only") is not True:
        fail("operator attention projection must remain read-only")

    task_composition = fixture.get("task_composition", {})
    if task_composition.get("read_only") is not True:
        fail("task composition must remain read-only")
    if task_composition.get("customer_payloads_exposed") is not False:
        fail("task composition must not expose customer payloads")
    if task_composition.get("normalized_intent_exposed") is not False:
        fail("task composition must not expose normalized intent")
    for group in ("by_source", "by_type"):
        values = task_composition.get(group)
        if not isinstance(values, dict):
            fail(f"task composition {group} must be an object")
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values.values()):
            fail(f"task composition {group} contains invalid counts")

    approval = fixture.get("approval", {})
    if approval.get("read_only") is not True or approval.get("authority_effect") != "none":
        fail("approval posture must remain read-only with no authority effect")
    if approval.get("decision_ids_exposed") is not False:
        fail("approval decision identifiers must remain hidden")
    for field in ("plan_count", "decision_count", "awaiting_decision", "simulation_releasable"):
        value = approval.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            fail(f"approval {field} must be a non-negative integer")
    state_counts = approval.get("by_state")
    if not isinstance(state_counts, dict) or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in state_counts.values()
    ):
        fail("approval by_state invalid")
    for field in ("automatic_execution", "execution_authorized", "channel_reply_authorized", "mutation_authorized"):
        if approval.get(field) is not False:
            fail(f"approval authority expanded: {field}")

    recovery = fixture.get("recovery", {})
    if recovery.get("read_only") is not True or recovery.get("authority_effect") != "none":
        fail("recovery posture must remain read-only with no authority effect")
    for field in ("plan_count", "duplicate_plans", "retry_simulation_count", "stop_for_review_count"):
        value = recovery.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            fail(f"recovery {field} must be a non-negative integer")
    error_counts = recovery.get("error_code_counts")
    if not isinstance(error_counts, dict) or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in error_counts.values()
    ):
        fail("recovery error_code_counts invalid")
    for field in (
        "automatic_retry",
        "retry_authorized",
        "automatic_rollback",
        "rollback_authorized",
        "execution_authorized",
        "mutation_authorized",
    ):
        if recovery.get(field) is not False:
            fail(f"recovery authority expanded: {field}")

    control = fixture.get("control_plane", {})
    if control.get("autonomy_level") != "A0":
        fail("autonomy level must remain A0")
    if control.get("execution_task_class") != "general":
        fail("execution task class must remain general")
    if control.get("hermes_state") != "idle":
        fail("Hermes must remain idle")
    if control.get("operator_decision_required_for_sensitive_actions") is not True:
        fail("sensitive actions must remain operator-gated")
    for field in ("specialists_enabled", "mission_control_write_enabled", "live_execution_enabled"):
        if control.get(field) is not False:
            fail(f"control-plane authority expanded: {field}")

    authority_flags = (
        "execution_authorized",
        "channel_reply_authorized",
        "network_dispatch_authorized",
        "woo_commerce_mutation_authorized",
        "order_creation_authorized",
        "payment_execution_authorized",
        "sms_send_authorized",
        "inventory_mutation_authorized",
        "production_publish_authorized",
        "mutation_authorized",
    )
    for field in authority_flags:
        if fixture.get(field) is not False:
            fail(f"{field} must remain false")

    for field, value in fixture.get("privacy", {}).items():
        if value is not False:
            fail(f"privacy exposure must remain false: {field}")

    forbidden_html = (
        r"<form\b",
        r"<button\b",
        r"type=[\"']submit[\"']",
        r"\bapprove\b[^<]{0,30}(button|control)",
        r"\bsend\b[^<]{0,30}(button|control)",
    )
    for pattern in forbidden_html:
        if re.search(pattern, html, flags=re.IGNORECASE):
            fail(f"interactive/authorizing HTML surface found: {pattern}")

    forbidden_js = (
        r"\bPOST\b",
        r"\bPUT\b",
        r"\bPATCH\b",
        r"\bDELETE\b",
        r"XMLHttpRequest",
        r"WebSocket",
        r"navigator\.sendBeacon",
    )
    for pattern in forbidden_js:
        if re.search(pattern, js, flags=re.IGNORECASE):
            fail(f"network write capability found: {pattern}")

    if 'fetch("./fixture.json"' not in js:
        fail("preview must load only the bounded local fixture")
    if "cache: \"no-store\"" not in js:
        fail("preview fixture must avoid stale caching")
    if "assertReadOnly" not in js:
        fail("runtime fail-closed read-only assertion missing")

    print(
        "PHIL_AI_OS_MISSION_CONTROL_PREVIEW_GREEN "
        "mode=read_only version=5 autonomy=A0 hermes=idle attention=read_only task_composition=read_only "
        "approval=read_only decision_ids=false recovery=read_only retry_authorized=false rollback_authorized=false "
        "simulated_only=true writes=false replies=false network_dispatch=false authority_effect=none"
    )


if __name__ == "__main__":
    main()
