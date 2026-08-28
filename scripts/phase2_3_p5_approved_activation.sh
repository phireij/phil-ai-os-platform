#!/usr/bin/env bash
set -euo pipefail

AUTHORIZATION="${PHIL_AI_OS_P5_AUTHORIZATION:-}"
[[ "$AUTHORIZATION" == "APPROVE_PHASE_2_3_P5" ]] || { echo 'P5 authorization missing or invalid'; exit 2; }
[[ "$(id -u)" == "0" ]] || { echo 'P5 activation requires root'; exit 2; }

BASE=/opt/phil-ai-os-platform/phil-ai-os-platform-phase1
COMPOSE_DIR="$BASE/infrastructure/core"
COMPOSE="$COMPOSE_DIR/compose.yml"
BUILD_CTX="$BASE/services/core/control-api"
APP_SRC="$BUILD_CTX/app.py"
MC=/opt/phil-ai-os/mission-control
MC_READ="$MC/read-model.py"
MC_SERVER="$MC/server.py"
PATCH_CONTROL=${1:-/tmp/phase2_3_p5_patch_control_api.py}
PATCH_MC=${2:-/tmp/phase2_3_p5_patch_read_model.py}
OLD_IMAGE='phil-ai-os/control-api:0.21.1-phase22a68'
NEW_IMAGE='phil-ai-os/control-api:0.21.2-phase23p5'
CONTROL="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"

for p in "$COMPOSE" "$APP_SRC" "$MC_READ" "$MC_SERVER" "$PATCH_CONTROL" "$PATCH_MC"; do test -f "$p"; done
[[ -n "$CONTROL" ]]

# P4-equivalent protected preflight.
curl -fsS http://127.0.0.1:4870/healthz >/dev/null
curl -fsS http://127.0.0.1:4870/readyz >/dev/null
[[ "$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:4881/api/read-model)" == 200 ]]
for m in POST PUT PATCH DELETE; do
  [[ "$(curl -sS -X "$m" -o /dev/null -w '%{http_code}' http://127.0.0.1:4881/api/read-model)" == 405 ]]
done
for unit in phil-ai-os-monitor.service phil-ai-os-backup.timer phil-ai-os-backup-self-heal.timer phil-ai-os-agent-heartbeat.timer phil-ai-os-specialist-worker-01-presence.timer; do
  systemctl is-active --quiet "$unit"
done
[[ "$(docker inspect "$CONTROL" --format '{{.Config.Image}}')" == "$OLD_IMAGE" ]]
[[ "$(docker exec "$CONTROL" sh -lc 'printf %s "$PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES"')" == general ]]
LIVE_SHA="$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')"
HOST_SHA="$(sha256sum "$APP_SRC" | awk '{print $1}')"
[[ "$LIVE_SHA" == "$HOST_SHA" ]]
MC_SHA="$(sha256sum "$MC_READ" | awk '{print $1}')"
MC_SERVER_SHA="$(sha256sum "$MC_SERVER" | awk '{print $1}')"
KILL_BEFORE="$(docker exec "$CONTROL" sh -lc 'printf %s "$PHIL_AI_OS_EXECUTION_KILL_SWITCH"')"

BASELINE="$(docker exec -i "$CONTROL" python3 - <<'PY'
import json,sqlite3
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True); c.row_factory=sqlite3.Row
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
assert c.execute("select count(*) from sqlite_master where type='table' and name='policy_decisions'").fetchone()[0]==0
tracked=['agent_registry','approval_requests','execution_audit','usage_ledger','task_lifecycle_events','task_handoffs','route_policies']
counts={t:c.execute(f'select count(*) from {t}').fetchone()[0] for t in tracked}
reg=[dict(r) for r in c.execute('select agent_id,authority_ceiling,enabled,assignable from agent_registry order by agent_id')]
assert reg==[
 {'agent_id':'hermes','authority_ceiling':'L3','enabled':1,'assignable':1},
 {'agent_id':'specialist-worker-01','authority_ceiling':'L1','enabled':0,'assignable':0},
]
print(json.dumps({'counts':counts,'registry':reg},sort_keys=True,separators=(',',':')))
PY
)"
echo p5_preflight=green
echo execution_allowlist=general
echo autonomy_ceiling=A0
echo specialist_execution_enabled=false
echo policy_decisions_prechange=absent

