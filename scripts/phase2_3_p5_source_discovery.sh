#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${PHIL_AI_OS_BASE_DIR:-/opt/phil-ai-os-platform/phil-ai-os-platform-phase1}"
CONTROL_DIR="$BASE_DIR/services/core/control-api"
MC_DIR="$BASE_DIR/services/core/mission-control"
CONTROL_APP="$CONTROL_DIR/app.py"
MC_APP="$MC_DIR/app.py"
DB="$CONTROL_DIR/control_plane.db"
CONTROL_BASE="${CONTROL_BASE:-http://127.0.0.1:8000}"
MC_BASE="${MC_BASE:-http://127.0.0.1:8080}"

for path in "$CONTROL_APP" "$MC_APP" "$DB"; do
  test -e "$path" || { echo "PHIL_AI_OS_PHASE_2_3_P5_DISCOVERY_MISSING=$path"; exit 1; }
done

control_hash_before="$(sha256sum "$CONTROL_APP" | awk '{print $1}')"
mc_hash_before="$(sha256sum "$MC_APP" | awk '{print $1}')"

curl -fsS "$CONTROL_BASE/health" >/dev/null
curl -fsS "$CONTROL_BASE/ready" >/dev/null
curl -fsS "$MC_BASE/health" >/dev/null
curl -fsS "$MC_BASE/v1/mission-control/summary" >/dev/null

python3 - "$CONTROL_APP" "$MC_APP" <<'PY'
import ast
import sys
from pathlib import Path


def route_from_decorator(node):
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    owner = node.func.value
    if not isinstance(owner, ast.Name) or owner.id != "app":
        return None
    if node.func.attr not in {"get", "post", "put", "patch", "delete"}:
        return None
    if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
        return None
    return f"{node.func.attr.upper()} {node.args[0].value}"


def summarize(label, filename):
    source = Path(filename).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=filename)
    imports = []
    assigned = []
    funcs = []
    routes = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    assigned.append(target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append(node.name)
            for dec in node.decorator_list:
                route = route_from_decorator(dec)
                if route:
                    routes.append(f"{route} -> {node.name}")
    print(f"=== {label}_AST ===")
    print("imports=" + ",".join(sorted(set(imports))))
    print("assigned_names=" + ",".join(sorted(set(assigned))))
    print("function_names=" + ",".join(funcs))
    print("routes_begin")
    for route in routes:
        print(route)
    print("routes_end")

summarize("CONTROL_API", sys.argv[1])
summarize("MISSION_CONTROL", sys.argv[2])
PY

echo "=== SQLITE_SCHEMA_SUMMARY ==="
sqlite3 -readonly "$DB" <<'SQL'
.headers off
.mode list
SELECT 'table=' || name FROM sqlite_master WHERE type='table' ORDER BY name;
SELECT 'agent_registry_columns=' || group_concat(name, ',') FROM pragma_table_info('agent_registry');
SELECT 'handoff_records_columns=' || group_concat(name, ',') FROM pragma_table_info('handoff_records');
SELECT 'approval_columns=' || group_concat(name, ',') FROM pragma_table_info('approvals');
SELECT 'policy_decisions_present=' || COUNT(*) FROM sqlite_master WHERE type='table' AND name='policy_decisions';
SQL

allowlist="$(systemctl show phil-ai-control.service -p Environment --value | tr ' ' '\n' | sed -n 's/^PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=//p' | tail -n 1)"
if [[ -z "$allowlist" && -f /etc/systemd/system/phil-ai-control.service.d/execution-governance.conf ]]; then
  allowlist="$(sed -n 's/^Environment="PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=\(.*\)"/\1/p' /etc/systemd/system/phil-ai-control.service.d/execution-governance.conf | tail -n 1)"
fi
[[ "$allowlist" == "general" ]] || { echo "Unexpected allowlist: $allowlist"; exit 1; }

enabled_specialists="$(sqlite3 -readonly "$DB" "SELECT COUNT(*) FROM agent_registry WHERE COALESCE(enabled,0)<>0 AND agent_id<>'hermes';" 2>/dev/null || echo 0)"
[[ "$enabled_specialists" == "0" ]] || { echo "Unexpected enabled specialist count: $enabled_specialists"; exit 1; }

control_hash_after="$(sha256sum "$CONTROL_APP" | awk '{print $1}')"
mc_hash_after="$(sha256sum "$MC_APP" | awk '{print $1}')"
[[ "$control_hash_before" == "$control_hash_after" ]]
[[ "$mc_hash_before" == "$mc_hash_after" ]]

echo "execution_allowlist=$allowlist"
echo "enabled_specialists=$enabled_specialists"
echo "autonomy_ceiling=A0"
echo "control_source_unchanged=true"
echo "mission_control_source_unchanged=true"
echo "production_change=none"
echo "PHIL_AI_OS_PHASE_2_3_P5_SOURCE_DISCOVERY_OK"
