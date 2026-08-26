#!/usr/bin/env python3
import datetime as dt
import json
import subprocess
import sys
from typing import Any

SCHEMA_VERSION = "2.1e.v1"
CONTROL_API_BASE = "http://127.0.0.1:4870"
CONTROL_DB = "/app/state/control-plane.db"
SENSITIVE_FRAGMENTS = ("token", "secret", "api_key", "apikey", "authorization", "password", "private_key")


def run(cmd, check=True):
    p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(f"command_failed:{cmd[0]}:{p.returncode}")
    return p.stdout.strip(), p.returncode


def state_of_unit(unit: str) -> str:
    _, rc = run(["systemctl", "is-active", "--quiet", unit], check=False)
    if rc == 0:
        return "active"
    out, _ = run(["systemctl", "is-failed", unit], check=False)
    return "failed" if out.strip() == "failed" else "inactive"


def docker_name(pattern: str, startswith=False) -> str:
    out, _ = run(["docker", "ps", "--format", "{{.Names}}"])
    for name in out.splitlines():
        if (startswith and name.startswith(pattern)) or ((not startswith) and pattern in name):
            return name
    raise RuntimeError(f"container_not_found:{pattern}")


def http_status(path: str) -> str:
    _, rc = run(["curl", "-fsS", "--max-time", "5", CONTROL_API_BASE + path], check=False)
    return "ok" if rc == 0 else "down"


def hermes_read(hermes: str, command: str) -> Any:
    out, _ = run(["docker", "exec", hermes, "/usr/local/bin/philaios-mission-control", command])
    return json.loads(out)


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {}
        for k, v in value.items():
            lk = str(k).lower()
            if any(fragment in lk for fragment in SENSITIVE_FRAGMENTS):
                continue
            cleaned[k] = sanitize(v)
        return cleaned
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    return value


def list_payload(payload: Any, preferred_key: str):
    payload = sanitize(payload)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        candidate = payload.get(preferred_key)
        if isinstance(candidate, list):
            return candidate
    return []


def env_value(control: str, key: str):
    out, _ = run(["docker", "inspect", control, "--format", "{{range .Config.Env}}{{println .}}{{end}}"])
    prefix = key + "="
    for line in out.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):]
    return None