# Fresh backup and exact rollback snapshot.
systemctl start phil-ai-os-backup.service
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ROLLBACK_DIR="/var/lib/phil-ai-os/rollback/phase23-p5-$STAMP"
install -d -m 700 "$ROLLBACK_DIR"
cp -a "$APP_SRC" "$ROLLBACK_DIR/app.py.host-before"
cp -a "$COMPOSE" "$ROLLBACK_DIR/compose.yml.before"
cp -a "$MC_READ" "$ROLLBACK_DIR/read-model.py.before"
docker cp "$CONTROL":/app/app.py "$ROLLBACK_DIR/app.py.live-before"
docker exec -i "$CONTROL" python3 - <<'PY'
import sqlite3
src=sqlite3.connect('/app/state/control-plane.db')
dst=sqlite3.connect('/tmp/phase23-p5-prechange.db')
src.backup(dst); dst.close(); src.close()
PY
docker cp "$CONTROL":/tmp/phase23-p5-prechange.db "$ROLLBACK_DIR/control-plane.db.before"
docker exec "$CONTROL" rm -f /tmp/phase23-p5-prechange.db
chmod 600 "$ROLLBACK_DIR/control-plane.db.before"
STATE_SOURCE="$(docker inspect "$CONTROL" --format '{{range .Mounts}}{{if eq .Destination "/app/state"}}{{.Source}}{{end}}{{end}}')"
[[ -n "$STATE_SOURCE" ]]
DB_HOST_PATH="$STATE_SOURCE/control-plane.db"
DB_UID="$(stat -c %u "$DB_HOST_PATH")"; DB_GID="$(stat -c %g "$DB_HOST_PATH")"; DB_MODE="$(stat -c %a "$DB_HOST_PATH")"
printf '%s\n' "$BASELINE" > "$ROLLBACK_DIR/protected-baseline.json"
printf '%s\n' "$LIVE_SHA" > "$ROLLBACK_DIR/app.live.sha256"
printf '%s\n' "$MC_SHA" > "$ROLLBACK_DIR/read-model.sha256"
echo rollback_snapshot="$ROLLBACK_DIR"
echo rollback_armed=true

# Isolated candidate validation against a transactionally consistent DB copy.
WORK="$(mktemp -d /tmp/phase23-p5.XXXXXX)"
cleanup(){ rm -rf "$WORK"; }
trap cleanup EXIT
docker cp "$CONTROL":/app/app.py "$WORK/app.py"
cp "$MC_READ" "$WORK/read-model.py"
mkdir -p "$WORK/state" "$WORK/secrets"
cp "$ROLLBACK_DIR/control-plane.db.before" "$WORK/state/control-plane.db"
printf '%s\n' 'phase23-p5-isolated-token' > "$WORK/secrets/hermes_control_api_token"
chmod 600 "$WORK/secrets/hermes_control_api_token"
python3 "$PATCH_CONTROL" "$WORK/app.py"
python3 "$PATCH_MC" "$WORK/read-model.py"
python3 -m py_compile "$WORK/app.py" "$WORK/read-model.py"
PATCHED_APP_SHA="$(sha256sum "$WORK/app.py" | awk '{print $1}')"
PATCHED_MC_SHA="$(sha256sum "$WORK/read-model.py" | awk '{print $1}')"
[[ "$PATCHED_APP_SHA" != "$LIVE_SHA" && "$PATCHED_MC_SHA" != "$MC_SHA" ]]

PHIL_AI_OS_STATE_DIR="$WORK/state" PHIL_AI_OS_SECRETS_DIR="$WORK/secrets" PHIL_AI_OS_RUNTIME_STATE_DIR="$COMPOSE_DIR/runtime/state" \
PHIL_AI_OS_ROUTED_EXECUTION_ENABLED=false PHIL_AI_OS_LIVE_TEST_ENABLED=false PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=general \
python3 - "$WORK/app.py" <<'PY'
import importlib.util,os,sqlite3,sys,datetime
spec=importlib.util.spec_from_file_location('p5candidate',sys.argv[1]); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.init_db()
evidence={
 'task_id':'tsk_p5_isolated','task_class':'general','action_type':'read_only_prepare','subject_agent_id':'hermes',
 'subject_authority_ceiling':'L3','risk_tier':'R0','required_authority':'L1','configured_autonomy_ceiling':'A0',
 'requested_autonomy_level':'A0','human_approval_required':False,'approval_consumption_required':False,
 'scope_constraints':{'validation':'isolated'},'evidence_refs':['p5-isolated-copy'],'evidence_complete':True,
 'requested_execution':False,'requested_side_effect':False,'direct_provider_bypass':False,
 'mission_control_mutation_as_authority':False,'readiness_as_permission':False,'authority_ceiling_as_permission':False,
}
d=m.policy_evaluate_pure(evidence,datetime.datetime(2026,8,28,tzinfo=datetime.timezone.utc))
assert d['decision']=='allow_prepare' and d['authority_effect']=='none'
r=m.policy_decision_persist(d); assert r['authority_effect']=='none'
c=sqlite3.connect(os.path.join(os.environ['PHIL_AI_OS_STATE_DIR'],'control-plane.db'))
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
assert c.execute('select count(*) from policy_decisions').fetchone()[0]==1
assert c.execute('select authority_effect from policy_decisions').fetchone()[0]=='none'
for sql in ("update policy_decisions set decision='deny'","delete from policy_decisions"):
    try:
        c.execute(sql); c.commit(); raise AssertionError('append-only trigger failed')
    except sqlite3.IntegrityError as e:
        assert 'append_only' in str(e); c.rollback()
