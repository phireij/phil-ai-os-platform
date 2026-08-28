#!/usr/bin/env bash
set -euo pipefail

MC=/opt/phil-ai-os/mission-control
LIVE="$MC/read-model.py"
SERVER="$MC/server.py"
CAND=/tmp/phase2_2_a7_4_multi_agent_read_model.py
CONTROL="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"
test -n "$CONTROL"
test -f "$CAND"

validate_projection() {
  local json_file="$1"
  python3 - "$json_file" <<'PY'
import json,sys
p=sys.argv[1]
d=json.load(open(p))
assert d['schema_version']=='2.2-a7.v1'
ma=d['multi_agent']
assert ma['registered_agent_count']==2
agents={a['agent_id']:a for a in ma['agents']}
assert set(agents)=={'hermes','specialist-worker-01'}
h=agents['hermes']; s=agents['specialist-worker-01']
assert h['authority_ceiling']=='L3'
assert h['registry']['enabled'] is True and h['registry']['assignable'] is True
assert h['readiness']['grants_authority'] is False
assert s['authority_ceiling']=='L1'
assert s['registry']['enabled'] is False and s['registry']['assignable'] is False
assert s['readiness']['state']=='unassignable'
assert s['readiness']['grants_authority'] is False
assert s['presence']['identity_verified'] is True
assert s['presence']['state'] in {'fresh','stale'}
assert s['workload']['active_task_count']==0
assert s['runtime']['type']=='presence_only' and s['runtime']['execution_runtime']=='none'
assert ma['handoff_count']==1
ho=ma['handoffs'][0]
assert ho['handoff_id']=='hof_ba25bd0fdfea401c9894d6520099b4cf'
assert ho['task_id']=='tsk_a68_082b86212fc944b0a45f6c43395cb6f1'
assert ho['source_agent_id']=='hermes' and ho['target_agent_id']=='specialist-worker-01'
assert ho['correlation_id']=='hofcorr_7dba30f92f2c46188c435aaea55bde67'
assert ho['required_authority']=='L1' and ho['state']=='accepted'
assert ho['handoff_approval_state']=='approved'
assert ho['task_latest_stage']=='COMPLETED'
assert ho['active_ownership'] is False
assert ho['execution_approval_consumed'] is False
assert ho['evidence_complete'] is True
g=d['governance']
assert g['mission_control_authority']=='read_only_observer'
for k in ('automatic_assignment','automatic_retry','automatic_reroute','automatic_delegation','automatic_execution'):
    assert g[k] is False
assert len(d['worker_readiness_by_agent'])==2
assert d['worker_readiness']['agent_id']=='hermes'
coord=d.get('coordinator') or {}
creg=coord.get('agent_registry') or []
assert {r['agent_id'] for r in creg}=={'hermes','specialist-worker-01'}
forbidden={'token','secret','private_key','signature_base64','authorization','bearer','api_key','provider_key'}
def walk(x):
    if isinstance(x,dict):
        for k,v in x.items():
            assert k.lower() not in forbidden,k
            walk(v)
    elif isinstance(x,list):
        for v in x: walk(v)
walk(d)
print('projection_schema=2.2-a7.v1')
print('registered_agents=2')
print('specialist_final_state=L1_disabled_nonassignable')
print('specialist_active_workload=0')
print('a6_8_handoff=accepted_historical_inactive')
print('execution_approval_consumed=false')
print('secret_exclusion=verified')
print('mission_control_authority=read_only_observer')
PY
}

capture_state() {
  docker exec -i "$CONTROL" python3 - <<'PY'
import sqlite3,json
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True); c.row_factory=sqlite3.Row
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
tables=['agent_registry','task_lifecycle_events','task_plans','approval_requests','execution_audit','usage_ledger','task_handoffs']
counts={t:c.execute(f'select count(*) from {t}').fetchone()[0] for t in tables}
reg=[dict(r) for r in c.execute('select agent_id,authority_ceiling,enabled,assignable from agent_registry order by agent_id')]
handoffs=[dict(r) for r in c.execute('select handoff_id,task_id,source_agent_id,target_agent_id,correlation_id,state,required_authority,lifecycle_event_id from task_handoffs order by requested_at,handoff_id')]
canary=[dict(r) for r in c.execute("select event_id,task_id,stage,assigned_agent_id,correlation_id from task_lifecycle_events where task_id='tsk_a68_082b86212fc944b0a45f6c43395cb6f1' order by occurred_at,event_id")]
print(json.dumps({'counts':counts,'registry':reg,'handoffs':handoffs,'canary_lifecycle':canary},sort_keys=True,separators=(',',':')))
PY
}

# Pre-mutation operational and governance checks.
curl -fsS http://127.0.0.1:4870/healthz >/dev/null
curl -fsS http://127.0.0.1:4870/readyz >/dev/null
test "$(docker exec "$CONTROL" sh -lc 'printf %s "$PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES"')" = general
for m in POST PUT PATCH DELETE; do
  test "$(curl -sS -X "$m" -o /dev/null -w '%{http_code}' http://127.0.0.1:4881/api/read-model)" = 405
