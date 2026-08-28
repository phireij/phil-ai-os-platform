#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone, timedelta

TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "DENIED", "EXPIRED"}


def parse_ts(v):
    if not v:
        return None
    return datetime.fromisoformat(v.replace("Z", "+00:00"))


def presence_state(presence, now, identity_required=False):
    if not presence:
        return {"state": "unknown", "identity_verified": False, "evidence_complete": False}
    if identity_required and not presence.get("identity_verified", False):
        return {"state": "unknown", "identity_verified": False, "evidence_complete": False}
    observed = parse_ts(presence.get("observed_at"))
    if observed is None:
        return {"state": "unknown", "identity_verified": False, "evidence_complete": False}
    age = max(0.0, (now - observed).total_seconds())
    if age <= 120:
        state = "fresh"
    elif age <= 300:
        state = "stale"
    else:
        state = "offline"
    return {
        "state": state,
        "observed_at": presence.get("observed_at"),
        "age_seconds": round(age, 3),
        "source_component": presence.get("source_component"),
        "identity_verified": bool(presence.get("identity_verified", True)),
        "evidence_complete": True,
    }


def reconstruct_workloads(lifecycle, registered_ids):
    by_task = {}
    for ev in lifecycle:
        by_task.setdefault(ev["task_id"], []).append(ev)

    owned = {aid: [] for aid in registered_ids}
    conflicts = {aid: False for aid in registered_ids}
    assignment_counts = {}

    for task_id, rows in by_task.items():
        rows = sorted(rows, key=lambda r: (r["occurred_at"], r.get("event_id", "")))
        owners = []
        owner = None
        for row in rows:
            aid = row.get("assigned_agent_id")
            if row.get("stage") == "ASSIGNED" and aid:
                owner = aid
                owners.append(aid)
                assignment_counts[(task_id, aid)] = assignment_counts.get((task_id, aid), 0) + 1
        latest = rows[-1]
        if owner in owned:
            owned[owner].append({
                "task_id": task_id,
                "latest_stage": latest["stage"],
                "active": latest["stage"] not in TERMINAL,
                "assignment_count": assignment_counts[(task_id, owner)],
            })
        if len(set(owners)) > 1:
            for aid in set(owners):
                if aid in conflicts:
                    conflicts[aid] = True
    return owned, conflicts


def project(registry, presences, lifecycle, handoffs, now):
    reg = {r["agent_id"]: r for r in registry}
    owned, conflicts = reconstruct_workloads(lifecycle, reg.keys())
    agents = []

    for aid in sorted(reg):
        r = reg[aid]
        identity_required = aid == "specialist-worker-01"
        p = presence_state(presences.get(aid), now, identity_required=identity_required)
        tasks = owned[aid]
        active = [t for t in tasks if t["active"]]
        latest_owned = tasks[-1]["latest_stage"] if tasks else None
        workload_complete = not conflicts[aid]

        if not bool(r["enabled"]) or not bool(r["assignable"]):
            readiness, reason = "unassignable", "registry_disabled_or_nonassignable"
        elif not workload_complete:
            readiness, reason = "indeterminate", "ownership_conflict"
        elif p["state"] == "unknown":
            readiness, reason = "indeterminate", "presence_evidence_incomplete"
        elif p["state"] == "stale":
            readiness, reason = "stale", "presence_stale"
        elif p["state"] == "offline":
            readiness, reason = "offline", "presence_offline"
        elif active:
            readiness, reason = "busy", "durable_active_workload_present"
        else:
            readiness, reason = "ready", "eligible_fresh_no_active_workload"

        agent_complete = bool(workload_complete and p.get("evidence_complete", False))
        agents.append({
            "agent_id": aid,
            "display_name": r.get("display_name"),
            "role": r.get("role"),
            "authority_ceiling": r["authority_ceiling"],
            "registry": {
                "enabled": bool(r["enabled"]),
                "assignable": bool(r["assignable"]),
                "evidence_complete": True,
            },
            "presence": p,
            "workload": {
                "active_task_count": len(active),
                "active_tasks": [t["task_id"] for t in active],
                "latest_owned_stage": latest_owned,
                "evidence_complete": workload_complete,
            },
            "readiness": {
                "state": readiness,
                "reason": reason,
                "grants_authority": False,
            },
            "evidence_complete": agent_complete,
        })

    lifecycle_by_task = {}
    for ev in lifecycle:
        lifecycle_by_task.setdefault(ev["task_id"], []).append(ev)

    projected_handoffs = []
    for h in handoffs:
        rows = sorted(lifecycle_by_task.get(h["task_id"], []), key=lambda r: (r["occurred_at"], r.get("event_id", "")))
        latest_stage = rows[-1]["stage"] if rows else None
        essentials = [
            h.get("handoff_id"), h.get("task_id"), h.get("source_agent_id"),
            h.get("target_agent_id"), h.get("correlation_id"), h.get("required_authority"), h.get("state")
        ]
        ids_known = h.get("source_agent_id") in reg and h.get("target_agent_id") in reg
        complete = all(essentials) and ids_known and latest_stage is not None
        projected_handoffs.append({
            **h,
            "task_latest_stage": latest_stage,
            "active_ownership": bool(h.get("state") == "accepted" and latest_stage not in TERMINAL),
            "evidence_complete": bool(complete),
        })

    return {
        "schema": "2.2-a7.v1",
        "generated_at": now.isoformat(),
        "evidence_complete": all(a["evidence_complete"] for a in agents) and all(h["evidence_complete"] for h in projected_handoffs),
        "agents": agents,
        "handoffs": projected_handoffs,
        "governance": {
            "mission_control_authority": "read_only_observer",
            "automatic_assignment": False,
            "automatic_retry": False,
            "automatic_reroute": False,
            "automatic_delegation": False,
            "automatic_execution": False,
        },
    }