try:
    c.execute("update policy_decisions set authority_effect='grant'"); c.commit(); raise AssertionError('authority constraint failed')
except sqlite3.IntegrityError:
    c.rollback()
print('isolated_policy_evaluator=green')
print('isolated_persistence_helper=green')
print('isolated_append_only=green')
print('isolated_authority_effect=none')
PY

python3 "$WORK/read-model.py" > "$WORK/read-model-before.json"
python3 - "$WORK/read-model-before.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); p=d['policy_decisions']
assert p['schema_version']=='2.3-p5.policy-ledger.v1'
assert p['installed'] is False and p['count']==0 and p['decisions']==[]
assert p['read_only'] is True and p['authority_effect']=='none' and p['authority_invariant_satisfied'] is True
print('isolated_read_model_backward_compatibility=green')
PY
echo isolated_candidate_validation=green

# Automatic containment begins before the first approved production mutation.
MUTATED=0
rollback(){
  rc=$?
  if [[ "$MUTATED" == 1 ]]; then
    set +e
    echo rollback_attempted=true
    cp -a "$ROLLBACK_DIR/app.py.host-before" "$APP_SRC"
    cp -a "$ROLLBACK_DIR/compose.yml.before" "$COMPOSE"
    install -m 644 -o root -g root "$ROLLBACK_DIR/read-model.py.before" "$MC_READ"
    cd "$COMPOSE_DIR"
    docker compose stop control-api >/dev/null 2>&1
    cp "$ROLLBACK_DIR/control-plane.db.before" "$DB_HOST_PATH"
    chown "$DB_UID:$DB_GID" "$DB_HOST_PATH"; chmod "$DB_MODE" "$DB_HOST_PATH"
    rm -f "$DB_HOST_PATH-wal" "$DB_HOST_PATH-shm"
    docker compose up -d --no-deps --force-recreate control-api >/dev/null 2>&1
    for _ in $(seq 1 50); do curl -fsS http://127.0.0.1:4870/healthz >/dev/null 2>&1 && break; sleep 1; done
    curl -fsS http://127.0.0.1:4870/healthz >/dev/null 2>&1
    echo rollback_completed=true
  fi
  exit "$rc"
}
trap rollback ERR

# APPROVED P5 mutation: app/schema support + read-only projection only.
MUTATED=1
cp "$WORK/app.py" "$APP_SRC"
install -m 644 -o root -g root "$WORK/read-model.py" "$MC_READ.p5-new"
mv -f "$MC_READ.p5-new" "$MC_READ"
python3 - "$COMPOSE" "$OLD_IMAGE" "$NEW_IMAGE" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); old=sys.argv[2]; new=sys.argv[3]
t=p.read_text(); needle='image: '+old
assert t.count(needle)==1,t.count(needle)
p.write_text(t.replace(needle,'image: '+new,1))
PY
cd "$COMPOSE_DIR"
docker compose config >/dev/null
docker compose build control-api
docker image inspect "$NEW_IMAGE" >/dev/null
docker compose up -d --no-deps --force-recreate control-api
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:4870/healthz >/dev/null 2>&1 && curl -fsS http://127.0.0.1:4870/readyz >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS http://127.0.0.1:4870/healthz >/dev/null
curl -fsS http://127.0.0.1:4870/readyz >/dev/null
CONTROL_NEW="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"; [[ -n "$CONTROL_NEW" ]]
[[ "$(docker inspect "$CONTROL_NEW" --format '{{.Config.Image}}')" == "$NEW_IMAGE" ]]
[[ "$(docker exec "$CONTROL_NEW" sha256sum /app/app.py | awk '{print $1}')" == "$PATCHED_APP_SHA" ]]
[[ "$(sha256sum "$APP_SRC" | awk '{print $1}')" == "$PATCHED_APP_SHA" ]]
[[ "$(sha256sum "$MC_READ" | awk '{print $1}')" == "$PATCHED_MC_SHA" ]]
[[ "$(sha256sum "$MC_SERVER" | awk '{print $1}')" == "$MC_SERVER_SHA" ]]
[[ "$(docker exec "$CONTROL_NEW" sh -lc 'printf %s "$PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES"')" == general ]]
[[ "$(docker exec "$CONTROL_NEW" sh -lc 'printf %s "$PHIL_AI_OS_EXECUTION_KILL_SWITCH"')" == "$KILL_BEFORE" ]]
[[ "$(docker exec "$CONTROL_NEW" sh -lc "grep -c '/v1/policy/evaluate' /app/app.py || true")" == 0 ]]

