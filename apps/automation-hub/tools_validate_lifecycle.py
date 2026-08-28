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
    ApprovalSimulationStore,
    InMemoryAutomationAudit,
    build_automation_plan,
    build_dry_run_boundary_request,
    build_recovery_plan,
)
from operations_hub import evaluate_governance, normalize_channel_event  # noqa: E402


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_SPRINT_6_LIFECYCLE_VALIDATION_FAILED: {message}")


def main() -> None:
    audit_schema = json.loads((REPO / "contracts/automation/automation-audit-event.schema.json").read_text(encoding="utf-8"))
    recovery_schema = json.loads((REPO / "contracts/automation/recovery-plan.schema.json").read_text(encoding="utf-8"))

    audit_props = audit_schema["properties"]
    if audit_props["simulated"].get("const") is not True or audit_props["authority_effect"].get("const") != "none":
        fail("audit schema must remain simulated with no authority effect")
    for field in ("execution_authorized", "channel_reply_authorized", "mutation_authorized"):
        if audit_props[field].get("const") is not False:
            fail(f"audit schema {field} must remain false")

    recovery_props = recovery_schema["properties"]
    expected_false = (
        "automatic_retry",
        "retry_authorized",
        "rollback_required",
        "automatic_rollback",
        "rollback_authorized",
        "execution_authorized",
        "mutation_authorized",
    )
    for field in expected_false:
        if recovery_props[field].get("const") is not False:
            fail(f"recovery schema {field} must remain false")
    if recovery_props["rollback_reason"].get("const") != "dry_run_no_side_effect":
        fail("recovery schema rollback reason changed")
    if recovery_props["authority_effect"].get("const") != "none":
        fail("recovery schema authority effect changed")

    payload = json.loads((REPO / "apps/operations-hub/fixtures/whatsapp.json").read_text(encoding="utf-8"))
    event = normalize_channel_event(payload)
    plan = build_automation_plan(event, evaluate_governance(event))
    store = ApprovalSimulationStore()
    store.register_plan(plan)
    store.decide(plan["plan_id"], "approve", "fixture-lifecycle-decision")
    release = store.release_for_simulation(plan)
    request = build_dry_run_boundary_request(plan, release)

    audit = InMemoryAutomationAudit()
    audit.record_plan(plan)
    audit.record_approval(plan, release["approval_state"])
    audit.record_boundary_request(plan, request)
    audit.record_simulated_result(plan, request, outcome="simulated_failure")
    model = audit.read_model()
    if model["total_events"] != 4 or model["read_only"] is not True or model["authority_effect"] != "none":
        fail("lifecycle audit read model invalid")
    if [item["sequence"] for item in model["items"]] != [1, 2, 3, 4]:
        fail("lifecycle sequence is not append-only")

    recovery = build_recovery_plan(request, error_code="synthetic_timeout", retryable=True, attempt=1)
    if recovery["retry_planned"] is not True or recovery["automatic_retry"] is not False or recovery["retry_authorized"] is not False:
        fail("retry plan gained automatic authority")
    if recovery["rollback_required"] is not False or recovery["automatic_rollback"] is not False or recovery["rollback_authorized"] is not False:
        fail("dry-run recovery unexpectedly requires/authorizes rollback")
    if recovery["authority_effect"] != "none":
        fail("recovery plan authority effect changed")

    print("PHIL_AI_OS_SPRINT_6_LIFECYCLE_AUDIT_GREEN events=4 read_only=true authority_effect=none")
    print("PHIL_AI_OS_SPRINT_6_RECOVERY_PLAN_GREEN retry=planned_only rollback=dry_run_no_side_effect")


if __name__ == "__main__":
    main()