def recursive_find(obj: Any, keys):
    wanted = {k.lower() for k in keys}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in wanted:
                return v
        for v in obj.values():
            found = recursive_find(v, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = recursive_find(v, keys)
            if found is not None:
                return found
    return None


def bool_state(value):
    if isinstance(value, bool):
        return "enabled" if value else "disabled"
    if value is None:
        return "unavailable"
    text = str(value).strip().lower()
    if text in {"1", "true", "enabled", "on"}:
        return "enabled"
    if text in {"0", "false", "disabled", "off"}:
        return "disabled"
    return "unknown"


def canonical_tasks(approvals, executions):
    by_id = {}
    legacy = 0
    for kind, rows in (("approval", approvals), ("execution", executions)):
        for row in rows:
            if not isinstance(row, dict):
                legacy += 1
                continue
            task_id = row.get("task_id") or row.get("canonical_task_id")
            if not task_id:
                legacy += 1
                continue
            task = by_id.setdefault(str(task_id), {
                "task_id": str(task_id),
                "lifecycle_state": "RECEIVED",
                "assigned_agent_id": row.get("agent_id") or row.get("requester") or row.get("requested_by"),
                "approval_ids": [],
                "execution_ids": [],
                "correlation_quality": "canonical",
            })
            if kind == "approval":
                rid = row.get("approval_id") or row.get("id")
                if rid and rid not in task["approval_ids"]:
                    task["approval_ids"].append(rid)
                state = str(row.get("state") or row.get("status") or "").lower()
                if state == "pending": task["lifecycle_state"] = "APPROVAL_PENDING"
                elif state == "approved": task["lifecycle_state"] = "AUTHORIZED"
                elif state == "denied": task["lifecycle_state"] = "DENIED"
                elif state == "expired": task["lifecycle_state"] = "EXPIRED"
            else:
                rid = row.get("execution_id") or row.get("id")
                if rid and rid not in task["execution_ids"]:
                    task["execution_ids"].append(rid)
                state = str(row.get("state") or row.get("status") or row.get("outcome") or "").lower()
                if state in {"running", "executing"}: task["lifecycle_state"] = "EXECUTING"
                elif state in {"success", "succeeded", "completed"}: task["lifecycle_state"] = "SUCCEEDED"
                elif state in {"failed", "error"}: task["lifecycle_state"] = "FAILED"
                elif state in {"blocked", "rejected"}: task["lifecycle_state"] = "BLOCKED"
                elif state in {"cancelled", "canceled"}: task["lifecycle_state"] = "CANCELLED"
    quality = "canonical" if by_id and legacy == 0 else "partial" if by_id else "none" if not approvals and not executions else "legacy"
    return list(by_id.values()), quality, legacy


def durable_approval_execution_links(control: str):
    # Explicit column allowlists prevent task text, decision notes, link hashes,
    # execution detail, provider responses, or credential material from entering
    # the browser-facing read model.
    code = r'''import sqlite3,json
c=sqlite3.connect("/app/state/control-plane.db")
c.row_factory=sqlite3.Row
approvals=[dict(r) for r in c.execute("""select approval_id,created_at,updated_at,expires_at,state,source,requester,task_class,requested_by,decision_by,decision_at,consumed_at,consumed_by from approval_requests order by rowid desc limit 100""")]
audits=[dict(r) for r in c.execute("""select id,occurred_at,source,task_class,provider_id,model_id,route_path,compatibility_pass,execution_mode,outcome,approval_id from execution_audit order by rowid desc limit 200""")]
print(json.dumps({"approvals":approvals,"audits":audits},default=str))'''
    out, _ = run(["docker", "exec", control, "python3", "-c", code])
    data = json.loads(out)
    approvals = data.get("approvals", [])
    audits = data.get("audits", [])
    audits_by_approval = {}
    unlinked_audits = 0
    for audit in audits:
        approval_id = audit.get("approval_id")
        if approval_id:
            audits_by_approval.setdefault(str(approval_id), []).append(audit)
        else:
            unlinked_audits += 1
    links = []
    seen = set()
    for approval in approvals:
        approval_id = approval.get("approval_id")
        if not approval_id:
            continue
        approval_id = str(approval_id)
        seen.add(approval_id)
        linked = audits_by_approval.get(approval_id, [])
        links.append({
            "correlation_key_type": "approval_id",
            "approval_id": approval_id,
            "canonical_task_id": None,
            "approval": approval,
            "execution_audits": linked,
            "execution_audit_count": len(linked),
            "link_quality": "durable_authoritative" if linked else "approval_only",
        })
    orphan_linked = sum(len(v) for k, v in audits_by_approval.items() if k not in seen)
    summary = {
        "approval_row_count_observed": len(approvals),
        "execution_audit_row_count_observed": len(audits),
        "linked_approval_count": sum(1 for x in links if x["execution_audit_count"] > 0),
        "approval_only_count": sum(1 for x in links if x["execution_audit_count"] == 0),
        "unlinked_execution_audit_count": unlinked_audits,
        "execution_audits_with_missing_observed_approval": orphan_linked,
        "canonical_task_persistence": "absent",
        "correlation_key_type": "approval_id",
        "provenance": "control_api_sqlite_read_only",
    }
    return links, summary


def main():
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat()
    warnings = []
    missing_sources = []
    proven_unavailable = []

    control = docker_name("control-api")
    hermes = docker_name("hermes-agent-whow", startswith=True)
    health = http_status("/healthz")
    readiness = http_status("/readyz")

    snapshot = sanitize(hermes_read(hermes, "snapshot"))
    approvals = list_payload(hermes_read(hermes, "approvals"), "approvals")
    executions = list_payload(hermes_read(hermes, "executions"), "executions")
    durable_links, durable_summary = durable_approval_execution_links(control)

    allowlist_raw = env_value(control, "PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES") or ""
    allowed_task_classes = [x.strip() for x in allowlist_raw.split(",") if x.strip()]
    if not allowed_task_classes:
        missing_sources.append("execution_allowed_task_classes")

    enforcement_mode = recursive_find(snapshot, ["execution_enforcement_mode", "enforcement_mode"])
    enforcement_scope = recursive_find(snapshot, ["execution_enforcement_scope", "enforcement_scope"])
    if enforcement_mode is None:
        enforcement_mode = "unavailable"
        proven_unavailable.append("execution_enforcement_mode")
        warnings.append("execution_enforcement_mode not exposed by current authoritative read sources")
    if enforcement_scope is None:
        enforcement_scope = "unavailable"
        proven_unavailable.append("execution_enforcement_scope")
        warnings.append("execution_enforcement_scope not exposed by current authoritative read sources")

    kill_switch_raw = env_value(control, "PHIL_AI_OS_EXECUTION_KILL_SWITCH")
    kill_switch_state = bool_state(kill_switch_raw)
    if kill_switch_raw is None:
        missing_sources.append("execution_kill_switch")

    snapshot_generated_at = recursive_find(snapshot, ["timestamp", "generated_at"])
    monitor_state = state_of_unit("phil-ai-os-monitor.service")
    backup_state = state_of_unit("phil-ai-os-backup.timer")
    self_heal_state = state_of_unit("phil-ai-os-backup-self-heal.timer")

    tasks, correlation_quality, legacy_record_count = canonical_tasks(approvals, executions)
    if correlation_quality == "legacy":
        warnings.append("recent approval/execution records are legacy because no canonical task_id is present")
    elif correlation_quality == "none":
        warnings.append("recent API history has no records for canonical task correlation; durable approval_id linkage is shown separately")
    warnings.append("canonical task persistence is absent; durable approval-to-execution linkage uses approval_id and is not a task_id")

    active_task_ids = {t["task_id"] for t in tasks if t.get("lifecycle_state") not in {"SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED", "DENIED", "EXPIRED", "CLOSED"}}
    hermes_task = next(iter(active_task_ids), None) if len(active_task_ids) == 1 else None
    hermes_lifecycle = "IDLE" if not active_task_ids else "ASSIGNED" if hermes_task else "ACTIVE_MULTIPLE"

    agents = [
        {"agent_id":"human-ceo","display_name":"Human Operator / CEO","role":"human_operator","owner":"CEO","authority_level":"L4","status":"active","lifecycle_state":"AVAILABLE","current_task_id":None,"handoff_from":None,"handoff_to":None,"credential_binding":"operator-authentication","allowed_task_classes":["policy","approval","governance"],"can_self_approve":False,"last_seen_at":None,"provenance":"declared_operating_model"},
        {"agent_id":"cto-office","display_name":"CTO Office","role":"cto","owner":"CEO","authority_level":"L2","status":"active","lifecycle_state":"AVAILABLE","current_task_id":None,"handoff_from":None,"handoff_to":None,"credential_binding":"declared-control-plane-role","allowed_task_classes":["observe","analyze","propose","validate"],"can_self_approve":False,"last_seen_at":None,"provenance":"declared_operating_model"},
        {"agent_id":"hermes","display_name":"Hermes","role":"gateway","owner":"CEO","authority_level":"L3","status":"active","lifecycle_state":hermes_lifecycle,"current_task_id":hermes_task,"handoff_from":None,"handoff_to":None,"credential_binding":"hermes-control-api-token-mount","allowed_task_classes":allowed_task_classes,"can_self_approve":False,"last_seen_at":generated_at,"provenance":"runtime_plus_derived_task_activity"},
    ]

    critical_ok = health == "ok" and readiness == "ok" and monitor_state == "active" and backup_state == "active" and self_heal_state == "active" and allowed_task_classes == ["general"]
    model = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "overall_state": "healthy" if critical_ok else "degraded",
        "platform": {"control_api_health":health,"control_api_readiness":readiness,"monitoring_state":monitor_state,"snapshot_generated_at":snapshot_generated_at,"snapshot_age_seconds":None,"snapshot":snapshot},
        "governance": {
            "execution_allowed_task_classes": allowed_task_classes,
            "execution_enforcement_mode": enforcement_mode,
            "execution_enforcement_scope": enforcement_scope,
            "kill_switch_state": kill_switch_state,
            "human_approval_required": True,
            "direct_provider_bypass_allowed": False,
            "authority_expansion_state": "blocked",
            "provenance": {
                "execution_allowed_task_classes":"control_api_container_env",
                "execution_enforcement_mode":"authoritative_source_unavailable" if enforcement_mode == "unavailable" else "mission_control_snapshot",
                "execution_enforcement_scope":"authoritative_source_unavailable" if enforcement_scope == "unavailable" else "mission_control_snapshot",
                "kill_switch_state":"control_api_container_env" if kill_switch_raw is not None else "unavailable",
                "human_approval_required":"governance_contract",
                "direct_provider_bypass_allowed":"governance_contract",
                "authority_expansion_state":"governance_contract"
            }
        },
        "agents": agents,
        "tasks": tasks,
        "approvals": approvals,
        "executions": executions,
        "durable_correlations": durable_links,
        "durable_correlation_summary": durable_summary,
        "recovery": {"backup_timer_state":backup_state,"backup_self_heal_state":self_heal_state,"latest_backup_status":"unknown","latest_backup_at":None,"restore_validation_status":"validated","monitoring_independent_of_ui":True},
        "data_quality": {
            "freshness":"fresh" if critical_ok else "unknown",
            "partial": bool(proven_unavailable or missing_sources or correlation_quality != "canonical" or durable_summary.get("canonical_task_persistence") != "present"),
            "missing_sources": missing_sources,
            "proven_unavailable": proven_unavailable,
            "correlation_quality": correlation_quality,
            "durable_link_quality": "approval_id_authoritative",
            "canonical_task_persistence": durable_summary.get("canonical_task_persistence"),
            "legacy_record_count": legacy_record_count,
            "warnings": warnings
        }
    }
    print(json.dumps(model, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"schema_version":SCHEMA_VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"overall_state":"unknown","error":str(exc),"data_quality":{"freshness":"unknown","partial":True,"missing_sources":["operator_read_model_generation"],"proven_unavailable":[],"correlation_quality":"unknown","durable_link_quality":"unknown","warnings":["read model generation failed visibly"]}}, indent=2, sort_keys=True))
        sys.exit(1)
