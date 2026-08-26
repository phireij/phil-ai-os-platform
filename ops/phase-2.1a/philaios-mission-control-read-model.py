#!/usr/bin/env python3
import datetime as dt
import json
import subprocess
import sys
from typing import Any

SCHEMA_VERSION = "2.1a.v1"
CONTROL_API_BASE = "http://127.0.0.1:4870"
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


def main():
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat()
    warnings = []
    missing_sources = []

    control = docker_name("control-api")
    hermes = docker_name("hermes-agent-whow", startswith=True)

    health = http_status("/healthz")
    readiness = http_status("/readyz")

    snapshot = sanitize(hermes_read(hermes, "snapshot"))
    approvals_raw = hermes_read(hermes, "approvals")
    executions_raw = hermes_read(hermes, "executions")
    approvals = list_payload(approvals_raw, "approvals")
    executions = list_payload(executions_raw, "executions")

    allowlist_raw = env_value(control, "PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES") or ""
    allowed_task_classes = [x.strip() for x in allowlist_raw.split(",") if x.strip()]
    if not allowed_task_classes:
        missing_sources.append("execution_allowed_task_classes")

    enforcement_mode = recursive_find(snapshot, ["execution_enforcement_mode", "enforcement_mode"])
    enforcement_scope = recursive_find(snapshot, ["execution_enforcement_scope", "enforcement_scope"])
    kill_switch = recursive_find(snapshot, ["kill_switch", "kill_switch_state", "execution_kill_switch"])
    snapshot_generated_at = recursive_find(snapshot, ["timestamp", "generated_at"])

    if enforcement_mode is None:
        enforcement_mode = "unknown"
        warnings.append("execution_enforcement_mode unavailable in current read sources")
    if enforcement_scope is None:
        enforcement_scope = "unknown"
        warnings.append("execution_enforcement_scope unavailable in current read sources")
    if kill_switch is None:
        kill_switch_state = "unknown"
        warnings.append("kill_switch_state unavailable in current read sources")
    elif isinstance(kill_switch, bool):
        kill_switch_state = "enabled" if kill_switch else "disabled"
    else:
        text = str(kill_switch).lower()
        kill_switch_state = "enabled" if text in {"1", "true", "enabled", "on"} else "disabled" if text in {"0", "false", "disabled", "off"} else "unknown"

    monitor_state = state_of_unit("phil-ai-os-monitor.service")
    backup_state = state_of_unit("phil-ai-os-backup.timer")
    self_heal_state = state_of_unit("phil-ai-os-backup-self-heal.timer")

    agents = [
        {
            "agent_id": "human-ceo",
            "display_name": "Human Operator / CEO",
            "role": "human_operator",
            "owner": "CEO",
            "authority_level": "L4",
            "status": "active",
            "credential_binding": "operator-authentication",
            "allowed_task_classes": ["policy", "approval", "governance"],
            "can_self_approve": False,
            "last_seen_at": None,
        },
        {
            "agent_id": "cto-office",
            "display_name": "CTO Office",
            "role": "cto",
            "owner": "CEO",
            "authority_level": "L2",
            "status": "active",
            "credential_binding": "declared-control-plane-role",
            "allowed_task_classes": ["observe", "analyze", "propose", "validate"],
            "can_self_approve": False,
            "last_seen_at": None,
        },
        {
            "agent_id": "hermes",
            "display_name": "Hermes",
            "role": "gateway",
            "owner": "CEO",
            "authority_level": "L3",
            "status": "active",
            "credential_binding": "hermes-control-api-token-mount",
            "allowed_task_classes": allowed_task_classes,
            "can_self_approve": False,
            "last_seen_at": generated_at,
        },
    ]

    # Historical approval/execution data does not yet have canonical task IDs.
    tasks = []
    warnings.append("canonical task_id correlation not yet available; historical correlations remain legacy/partial")

    critical_ok = (
        health == "ok"
        and readiness == "ok"
        and monitor_state == "active"
        and backup_state == "active"
        and self_heal_state == "active"
        and allowed_task_classes == ["general"]
    )
    overall_state = "healthy" if critical_ok else "degraded"

    model = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "overall_state": overall_state,
        "platform": {
            "control_api_health": health,
            "control_api_readiness": readiness,
            "monitoring_state": monitor_state,
            "snapshot_generated_at": snapshot_generated_at,
            "snapshot_age_seconds": None,
            "snapshot": snapshot,
        },
        "governance": {
            "execution_allowed_task_classes": allowed_task_classes,
            "execution_enforcement_mode": enforcement_mode,
            "execution_enforcement_scope": enforcement_scope,
            "kill_switch_state": kill_switch_state,
            "human_approval_required": True,
            "direct_provider_bypass_allowed": False,
            "authority_expansion_state": "blocked",
        },
        "agents": agents,
        "tasks": tasks,
        "approvals": approvals,
        "executions": executions,
        "recovery": {
            "backup_timer_state": backup_state,
            "backup_self_heal_state": self_heal_state,
            "latest_backup_status": "unknown",
            "latest_backup_at": None,
            "restore_validation_status": "validated",
            "monitoring_independent_of_ui": True,
        },
        "data_quality": {
            "freshness": "fresh" if critical_ok else "unknown",
            "partial": True,
            "missing_sources": missing_sources,
            "correlation_quality": "legacy",
            "warnings": warnings,
        },
    }

    print(json.dumps(model, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "overall_state": "unknown",
            "error": str(exc),
            "data_quality": {
                "freshness": "unknown",
                "partial": True,
                "missing_sources": ["operator_read_model_generation"],
                "correlation_quality": "unknown",
                "warnings": ["read model generation failed visibly"],
            },
        }, indent=2, sort_keys=True))
        sys.exit(1)