# Live schema and append-only enforcement proof; probe transaction is rolled back.
docker exec -i "$CONTROL_NEW" python3 - <<'PY'
import sqlite3,datetime
c=sqlite3.connect('/app/state/control-plane.db')
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
assert c.execute("select count(*) from sqlite_master where type='table' and name='policy_decisions'").fetchone()[0]==1
assert c.execute('select count(*) from policy_decisions').fetchone()[0]==0
tr={r[0] for r in c.execute("select name from sqlite_master where type='trigger' and name like 'policy_decisions_%'")}
assert {'policy_decisions_no_update','policy_decisions_no_delete'}<=tr
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
vals=('pdec_p5_live_probe','2.3-p3.v1',now,'tsk_probe','general','read_only_prepare','hermes','L3','R0','L1','A0','A0',0,None,None,None,0,'{}','[]','allow_prepare','["live_probe"]',0,'none','sha256:probe')
c.execute('BEGIN IMMEDIATE')
c.execute('insert into policy_decisions values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',vals)
for sql in ("update policy_decisions set decision='deny' where policy_decision_id='pdec_p5_live_probe'","delete from policy_decisions where policy_decision_id='pdec_p5_live_probe'"):
    try:
        c.execute(sql); raise AssertionError('append-only enforcement failed')
    except sqlite3.IntegrityError as e:
        assert 'append_only' in str(e)
c.rollback()
assert c.execute('select count(*) from policy_decisions').fetchone()[0]==0
bad=list(vals); bad[-2]='grant'
try:
    c.execute('insert into policy_decisions values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',bad); c.commit(); raise AssertionError('authority effect constraint failed')
except sqlite3.IntegrityError:
    c.rollback()
assert c.execute('select count(*) from policy_decisions').fetchone()[0]==0
print('live_policy_ledger=present_empty')
print('live_append_only_enforcement=verified')
print('live_authority_effect_constraint=none')
PY

# Mission Control read-only projection and inherited governance invariants.
curl -fsS http://127.0.0.1:4881/api/read-model > "$WORK/read-model-after.json"
python3 - "$WORK/read-model-after.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); p=d['policy_decisions']; ma=d['multi_agent']; g=d['governance']
assert p['installed'] is True and p['count']==0 and p['decisions']==[] and p['read_only'] is True
assert p['authority_effect']=='none' and p['authority_invariant_satisfied'] is True
agents={a['agent_id']:a for a in ma['agents']}
assert agents['hermes']['authority_ceiling']=='L3' and agents['hermes']['registry']['enabled'] is True and agents['hermes']['registry']['assignable'] is True
assert agents['specialist-worker-01']['authority_ceiling']=='L1' and agents['specialist-worker-01']['registry']['enabled'] is False and agents['specialist-worker-01']['registry']['assignable'] is False
assert g['mission_control_authority']=='read_only_observer' and g['automatic_execution'] is False
print('mission_control_policy_projection=green')
PY
for m in POST PUT PATCH DELETE; do
  [[ "$(curl -sS -X "$m" -o /dev/null -w '%{http_code}' http://127.0.0.1:4881/api/read-model)" == 405 ]]
done

FINAL="$(docker exec -i "$CONTROL_NEW" python3 - <<'PY'
import json,sqlite3
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True); c.row_factory=sqlite3.Row
tracked=['agent_registry','approval_requests','execution_audit','usage_ledger','task_lifecycle_events','task_handoffs','route_policies']
counts={t:c.execute(f'select count(*) from {t}').fetchone()[0] for t in tracked}
reg=[dict(r) for r in c.execute('select agent_id,authority_ceiling,enabled,assignable from agent_registry order by agent_id')]
print(json.dumps({'counts':counts,'registry':reg},sort_keys=True,separators=(',',':')))
PY
)"
[[ "$FINAL" == "$BASELINE" ]]
for unit in phil-ai-os-monitor.service phil-ai-os-backup.timer phil-ai-os-backup-self-heal.timer phil-ai-os-agent-heartbeat.timer phil-ai-os-specialist-worker-01-presence.timer; do systemctl is-active --quiet "$unit"; done

echo protected_state_unchanged=true
echo approval_consumption=none
echo provider_call=none
echo execution_call=none
echo execution_allowlist=general
echo autonomy_ceiling=A0
echo specialist_execution_enabled=false
echo mission_control_mutations=405
echo policy_authority_effect=none
echo automatic_action_introduced=false
echo rollback_invoked=false
echo PHIL_AI_OS_PHASE_2_3_P5_ACTIVATION_OK

trap - ERR
MUTATED=0