def agent(out, aid):
    return next(x for x in out["agents"] if x["agent_id"] == aid)


def main():
    now = datetime(2026, 8, 28, 6, 20, tzinfo=timezone.utc)
    ts = lambda seconds: (now - timedelta(seconds=seconds)).isoformat()

    registry = [
        {"agent_id": "hermes", "display_name": "Hermes", "role": "general_worker", "authority_ceiling": "L3", "enabled": 1, "assignable": 1},
        {"agent_id": "specialist-worker-01", "display_name": "Specialist Worker 01", "role": "specialist_worker", "authority_ceiling": "L1", "enabled": 0, "assignable": 0},
    ]
    presences = {
        "hermes": {"observed_at": ts(20), "source_component": "authenticated_control_api_roundtrip", "identity_verified": True},
        "specialist-worker-01": {"observed_at": ts(30), "source_component": "specialist_presence_heartbeat", "identity_verified": True},
    }
    lifecycle = [
        {"event_id": "e1", "task_id": "tsk_active", "stage": "ASSIGNED", "occurred_at": ts(100), "assigned_agent_id": "hermes"},
        {"event_id": "e2", "task_id": "tsk_active", "stage": "PLANNED", "occurred_at": ts(80), "assigned_agent_id": None},
        {"event_id": "e3", "task_id": "tsk_canary", "stage": "ASSIGNED", "occurred_at": ts(70), "assigned_agent_id": "hermes"},
        {"event_id": "e4", "task_id": "tsk_canary", "stage": "ASSIGNED", "occurred_at": ts(60), "assigned_agent_id": "specialist-worker-01"},
        {"event_id": "e5", "task_id": "tsk_canary", "stage": "COMPLETED", "occurred_at": ts(50), "assigned_agent_id": None},
    ]
    handoffs = [{
        "handoff_id": "hof_canary", "task_id": "tsk_canary", "source_agent_id": "hermes",
        "target_agent_id": "specialist-worker-01", "task_class": "general", "required_authority": "L1",
        "source_authority_ceiling": "L3", "target_authority_ceiling": "L1",
        "reason_code": "phase_2_2_a6_8_controlled_canary", "correlation_id": "hofcorr_canary",
        "state": "accepted", "handoff_approval_required": 1, "handoff_approval_state": "approved",
        "execution_approval_state": "not_consumed", "requested_at": ts(65), "decided_at": ts(60),
        "lifecycle_event_id": "e4",
    }]

    out = project(registry, presences, lifecycle, handoffs, now)
    h = agent(out, "hermes")
    s = agent(out, "specialist-worker-01")
    assert out["schema"] == "2.2-a7.v1"
    assert out["governance"]["mission_control_authority"] == "read_only_observer"
    assert not any(out["governance"][k] for k in out["governance"] if k.startswith("automatic_"))
    assert h["authority_ceiling"] == "L3" and h["readiness"]["state"] == "busy"
    assert h["workload"]["active_task_count"] == 1
    assert s["authority_ceiling"] == "L1"
    assert s["presence"]["state"] == "fresh" and s["presence"]["identity_verified"] is True
    assert s["readiness"]["state"] == "unassignable"
    assert s["readiness"]["grants_authority"] is False
    assert s["workload"]["active_task_count"] == 0
    assert s["workload"]["latest_owned_stage"] == "COMPLETED"
    assert len(out["handoffs"]) == 1
    assert out["handoffs"][0]["state"] == "accepted"
    assert out["handoffs"][0]["active_ownership"] is False
    assert out["handoffs"][0]["task_latest_stage"] == "COMPLETED"

    bad_presence = dict(presences)
    bad_presence["specialist-worker-01"] = {"observed_at": ts(10), "source_component": "specialist_presence_heartbeat", "identity_verified": False}
    bad = project(registry, bad_presence, lifecycle, handoffs, now)
    bs = agent(bad, "specialist-worker-01")
    assert bs["presence"]["state"] == "unknown"
    assert bs["evidence_complete"] is False
    assert bs["readiness"]["state"] == "unassignable"  # registry precedence remains strongest
    assert bad["evidence_complete"] is False

    eligible_registry = [dict(x) for x in registry]
    eligible_registry[1]["enabled"] = 1; eligible_registry[1]["assignable"] = 1
    conflict_lifecycle = lifecycle + [
        {"event_id": "e6", "task_id": "tsk_conflict", "stage": "ASSIGNED", "occurred_at": ts(45), "assigned_agent_id": "hermes"},
        {"event_id": "e7", "task_id": "tsk_conflict", "stage": "ASSIGNED", "occurred_at": ts(44), "assigned_agent_id": "specialist-worker-01"},
    ]
    conflict = project(eligible_registry, presences, conflict_lifecycle, handoffs, now)
    assert agent(conflict, "specialist-worker-01")["readiness"]["state"] == "indeterminate"
    assert agent(conflict, "specialist-worker-01")["workload"]["evidence_complete"] is False

    secret_words = {"token", "secret", "private_key", "authorization"}
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                assert k.lower() not in secret_words
                walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(out)

    print("schema=2.2-a7.v1")
    print("registry_precedence=verified")
    print("fresh_disabled_specialist=unassignable")
    print("terminal_handoff_history=visible_inactive")
    print("specialist_active_workload=0")
    print("missing_identity_evidence=fail_closed")
    print("ownership_conflict=indeterminate")
    print("secret_exclusion=verified")
    print("mission_control_authority=read_only_observer")
    print("PHIL_AI_OS_PHASE_2_2_A7_2_ISOLATED_READ_MODEL_CONTRACT_OK")


if __name__ == "__main__":
    main()
