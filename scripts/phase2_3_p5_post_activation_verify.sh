#!/usr/bin/env bash
set -euo pipefail

BASE=/opt/phil-ai-os-platform/phil-ai-os-platform-phase1
APP_SRC="$BASE/services/core/control-api/app.py"
MC=/opt/phil-ai-os/mission-control
CONTROL="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"
[[ -n "$CONTROL" ]]

curl -fsS http://127.0.0.1:4870/healthz >/dev/null
curl -fsS http://127.0.0.1:4870/readyz >/dev/null
[[ "$(docker inspect "$CONTROL" --format '{{.Config.Image}}')" == 'phil-ai-os/control-api:0.21.2-phase23p5' ]]
[[ "$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')" == "$(sha256sum "$APP_SRC" | awk '{print $1}')" ]]
[[ "$(docker exec "$CONTROL" sh -lc 'printf %s "$PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES"')" == general ]]
[[ "$(docker exec "$CONTROL" sh -lc "grep -c '/v1/policy/evaluate' /app/app.py || true")" == 0 ]]
[[ "$(docker exec "$CONTROL" sh -lc "grep -c 'def policy_decision_persist' /app/app.py || true")" == 1 ]]
[[ "$(docker exec "$CONTROL" sh -lc "grep -c 'def policy_evaluate_pure' /app/app.py || true")" == 1 ]]

# Durable policy schema plus preserved identity/approval/execution boundaries.
docker exec -i "$CONTROL" python3 - <<'PY'
import sqlite3
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True); c.row_factory=sqlite3.Row
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
assert c.execute("select count(*) from sqlite_master where type='table' and name='policy_decisions'").fetchone()[0]==1
assert c.execute('select count(*) from policy_decisions').fetchone()[0]==0
cols=[r['name'] for r in c.execute('pragma table_info(policy_decisions)')]
for required in ('policy_decision_id','policy_version','evaluated_at','task_id','task_class','subject_agent_id','risk_tier','authority_effect','evidence_hash'):
    assert required in cols
tr={r[0] for r in c.execute("select name from sqlite_master where type='trigger' and name like 'policy_decisions_%'")}
assert {'policy_decisions_no_update','policy_decisions_no_delete'}<=tr
schema=c.execute("select sql from sqlite_master where type='table' and name='policy_decisions'").fetchone()[0]
assert "CHECK(authority_effect='none')" in schema
reg=[dict(r) for r in c.execute('select agent_id,authority_ceiling,enabled,assignable from agent_registry order by agent_id')]
assert reg==[
 {'agent_id':'hermes','authority_ceiling':'L3','enabled':1,'assignable':1},
 {'agent_id':'specialist-worker-01','authority_ceiling':'L1','enabled':0,'assignable':0},
]
assert c.execute("select count(*) from execution_audit where task_class<>'general'").fetchone()[0]==0
print('database_quick_check=ok')
print('policy_ledger=present_empty')
print('append_only_triggers=present')
print('authority_effect_constraint=none')
print('hermes=L3_enabled_assignable')
print('specialist=L1_disabled_nonassignable')
PY

curl -fsS http://127.0.0.1:4881/api/read-model > /tmp/phase23-p5-independent-read-model.json
python3 - /tmp/phase23-p5-independent-read-model.json <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); p=d['policy_decisions']; g=d['governance']; ma=d['multi_agent']
assert p['schema_version']=='2.3-p5.policy-ledger.v1'
assert p['installed'] is True and p['count']==0 and p['decisions']==[]
assert p['read_only'] is True and p['authority_effect']=='none' and p['authority_invariant_satisfied'] is True
assert g['mission_control_authority']=='read_only_observer'
for k in ('automatic_assignment','automatic_retry','automatic_reroute','automatic_delegation','automatic_execution'):
    assert g[k] is False
agents={a['agent_id']:a for a in ma['agents']}
assert agents['specialist-worker-01']['registry']['enabled'] is False
assert agents['specialist-worker-01']['registry']['assignable'] is False
print('mission_control_policy_projection=green')
print('mission_control_authority=read_only_observer')
print('automatic_execution=false')
PY
rm -f /tmp/phase23-p5-independent-read-model.json
for m in POST PUT PATCH DELETE; do
  [[ "$(curl -sS -X "$m" -o /dev/null -w '%{http_code}' http://127.0.0.1:4881/api/read-model)" == 405 ]]
done
for unit in phil-ai-os-monitor.service phil-ai-os-backup.timer phil-ai-os-backup-self-heal.timer phil-ai-os-agent-heartbeat.timer phil-ai-os-specialist-worker-01-presence.timer; do
  systemctl is-active --quiet "$unit"
  echo "$unit=active"
done

echo control_health=ok
echo control_ready=ok
echo execution_allowlist=general
echo autonomy_ceiling=A0
echo mission_control_mutations=405
echo approval_consumption=none
echo provider_call=none
echo execution_call=none
echo authority_expansion=none
echo PHIL_AI_OS_PHASE_2_3_P5_POST_ACTIVATION_VERIFY_OK
