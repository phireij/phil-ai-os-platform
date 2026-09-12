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
    build_task_automation_plan,
)
from operations_hub import (  # noqa: E402
    ReplyDraftDecisionError,
    SUPPORTED_SOURCES,
    build_reply_draft_decision_proposal,
    build_reply_draft_proposal,
    build_reply_operator_decision_packet,
    build_task_candidate,
    evaluate_governance,
    normalize_channel_event,
)


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

    store = ApprovalSimulationStore()
    audit = InMemoryAutomationAudit()
    approval_required_sources: set[str] = set()
    not_required_sources: set[str] = set()
    reply_packet_sources: set[str] = set()
    governance_blocked_reply_sources: set[str] = set()
    requests: dict[str, dict] = {}

    for source in SUPPORTED_SOURCES:
        fixture_path = REPO / "apps/operations-hub/fixtures" / f"{source}.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        if payload.get("fixture_only") is not True or payload.get("source") != source:
            fail(f"{source} fixture boundary invalid")

        event = normalize_channel_event(payload)
        governance = evaluate_governance(event)
        task_candidate = build_task_candidate(event, governance)
        legacy_plan = build_automation_plan(event, governance)
        plan = build_task_automation_plan(task_candidate)

        for field in (
            "plan_id",
            "lifecycle_correlation_id",
            "source",
            "normalized_intent",
            "risk_level",
            "approval_required",
            "approval_state",
            "plan_state",
        ):
            if plan.get(field) != legacy_plan.get(field):
                fail(f"{source} task/event automation plan alignment changed at {field}")
        if plan["steps"][0]["name"] != "observe_task_candidate":
            fail(f"{source} task automation plan did not observe extracted task")
        if plan["steps"][1]["name"] != "validate_task_governance":
            fail(f"{source} task automation plan lost governance validation")

        # Prove the customer-reply lifecycle remains bounded at explicit operator decision.
        reply_draft = build_reply_draft_proposal(
            task_candidate,
            f"Simulation-only reply draft for {source}.",
            drafted_by="hermes",
        )
        if reply_draft["authority"]["channel_reply_authorized"] is not False:
            fail(f"{source} reply draft gained channel reply authority")
        if task_candidate["approval_required"]:
            try:
                build_reply_draft_decision_proposal(
                    reply_draft,
                    recommendation="recommend_future_dispatch",
                    reviewer_ref="operator:simulation",
                )
            except ReplyDraftDecisionError:
                governance_blocked_reply_sources.add(source)
            else:
                fail(f"{source} governance-gated reply reached operator recommendation")
        else:
            decision_proposal = build_reply_draft_decision_proposal(
                reply_draft,
                recommendation="recommend_future_dispatch",
                reviewer_ref="operator:simulation",
            )
            packet = build_reply_operator_decision_packet(reply_draft, decision_proposal)
            if packet["state"] != "awaiting_explicit_operator_decision" or packet["operator_decision"] is not None:
                fail(f"{source} operator decision packet state invalid")
            packet_authority = packet.get("authority", {})
            for field in (
                "reply_approved",
                "channel_reply_authorized",
                "network_dispatch_authorized",
                "execution_authorized",
                "woo_commerce_mutation_authorized",
                "order_creation_authorized",
                "payment_execution_authorized",
                "sms_send_authorized",
                "inventory_mutation_authorized",
                "production_publish_authorized",
                "mutation_authorized",
            ):
                if packet_authority.get(field) is not False:
                    fail(f"{source} operator decision packet gained {field}")
            if packet_authority.get("authority_effect") != "none":
                fail(f"{source} operator decision packet changed authority effect")
            reply_packet_sources.add(source)

        store.register_plan(plan)

        if plan["approval_required"]:
            approval_required_sources.add(source)
            store.decide(plan["plan_id"], "approve", f"fixture-lifecycle-{source}-approval")
        else:
            not_required_sources.add(source)

        release = store.release_for_simulation(plan)
        expected_approval_state = "approved" if plan["approval_required"] else "not_required"
        if release["approval_state"] != expected_approval_state:
            fail(f"{source} approval release state invalid")

        request = build_dry_run_boundary_request(plan, release)
        if request["dispatch"] is not False or request["network_call"] is not False:
            fail(f"{source} dry-run request attempted dispatch or network")
        for field in ("automatic_execution", "execution_authorized", "channel_reply_authorized", "mutation_authorized"):
            if request[field] is not False:
                fail(f"{source} dry-run request gained {field}")
        if request["authority_effect"] != "none":
            fail(f"{source} dry-run request changed authority")

        audit.record_plan(plan)
        audit.record_approval(plan, release["approval_state"])
        audit.record_boundary_request(plan, request)
        audit.record_simulated_result(
            plan,
            request,
            outcome="simulated_failure" if source == "whatsapp" else "simulated_success",
        )
        requests[source] = request

    if approval_required_sources != {"whatsapp", "google_business"}:
        fail(f"approval-required source matrix changed: {sorted(approval_required_sources)}")
    if not_required_sources != {"facebook", "instagram", "telegram"}:
        fail(f"approval-not-required source matrix changed: {sorted(not_required_sources)}")
    if reply_packet_sources != {"facebook", "instagram", "telegram"}:
        fail(f"operator-ready reply packet matrix changed: {sorted(reply_packet_sources)}")
    if governance_blocked_reply_sources != {"whatsapp", "google_business"}:
        fail(f"governance-blocked reply matrix changed: {sorted(governance_blocked_reply_sources)}")

    model = audit.read_model()
    expected_events = len(SUPPORTED_SOURCES) * 4
    if model["total_events"] != expected_events or model["read_only"] is not True or model["authority_effect"] != "none":
        fail("multi-channel lifecycle audit read model invalid")
    expected_stages = {
        "plan_created": len(SUPPORTED_SOURCES),
        "approval_evaluated": len(SUPPORTED_SOURCES),
        "boundary_preview": len(SUPPORTED_SOURCES),
        "result_preview": len(SUPPORTED_SOURCES),
    }
    if model["by_stage"] != expected_stages:
        fail("multi-channel lifecycle audit stage counts invalid")
    if [item["sequence"] for item in model["items"]] != list(range(1, expected_events + 1)):
        fail("multi-channel lifecycle sequence is not append-only")
    if any(
        item[field] is not False
        for item in model["items"]
        for field in ("execution_authorized", "channel_reply_authorized", "mutation_authorized")
    ):
        fail("multi-channel audit event gained authority")

    recovery = build_recovery_plan(
        requests["whatsapp"],
        error_code="synthetic_timeout",
        retryable=True,
        attempt=1,
    )
    if recovery["retry_planned"] is not True or recovery["automatic_retry"] is not False or recovery["retry_authorized"] is not False:
        fail("retry plan gained automatic authority")
    if recovery["rollback_required"] is not False or recovery["automatic_rollback"] is not False or recovery["rollback_authorized"] is not False:
        fail("dry-run recovery unexpectedly requires/authorizes rollback")
    if recovery["authority_effect"] != "none":
        fail("recovery plan authority effect changed")

    print(
        "PHIL_AI_OS_SPRINT_6_TASK_AUTOMATION_BRIDGE_GREEN "
        f"sources={len(SUPPORTED_SOURCES)} approvals={len(approval_required_sources)} "
        f"no_approval={len(not_required_sources)} task_plan_identity=stable"
    )
    print(
        "PHIL_AI_OS_SPRINT_6_REPLY_DECISION_BOUNDARY_GREEN "
        f"operator_ready={len(reply_packet_sources)} governance_blocked={len(governance_blocked_reply_sources)} "
        "operator_decision=unset dispatch=false network_call=false reply=false mutation=false authority_effect=none"
    )
    print(
        "PHIL_AI_OS_SPRINT_6_MULTICHANNEL_SIMULATION_GREEN "
        f"sources={len(SUPPORTED_SOURCES)} approvals={len(approval_required_sources)} "
        f"no_approval={len(not_required_sources)} audit_events={model['total_events']} "
        "dispatch=false network_call=false execution=false reply=false mutation=false authority_effect=none"
    )
    print("PHIL_AI_OS_SPRINT_6_RECOVERY_PLAN_GREEN retry=planned_only rollback=dry_run_no_side_effect")


if __name__ == "__main__":
    main()
