#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${PHIL_AI_OS_BASE_DIR:-/opt/phil-ai-os-platform/phil-ai-os-platform-phase1}"
CONTROL_APP="$BASE_DIR/services/core/control-api/app.py"
MC_DIR="${PHIL_AI_OS_MC_DIR:-/opt/phil-ai-os/mission-control}"
MC_SERVER="$MC_DIR/server.py"
MC_READ_MODEL="$MC_DIR/read-model.py"
CONTROL_BASE="${CONTROL_BASE:-http://127.0.0.1:4870}"
MC_BASE="${MC_BASE:-http://127.0.0.1:4881}"
CONTROL="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"

[[ -n "$CONTROL" ]] || { echo 'PHIL_AI_OS_PHASE_2_3_P5_DISCOVERY_MISSING=control-api-container'; exit 1; }
for path in "$CONTROL_APP" "$MC_SERVER" "$MC_READ_MODEL"; do
  test -f "$path" || { echo "PHIL_AI_OS_PHASE_2_3_P5_DISCOVERY_MISSING=$path"; exit 1; }
done

control_hash_before="$(sha256sum "$CONTROL_APP" | awk '{print $1}')"
mc_server_hash_before="$(sha256sum "$MC_SERVER" | awk '{print $1}')"
mc_read_model_hash_before="$(sha256sum "$MC_READ_MODEL" | awk '{print $1}')"
live_control_hash="$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')"
[[ "$live_control_hash" == "$control_hash_before" ]] || { echo 'control_live_host_source_match=false'; exit 1; }

curl -fsS "$CONTROL_BASE/healthz" >/dev/null
curl -fsS "$CONTROL_BASE/readyz" >/dev/null
[[ "$(curl -sS -o /dev/null -w '%{http_code}' "$MC_BASE/api/read-model")" == "200" ]]

python3 - "$CONTROL_APP" "$MC_SERVER" "$MC_READ_MODEL" <<'PY'
import ast
import sys
from pathlib import Path


def summarize(label, filename):
    source = Path(filename).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=filename)
    imports, assigned, funcs, classes, paths = [], [], [], [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append(node.name)
        elif isinstance(node, ast.ClassDef):
            methods=[n.name for n in node.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
            classes.append(node.name+":"+",".join(methods))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name): assigned.append(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assigned.append(node.target.id)
        elif isinstance(node, ast.Compare):
            values=[]
            candidates=[node.left,*node.comparators]
            for c in candidates:
                if isinstance(c,ast.Constant) and isinstance(c.value,str) and c.value.startswith('/'):
                    values.append(c.value)
            paths.extend(values)
    print(f"=== {label}_AST ===")
    print("imports="+",".join(sorted(set(imports))))
    print("assigned_names="+",".join(sorted(set(assigned))))
    print("function_names="+",".join(sorted(set(funcs))))
    print("classes="+";".join(sorted(set(classes))))
    print("path_literals="+",".join(sorted(set(paths))))

summarize("CONTROL_API", sys.argv[1])
summarize("MISSION_CONTROL_SERVER", sys.argv[2])
summarize("MISSION_CONTROL_READ_MODEL", sys.argv[3])
PY

echo "=== CONTROL_SOURCE_ANCHORS ==="
for anchor in \
  'def db(' \
  'def now_iso(' \
  'def coordinator_assign(' \
  'if path=="/v1/tasks/assign":' \
  '# v0.19 approval-to-execution audit trace.' \
  'Phase 2.2 A6.7 additive inert handoff persistence'; do
  printf 'anchor_count[%s]=%s\n' "$anchor" "$(grep -F -c "$anchor" "$CONTROL_APP" || true)"
done

echo "=== MISSION_CONTROL_SOURCE_ANCHORS ==="
for target in "$MC_SERVER" "$MC_READ_MODEL"; do
  echo "file=$(basename "$target")"
  for anchor in 'mode=ro' "mission_control_authority':'read_only_observer'" '/api/read-model' 'do_GET' 'do_POST'; do
    printf 'anchor_count[%s]=%s\n' "$anchor" "$(grep -F -c "$anchor" "$target" || true)"
  done
done

echo "=== SQLITE_SCHEMA_SUMMARY ==="
docker exec -i "$CONTROL" python3 - <<'PY'
import sqlite3
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True)
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
for name in sorted(r[0] for r in c.execute("select name from sqlite_master where type='table'")):
    print('table='+name)
for table in ('agent_registry','task_handoffs','approval_requests','execution_audit'):
    cols=','.join(r[1] for r in c.execute(f'pragma table_info({table})'))
    print(f'{table}_columns={cols}')
print('policy_decisions_present='+str(c.execute("select count(*) from sqlite_master where type='table' and name='policy_decisions'").fetchone()[0]))
print('enabled_specialists='+str(c.execute("select count(*) from agent_registry where coalesce(enabled,0)<>0 and agent_id<>'hermes'").fetchone()[0]))
reg=list(c.execute('select agent_id,authority_ceiling,enabled,assignable from agent_registry order by agent_id'))
print('agent_registry='+repr(reg))
c.close()
PY

allowlist="$(docker exec "$CONTROL" sh -lc 'printf %s "$PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES"')"
[[ "$allowlist" == "general" ]] || { echo "Unexpected allowlist: $allowlist"; exit 1; }

enabled_specialists="$(docker exec -i "$CONTROL" python3 - <<'PY'
import sqlite3
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True)
print(c.execute("select count(*) from agent_registry where coalesce(enabled,0)<>0 and agent_id<>'hermes'").fetchone()[0])
PY
)"
[[ "$enabled_specialists" == "0" ]] || { echo "Unexpected enabled specialist count: $enabled_specialists"; exit 1; }

docker exec -i "$CONTROL" python3 - <<'PY'
import sqlite3
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True)
assert c.execute("select count(*) from sqlite_master where type='table' and name='policy_decisions'").fetchone()[0]==0
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
PY

for m in POST PUT PATCH DELETE; do
  [[ "$(curl -sS -X "$m" -o /dev/null -w '%{http_code}' "$MC_BASE/api/read-model")" == "405" ]]
done

control_hash_after="$(sha256sum "$CONTROL_APP" | awk '{print $1}')"
mc_server_hash_after="$(sha256sum "$MC_SERVER" | awk '{print $1}')"
mc_read_model_hash_after="$(sha256sum "$MC_READ_MODEL" | awk '{print $1}')"
[[ "$control_hash_before" == "$control_hash_after" ]]
[[ "$mc_server_hash_before" == "$mc_server_hash_after" ]]
[[ "$mc_read_model_hash_before" == "$mc_read_model_hash_after" ]]

echo "control_health=ok"
echo "control_ready=ok"
echo "mission_control_read_model=200"
echo "mission_control_mutations=405"
echo "control_live_host_source_match=true"
echo "execution_allowlist=$allowlist"
echo "enabled_specialists=$enabled_specialists"
echo "autonomy_ceiling=A0"
echo "control_source_unchanged=true"
echo "mission_control_server_unchanged=true"
echo "mission_control_read_model_unchanged=true"
echo "provider_call=none"
echo "execution_call=none"
echo "approval_consumption=none"
echo "production_change=none"
echo "PHIL_AI_OS_PHASE_2_3_P5_SOURCE_DISCOVERY_OK"
