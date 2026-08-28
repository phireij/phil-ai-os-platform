#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(REPO / "apps/operations-hub/src"))

from automation_hub import build_automation_plan  # noqa: E402
from operations_hub import evaluate_governance, normalize_channel_event  # noqa: E402


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_SPRINT_6_AUTOMATION_VALIDATION_FAILED: {message}")


def main() -> None:
    schema = json.loads((REPO / "contracts/automation/automation-plan.schema.json").read_text(encoding="utf-8"))
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

    sources = ("facebook", "instagram", "telegram", "whatsapp", "google_business")
    plans = []
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

    blocked = sum(1 for plan in plans if plan["plan_state"] == "blocked_pending_approval")
    ready = sum(1 for plan in plans if plan["plan_state"] == "ready_for_simulation")
    if blocked != 2 or ready != 3:
        fail(f"unexpected simulation states blocked={blocked} ready={ready}")

    print(f"PHIL_AI_OS_SPRINT_6_AUTOMATION_VALIDATION_GREEN sources={len(plans)} blocked={blocked} ready={ready}")
    print("PHIL_AI_OS_SPRINT_6_AUTHORITY_BOUNDARY_GREEN task_class=general assigned_agent=hermes authority_effect=none")


if __name__ == "__main__":
    main()
