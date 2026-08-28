#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(REPO / "apps/operations-hub/src"))

from automation_hub import (  # noqa: E402
    ApprovalReplayError,
    ApprovalSimulationStore,
    build_automation_plan,
    build_dry_run_boundary_request,
)
from operations_hub import evaluate_governance, normalize_channel_event  # noqa: E402


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_SPRINT_6_AUTOMATION_VALIDATION_FAILED: {message}")


def main() -> None:
    schema = json.loads((REPO / "contracts/automation/automation-plan.schema.json").read_text(encoding="utf-8"))
    release_schema = json.loads((REPO / "contracts/automation/simulation-release.schema.json").read_text(encoding="utf-8"))
    boundary_schema = json.loads((REPO / "contracts/automation/dry-run-boundary-request.schema.json").read_text(encoding="utf-8"))
    props = schema["properties"]
    required_consts = {
        "task_class": "general",
        "assigned_agent": "hermes",
        "specialist_enabled": False,
        "automatic_execution": False,
        "execution_authorized": False,
        "channel_reply_authorized": False,
        "mutation_authorized": False,
        "authority_effect": "none",
    }
    for field, expected in required_consts.items():
        if props[field].get("const") != expected:
            fail(f"schema {field} must remain {expected!r}")

    release_props = release_schema["properties"]
    if release_props["simulation_release"].get("const") is not True:
        fail("simulation release contract must explicitly release simulation")
    for field in ("automatic_execution", "execution_authorized", "channel_reply_authorized", "mutation_authorized"):
        if release_props[field].get("const") is not False:
            fail(f"simulation release {field} must remain false")
    if release_props["authority_effect"].get("const") != "none":
        fail("simulation release authority_effect must remain none")

    boundary_props = boundary_schema["properties"]
    expected_boundary = {
        "target": "execution_boundary",
        "operation": "preview_request",
        "mode": "dry_run",
        "task_class": "general",
        "assigned_agent": "hermes",
        "dry_run": True,
        "dispatch": False,
        "network_call": False,
        "automatic_execution": False,
        "execution_authorized": False,
        "channel_reply_authorized": False,
        "mutation_authorized": False,
        "authority_effect": "none",
    }
    for field, expected in expected_boundary.items():
        if boundary_props[field].get("const") != expected:
            fail(f"dry-run request {field} must remain {expected!r}")

    sources = ("facebook", "instagram", "telegram", "whatsapp", "google_business")
    plans = []
    by_source = {}
    for source in sources:
        payload = json.loads((REPO / f"apps/operations-hub/fixtures/{source}.json").read_text(encoding="utf-8"))
        event = normalize_channel_event(payload)
        governance = evaluate_governance(event)
        plan = build_automation_plan(event, governance)
        if plan["authority_effect"] != "none":
            fail(f"{source} plan gained authority")
        if plan["task_class"] != "general" or plan["assigned_agent"] != "hermes" or plan["specialist_enabled"] is not False:
            fail(f"{source} routing escaped baseline")
        if any(plan[field] is not False for field in ("automatic_execution", "execution_authorized", "channel_reply_authorized", "mutation_authorized")):
            fail(f"{source} plan gained execution/reply/mutation authority")
        plans.append(plan)
        by_source[source] = plan

    blocked = sum(1 for plan in plans if plan["plan_state"] == "blocked_pending_approval")
    ready = sum(1 for plan in plans if plan["plan_state"] == "ready_for_simulation")
    if blocked != 2 or ready != 3:
        fail(f"unexpected simulation states blocked={blocked} ready={ready}")

    store = ApprovalSimulationStore()
    complaint_plan = by_source["whatsapp"]
    store.register_plan(complaint_plan)
    store.decide(complaint_plan["plan_id"], "approve", "fixture-decision-001")
    release = store.release_for_simulation(complaint_plan)
    if release["simulation_release"] is not True or release["authority_effect"] != "none":
        fail("approved plan did not produce a bounded simulation release")
    if any(release[field] is not False for field in ("automatic_execution", "execution_authorized", "channel_reply_authorized", "mutation_authorized")):
        fail("approval simulation release gained authority")
    try:
        store.decide(complaint_plan["plan_id"], "approve", "fixture-decision-replay")
    except ApprovalReplayError:
        replay_protected = True
    else:
        replay_protected = False
    if not replay_protected:
        fail("approval decision replay was accepted")

    low_risk_plan = by_source["instagram"]
    store.register_plan(low_risk_plan)
    direct_release = store.release_for_simulation(low_risk_plan)
    if direct_release["approval_state"] != "not_required" or direct_release["execution_authorized"] is not False:
        fail("not-required plan simulation release invalid")

    approved_request = build_dry_run_boundary_request(complaint_plan, release)
    direct_request = build_dry_run_boundary_request(low_risk_plan, direct_release)
    for request in (approved_request, direct_request):
        if request["dry_run"] is not True or request["dispatch"] is not False or request["network_call"] is not False:
            fail("dry-run boundary request can dispatch or call network")
        if any(request[field] is not False for field in ("automatic_execution", "execution_authorized", "channel_reply_authorized", "mutation_authorized")):
            fail("dry-run boundary request gained authority")
        if request["authority_effect"] != "none":
            fail("dry-run boundary request authority effect changed")

    print(f"PHIL_AI_OS_SPRINT_6_AUTOMATION_VALIDATION_GREEN sources={len(plans)} blocked={blocked} ready={ready}")
    print("PHIL_AI_OS_SPRINT_6_AUTHORITY_BOUNDARY_GREEN task_class=general assigned_agent=hermes authority_effect=none")
    print("PHIL_AI_OS_SPRINT_6_APPROVAL_SIMULATION_GREEN replay_protected=true authority_effect=none")
    print("PHIL_AI_OS_SPRINT_6_DRY_RUN_BOUNDARY_GREEN dispatch=false network_call=false authority_effect=none")


if __name__ == "__main__":
    main()