done
SERVER_PID="$(pgrep -f '^/usr/bin/python3 /opt/phil-ai-os/mission-control/server.py$' | head -n1)"
test -n "$SERVER_PID"
tr '\0' '\n' < "/proc/$SERVER_PID/environ" | grep -Fx 'PHIL_AI_OS_MC_READ_MODEL=/opt/phil-ai-os/mission-control/read-model.py' >/dev/null
ss -lntp | grep -F '127.0.0.1:4881' >/dev/null
python3 -m py_compile "$CAND"

# Re-run candidate on live evidence immediately before installation.
python3 "$CAND" > /tmp/a7-preinstall-projection.json
validate_projection /tmp/a7-preinstall-projection.json

LIVE_HASH="$(sha256sum "$LIVE" | awk '{print $1}')"
SERVER_HASH="$(sha256sum "$SERVER" | awk '{print $1}')"
CONTROL_APP_HASH="$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')"
CAND_HASH="$(sha256sum "$CAND" | awk '{print $1}')"
BEFORE="$(capture_state)"
printf '%s\n' "$BEFORE" > /tmp/a7-state-before.json

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ROLLBACK_DIR="/var/lib/phil-ai-os/rollback/phase22-a7-$STAMP"
install -d -m 700 -o root -g root "$ROLLBACK_DIR"
cp -a "$LIVE" "$ROLLBACK_DIR/read-model.py"
printf '%s\n' "$LIVE_HASH" > "$ROLLBACK_DIR/read-model.py.sha256"
chmod 600 "$ROLLBACK_DIR/read-model.py.sha256"

echo rollback_snapshot="$ROLLBACK_DIR"
echo prechange_read_model_sha256="$LIVE_HASH"
echo candidate_sha256="$CAND_HASH"

MUTATED=0
rollback() {
  local rc=$?
  if [ "$MUTATED" -eq 1 ]; then
    echo rollback_attempted=true
    install -m 644 -o root -g root "$ROLLBACK_DIR/read-model.py" "$LIVE.rollback-new"
    mv -f "$LIVE.rollback-new" "$LIVE"
    test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$LIVE_HASH"
    test "$(sha256sum "$SERVER" | awk '{print $1}')" = "$SERVER_HASH"
    test "$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')" = "$CONTROL_APP_HASH"
    local after
    after="$(capture_state)"
    test "$after" = "$BEFORE"
    for m in POST PUT PATCH DELETE; do
      test "$(curl -sS -X "$m" -o /dev/null -w '%{http_code}' http://127.0.0.1:4881/api/read-model)" = 405 || true
    done
    echo rollback_completed=true
  fi
  rm -f /tmp/a7-preinstall-projection.json /tmp/a7-live-projection.json /tmp/a7-state-before.json "$CAND"
  exit "$rc"
}
trap rollback ERR

# A7.4 mutation starts: one read-only projection file only.
MUTATED=1
install -m 644 -o root -g root "$CAND" "$LIVE.a7-new"
mv -f "$LIVE.a7-new" "$LIVE"
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "$CAND_HASH"
echo read_model_atomic_install=true

# Server executes the read model per request; no restart is authorized or required.
test "$(pgrep -f '^/usr/bin/python3 /opt/phil-ai-os/mission-control/server.py$' | head -n1)" = "$SERVER_PID"
echo mission_control_server_restarted=false

# Endpoint must recover to 200 and satisfy the full read-only projection contract.
HTTP=000
for _ in 1 2 3 4 5; do
  HTTP="$(curl -sS -o /tmp/a7-live-projection.json -w '%{http_code}' http://127.0.0.1:4881/api/read-model || true)"
  [ "$HTTP" = 200 ] && break
  sleep 1
done
test "$HTTP" = 200
echo mission_control_read_model_http=200
validate_projection /tmp/a7-live-projection.json

# Durable state and protected code remain unchanged.
AFTER="$(capture_state)"
test "$AFTER" = "$BEFORE"
test "$(sha256sum "$SERVER" | awk '{print $1}')" = "$SERVER_HASH"
test "$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')" = "$CONTROL_APP_HASH"
test "$(docker exec "$CONTROL" sh -lc 'printf %s "$PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES"')" = general
curl -fsS http://127.0.0.1:4870/healthz >/dev/null
curl -fsS http://127.0.0.1:4870/readyz >/dev/null
for m in POST PUT PATCH DELETE; do
  test "$(curl -sS -X "$m" -o /dev/null -w '%{http_code}' http://127.0.0.1:4881/api/read-model)" = 405
  echo mission_control_${m}=405
done
for unit in phil-ai-os-agent-heartbeat.timer phil-ai-os-specialist-worker-01-presence.timer phil-ai-os-monitor.service phil-ai-os-backup.timer phil-ai-os-backup-self-heal.timer; do
  systemctl is-active --quiet "$unit"
  echo "$unit=active"
done

echo durable_state_unchanged=true
echo control_api_app_unchanged=true
echo server_file_unchanged=true
echo execution_allowlist=general
echo provider_call=none
echo execution_call=none
echo authority_expansion=none
echo automatic_assignment=false
echo automatic_retry=false
echo automatic_reroute=false
echo automatic_delegation=false
echo automatic_execution=false
echo rollback_armed=true
echo rollback_invoked=false
echo PHIL_AI_OS_PHASE_2_2_A7_4_READ_MODEL_INTEGRATION_OK

trap - ERR
MUTATED=0
rm -f /tmp/a7-preinstall-projection.json /tmp/a7-live-projection.json /tmp/a7-state-before.json "$CAND"
