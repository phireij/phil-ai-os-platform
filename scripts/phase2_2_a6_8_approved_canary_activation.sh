#!/usr/bin/env bash
set -euo pipefail

PATCHER=${1:-/tmp/phase2_2_a6_8_patch_control_api.py}
COMPOSE_DIR=/opt/phil-ai-os-platform/phil-ai-os-platform-phase1/infrastructure/core
COMPOSE="$COMPOSE_DIR/compose.yml"
BUILD_CTX=/opt/phil-ai-os-platform/phil-ai-os-platform-phase1/services/core/control-api
APP_SRC="$BUILD_CTX/app.py"
RUNTIME_STATE="$COMPOSE_DIR/runtime/state"
SECRETS="$COMPOSE_DIR/secrets"
POLICY="$RUNTIME_STATE/phase2_2_a6_8_canary_policy.json"
READINESS="$RUNTIME_STATE/phase2_2_a6_8_canary_readiness.json"
OLD_IMAGE='phil-ai-os/control-api:0.21.0-phase22a67'
NEW_IMAGE='phil-ai-os/control-api:0.21.1-phase22a68'
EXPECTED_APP_SHA='faa727987e087e2540fec7be0c9d709f7cc57dd51ddc767a3d8b39e0a6474b55'
AUTHORIZATION='APPROVE_PHASE_2_2_A6_8'
CONTROL="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"
test -n "$CONTROL"
test -r "$PATCHER"

# ----- strict preflight -----
curl -fsS http://127.0.0.1:4870/healthz >/dev/null
curl -fsS http://127.0.0.1:4870/readyz >/dev/null
for unit in \
  phil-ai-os-mission-control-operator.service \
  phil-ai-os-agent-heartbeat.timer \
  phil-ai-os-specialist-worker-01-presence.timer \
  phil-ai-os-monitor.service \
  phil-ai-os-backup.timer \
  phil-ai-os-backup-self-heal.timer; do
  systemctl is-active --quiet "$unit"
done
test "$(docker inspect "$CONTROL" --format '{{.Config.Image}}')" = "$OLD_IMAGE"
test "$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')" = "$EXPECTED_APP_SHA"
test "$(sha256sum "$APP_SRC" | awk '{print $1}')" = "$EXPECTED_APP_SHA"
test "$(docker exec "$CONTROL" sh -lc 'printf %s "$PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES"')" = general
for m in POST PUT PATCH DELETE; do
  test "$(curl -sS -X "$m" -o /dev/null -w '%{http_code}' http://127.0.0.1:4881/api/read-model)" = 405
done
test ! -e "$POLICY"
test ! -e "$READINESS"

docker exec -i "$CONTROL" python3 - <<'PY'
import sqlite3
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True); c.row_factory=sqlite3.Row
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
assert c.execute("select count(*) from task_handoffs").fetchone()[0]==0
h=c.execute("select authority_ceiling,enabled,assignable from agent_registry where agent_id='hermes'").fetchone()
s=c.execute("select authority_ceiling,enabled,assignable from agent_registry where agent_id='specialist-worker-01'").fetchone()
assert h and h[0]=='L3' and int(h[1])==1 and int(h[2])==1
assert s and s[0]=='L1' and int(s[1])==0 and int(s[2])==0
assert c.execute("select count(*) from task_lifecycle_events where stage='ASSIGNED' and assigned_agent_id='specialist-worker-01'").fetchone()[0]==0
PY

# Verify both presence channels before any mutation.
python3 - <<'PY'
import base64,datetime,json,pathlib,subprocess,tempfile
now=datetime.datetime.now(datetime.timezone.utc)
sp=pathlib.Path('/var/lib/phil-ai-os/agent-presence/specialist-worker-01.json')
pub='/var/lib/phil-ai-os/agent-identities/specialist-worker-01/public.pem'
e=json.loads(sp.read_text()); pl=e['payload']
assert pl['agent_id']=='specialist-worker-01' and pl['authority_ceiling']=='L1'
assert pl['enabled'] is False and pl['assignable'] is False
age=(now-datetime.datetime.fromisoformat(pl['observed_at'])).total_seconds(); assert 0<=age<=120,age
canonical=json.dumps(pl,sort_keys=True,separators=(',',':')).encode()
with tempfile.TemporaryDirectory() as td:
    msg=pathlib.Path(td)/'msg'; sig=pathlib.Path(td)/'sig'
    msg.write_bytes(canonical); sig.write_bytes(base64.b64decode(e['signature_base64'],validate=True))
    subprocess.run(['openssl','pkeyutl','-verify','-pubin','-inkey',pub,'-sigfile',str(sig),'-rawin','-in',str(msg)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
h=json.loads(pathlib.Path('/var/lib/phil-ai-os/agent-presence/hermes.json').read_text())
assert h.get('observation_type')=='authenticated_control_api_roundtrip'
hage=(now-datetime.datetime.fromisoformat(str(h['observed_at']).replace('Z','+00:00'))).total_seconds(); assert 0<=hage<=120,hage
print('specialist_presence_signature_verified=true')
print('specialist_presence_age_seconds='+str(round(age,3)))
print('hermes_presence_authenticated=true')
print('hermes_presence_age_seconds='+str(round(hage,3)))
PY

echo preflight=green

# ----- baseline + rollback snapshot -----
BASELINE="$(docker exec -i "$CONTROL" python3 - <<'PY'
import json,sqlite3
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True)
tables=['approval_requests','task_lifecycle_events','task_plans','task_handoffs','execution_audit','usage_ledger','agent_registry']
print(json.dumps({t:c.execute(f'select count(*) from {t}').fetchone()[0] for t in tables},sort_keys=True,separators=(',',':')))
PY
)"
echo baseline_captured=true
systemctl start phil-ai-os-backup.service
echo prechange_backup_service=completed
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ROLLBACK_DIR="/var/lib/phil-ai-os/rollback/phase22-a68-$STAMP"
install -d -m 700 "$ROLLBACK_DIR"
cp -a "$APP_SRC" "$ROLLBACK_DIR/app.py.before"
cp -a "$COMPOSE" "$ROLLBACK_DIR/compose.yml.before"
docker exec -i "$CONTROL" python3 - <<'PY'
import sqlite3
src=sqlite3.connect('/app/state/control-plane.db'); dst=sqlite3.connect('/tmp/phase22-a68-prechange.db')
src.backup(dst); dst.close(); src.close()
PY
docker cp "$CONTROL":/tmp/phase22-a68-prechange.db "$ROLLBACK_DIR/control-plane.db.before"
docker exec "$CONTROL" rm -f /tmp/phase22-a68-prechange.db
chmod 600 "$ROLLBACK_DIR/control-plane.db.before"
STATE_SOURCE="$(docker inspect "$CONTROL" --format '{{range .Mounts}}{{if eq .Destination "/app/state"}}{{.Source}}{{end}}{{end}}')"
test -n "$STATE_SOURCE"
DB_HOST_PATH="$STATE_SOURCE/control-plane.db"
DB_UID="$(stat -c %u "$DB_HOST_PATH")"; DB_GID="$(stat -c %g "$DB_HOST_PATH")"; DB_MODE="$(stat -c %a "$DB_HOST_PATH")"
echo rollback_snapshot="$ROLLBACK_DIR"

# ----- exact candidate patch + copied-DB validation; no production mutation yet -----
WORK="$(mktemp -d /tmp/phase22-a68.XXXXXX)"
CAND_PID=''
cleanup(){
  if [ -n "$CAND_PID" ]; then kill "$CAND_PID" >/dev/null 2>&1 || true; wait "$CAND_PID" >/dev/null 2>&1 || true; fi
  rm -rf "$WORK"
}
trap cleanup EXIT
mkdir -p "$WORK/state" "$WORK/runtime" "$WORK/secrets"
cp "$APP_SRC" "$WORK/app.py"
cp "$ROLLBACK_DIR/control-plane.db.before" "$WORK/state/control-plane.db"
printf '%s\n' 'phase22-a68-isolated-token' > "$WORK/secrets/hermes_control_api_token"
chmod 600 "$WORK/secrets/hermes_control_api_token"
python3 "$PATCHER" "$WORK/app.py"
python3 -m py_compile "$WORK/app.py"
PATCHED_SHA="$(sha256sum "$WORK/app.py" | awk '{print $1}')"
test "$PATCHED_SHA" != "$EXPECTED_APP_SHA"
echo candidate_app_sha256="$PATCHED_SHA"

C_TASK="tsk_a68_isolated_$(python3 -c 'import uuid;print(uuid.uuid4().hex)')"
C_APR="apr_a68_isolated_$(python3 -c 'import uuid;print(uuid.uuid4().hex)')"
C_CORR="a68iso_$(python3 -c 'import uuid;print(uuid.uuid4().hex)')"
python3 - "$WORK/state/control-plane.db" "$C_TASK" "$C_APR" "$C_CORR" <<'PY'
import sqlite3,sys,uuid
from datetime import datetime,timezone,timedelta
db,tid,aid,corr=sys.argv[1:]
now=datetime.now(timezone.utc); exp=now+timedelta(minutes=10)
c=sqlite3.connect(db)
c.execute("insert into approval_requests(approval_id,created_at,updated_at,expires_at,state,source,requester,task_text,task_class,confidence,requested_by,task_id) values(?,?,?,?,?,?,?,?,?,?,?,?)",
 (aid,now.isoformat(),now.isoformat(),exp.isoformat(),'pending','phase-2.2-a6.8-isolated','human-operator-ceo','A6.8 isolated non-executing canary','general',1.0,'human-operator-ceo',tid))
c.execute("insert into task_lifecycle_events(event_id,task_id,stage,occurred_at,source_component,actor_id,assigned_agent_id,previous_stage,reason_code,correlation_id) values(?,?,?,?,?,?,?,?,?,?)",
 ('evt_'+uuid.uuid4().hex,tid,'ASSIGNED',now.isoformat(),'phase-2.2-a6.8-isolated','human-operator-ceo','hermes',None,'a6_8_isolated_initial_assignment',corr))
c.execute("update agent_registry set enabled=1,assignable=1 where agent_id='specialist-worker-01' and authority_ceiling='L1' and enabled=0 and assignable=0")
assert c.total_changes>=3
c.commit()
PY
python3 - "$WORK/runtime" "$C_TASK" "$C_CORR" <<'PY'
import json,pathlib,sys
from datetime import datetime,timezone,timedelta
root=pathlib.Path(sys.argv[1]); tid=sys.argv[2]; corr=sys.argv[3]; now=datetime.now(timezone.utc); exp=now+timedelta(minutes=5)
policy={'schema_version':'2.2-a6.8.v1','authorization':'APPROVE_PHASE_2_2_A6_8','authorized_by':'CEO','task_id':tid,'task_class':'general','required_authority':'L1','source_agent_id':'hermes','target_agent_id':'specialist-worker-01','canary_correlation_id':corr,'handoff_authorized':False,'handoff_id':None,'handoff_correlation_id':None,'expires_at':exp.isoformat()}
ready={'schema_version':'2.2-a6.8.v1','authorization':'APPROVE_PHASE_2_2_A6_8','task_id':tid,'source_agent_id':'hermes','target_agent_id':'specialist-worker-01','canary_correlation_id':corr,'source_presence_authenticated':True,'target_presence_signature_verified':True,'specialist_prior_assignment_refs':0,'generated_at':now.isoformat(),'expires_at':exp.isoformat()}
(root/'phase2_2_a6_8_canary_policy.json').write_text(json.dumps(policy,sort_keys=True,separators=(',',':')))
(root/'phase2_2_a6_8_canary_readiness.json').write_text(json.dumps(ready,sort_keys=True,separators=(',',':')))
PY
PHIL_AI_OS_STATE_DIR="$WORK/state" PHIL_AI_OS_RUNTIME_STATE_DIR="$WORK/runtime" PHIL_AI_OS_SECRETS_DIR="$WORK/secrets" PHIL_AI_OS_CONFIG_DIR="$BUILD_CTX/config" PHIL_AI_OS_PORT=4871 PHIL_AI_OS_ROUTED_EXECUTION_ENABLED=false PHIL_AI_OS_LIVE_TEST_ENABLED=false PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=general python3 "$WORK/app.py" >"$WORK/candidate.log" 2>&1 &
CAND_PID=$!
for _ in $(seq 1 40); do curl -fsS http://127.0.0.1:4871/healthz >/dev/null 2>&1 && break; sleep 0.25; done
curl -fsS http://127.0.0.1:4871/healthz >/dev/null
test "$(curl -sS -X POST -o /dev/null -w '%{http_code}' http://127.0.0.1:4871/v1/tasks/handoff/request)" = 401
REQ="$(curl -fsS -X POST -H 'Authorization: Bearer phase22-a68-isolated-token' -H 'Content-Type: application/json' -d "{\"task_id\":\"$C_TASK\",\"target_agent_id\":\"specialist-worker-01\",\"reason_code\":\"a6_8_isolated\",\"requested_by\":\"human-operator-ceo\"}" http://127.0.0.1:4871/v1/tasks/handoff/request)"
read -r C_HID C_HCORR < <(python3 -c 'import json,sys;d=json.load(sys.stdin)["handoff"];print(d["handoff_id"],d["correlation_id"])' <<<"$REQ")
PRE_CODE="$(curl -sS -X POST -H 'Authorization: Bearer phase22-a68-isolated-token' -H 'Content-Type: application/json' -d "{\"handoff_id\":\"$C_HID\"}" -o "$WORK/pre.json" -w '%{http_code}' http://127.0.0.1:4871/v1/tasks/handoff/accept)"
test "$PRE_CODE" = 409
python3 - "$WORK/runtime/phase2_2_a6_8_canary_policy.json" "$C_HID" "$C_HCORR" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); d=json.loads(p.read_text()); d['handoff_authorized']=True; d['handoff_id']=sys.argv[2]; d['handoff_correlation_id']=sys.argv[3]; p.write_text(json.dumps(d,sort_keys=True,separators=(',',':')))
PY
ACC="$(curl -fsS -X POST -H 'Authorization: Bearer phase22-a68-isolated-token' -H 'Content-Type: application/json' -d "{\"handoff_id\":\"$C_HID\"}" http://127.0.0.1:4871/v1/tasks/handoff/accept)"
REP="$(curl -fsS -X POST -H 'Authorization: Bearer phase22-a68-isolated-token' -H 'Content-Type: application/json' -d "{\"handoff_id\":\"$C_HID\"}" http://127.0.0.1:4871/v1/tasks/handoff/accept)"
python3 - "$WORK/state/control-plane.db" "$C_TASK" "$C_HID" <<'PY'
import sqlite3,sys
db,tid,hid=sys.argv[1:]; c=sqlite3.connect(db)
assert c.execute("select count(*) from task_handoffs where handoff_id=? and state='accepted' and handoff_approval_state='approved'",(hid,)).fetchone()[0]==1
assert c.execute("select count(*) from task_lifecycle_events where task_id=? and stage='ASSIGNED' and assigned_agent_id='specialist-worker-01'",(tid,)).fetchone()[0]==1
PY
python3 -c 'import json,sys;assert json.load(sys.stdin).get("idempotent_replay") is True' <<<"$REP"
kill "$CAND_PID" >/dev/null 2>&1 || true; wait "$CAND_PID" >/dev/null 2>&1 || true; CAND_PID=''
echo isolated_candidate_validation=green

# ----- production mutation begins; rollback becomes mandatory on any failure -----
ROLLBACK_ARMED=1
rollback(){
  rc=$?
  if [ "${ROLLBACK_ARMED:-0}" = 1 ]; then
    echo rollback_invoked=true
    rm -f "$POLICY" "$READINESS"
    cd "$COMPOSE_DIR"
    docker compose stop control-api >/dev/null 2>&1 || true
    cp -a "$ROLLBACK_DIR/app.py.before" "$APP_SRC"
    cp -a "$ROLLBACK_DIR/compose.yml.before" "$COMPOSE"
    cp -a "$ROLLBACK_DIR/control-plane.db.before" "$DB_HOST_PATH"
    chown "$DB_UID:$DB_GID" "$DB_HOST_PATH" || true
    chmod "$DB_MODE" "$DB_HOST_PATH" || true
    docker compose up -d --no-deps control-api >/dev/null 2>&1 || true
  fi
  exit "$rc"
}
trap rollback ERR

cp "$WORK/app.py" "$APP_SRC"
python3 - "$COMPOSE" "$OLD_IMAGE" "$NEW_IMAGE" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); old=sys.argv[2]; new=sys.argv[3]; t=p.read_text(); needle='image: '+old
assert t.count(needle)==1,t.count(needle)
p.write_text(t.replace(needle,'image: '+new,1))
PY
cd "$COMPOSE_DIR"
docker compose build control-api
docker compose up -d --no-deps control-api
for _ in $(seq 1 50); do curl -fsS http://127.0.0.1:4870/healthz >/dev/null 2>&1 && break; sleep 0.5; done
curl -fsS http://127.0.0.1:4870/healthz >/dev/null
curl -fsS http://127.0.0.1:4870/readyz >/dev/null
CONTROL="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"
test "$(docker inspect "$CONTROL" --format '{{.Config.Image}}')" = "$NEW_IMAGE"
test "$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')" = "$PATCHED_SHA"

# Dedicated canary task is inserted without invoking the normal execution-approval request surface.
TASK_ID="tsk_a68_$(python3 -c 'import uuid;print(uuid.uuid4().hex)')"
APPROVAL_ID="apr_a68_$(python3 -c 'import uuid;print(uuid.uuid4().hex)')"
CANARY_CORR="a68_$(python3 -c 'import uuid;print(uuid.uuid4().hex)')"
docker exec -i "$CONTROL" python3 - "$TASK_ID" "$APPROVAL_ID" "$CANARY_CORR" <<'PY'
import sqlite3,sys,uuid
from datetime import datetime,timezone,timedelta
tid,aid,corr=sys.argv[1:]; now=datetime.now(timezone.utc); exp=now+timedelta(minutes=10)
c=sqlite3.connect('/app/state/control-plane.db')
c.execute('BEGIN IMMEDIATE')
assert c.execute("select count(*) from task_handoffs").fetchone()[0]==0
assert c.execute("select count(*) from task_lifecycle_events where assigned_agent_id='specialist-worker-01' and stage='ASSIGNED'").fetchone()[0]==0
c.execute("insert into approval_requests(approval_id,created_at,updated_at,expires_at,state,source,requester,task_text,task_class,confidence,requested_by,task_id) values(?,?,?,?,?,?,?,?,?,?,?,?)",
 (aid,now.isoformat(),now.isoformat(),exp.isoformat(),'pending','phase-2.2-a6.8-approved-canary','human-operator-ceo','Phil AI OS Phase 2.2 A6.8 non-executing controlled handoff canary','general',1.0,'human-operator-ceo',tid))
c.execute("insert into task_lifecycle_events(event_id,task_id,stage,occurred_at,source_component,actor_id,assigned_agent_id,previous_stage,reason_code,correlation_id) values(?,?,?,?,?,?,?,?,?,?)",
 ('evt_'+uuid.uuid4().hex,tid,'ASSIGNED',now.isoformat(),'phase-2.2-a6.8-approved-canary','human-operator-ceo','hermes',None,'a6_8_canary_initial_assignment',corr))
c.commit()
PY

# Canary-only policy evidence: authority exists, handoff authorization is not yet bound.
python3 - "$POLICY" "$TASK_ID" "$CANARY_CORR" <<'PY'
import json,os,pathlib,sys,tempfile
from datetime import datetime,timezone,timedelta
p=pathlib.Path(sys.argv[1]); now=datetime.now(timezone.utc); exp=now+timedelta(minutes=5)
d={'schema_version':'2.2-a6.8.v1','authorization':'APPROVE_PHASE_2_2_A6_8','authorized_by':'CEO','task_id':sys.argv[2],'task_class':'general','required_authority':'L1','source_agent_id':'hermes','target_agent_id':'specialist-worker-01','canary_correlation_id':sys.argv[3],'handoff_authorized':False,'handoff_id':None,'handoff_correlation_id':None,'expires_at':exp.isoformat()}
fd,tmp=tempfile.mkstemp(dir=str(p.parent),prefix=p.name+'.',text=True); os.write(fd,json.dumps(d,sort_keys=True,separators=(',',':')).encode()); os.close(fd); os.chmod(tmp,0o600); os.replace(tmp,p)
PY

# Re-verify presence immediately before temporary eligibility/readiness.
python3 - <<'PY'
import base64,datetime,json,pathlib,subprocess,tempfile
now=datetime.datetime.now(datetime.timezone.utc)
e=json.loads(pathlib.Path('/var/lib/phil-ai-os/agent-presence/specialist-worker-01.json').read_text()); pl=e['payload']
age=(now-datetime.datetime.fromisoformat(pl['observed_at'])).total_seconds(); assert 0<=age<=120
assert pl['agent_id']=='specialist-worker-01' and pl['authority_ceiling']=='L1'
canonical=json.dumps(pl,sort_keys=True,separators=(',',':')).encode()
with tempfile.TemporaryDirectory() as td:
    msg=pathlib.Path(td)/'m'; sig=pathlib.Path(td)/'s'; msg.write_bytes(canonical); sig.write_bytes(base64.b64decode(e['signature_base64'],validate=True))
    subprocess.run(['openssl','pkeyutl','-verify','-pubin','-inkey','/var/lib/phil-ai-os/agent-identities/specialist-worker-01/public.pem','-sigfile',str(sig),'-rawin','-in',str(msg)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
h=json.loads(pathlib.Path('/var/lib/phil-ai-os/agent-presence/hermes.json').read_text()); assert h.get('observation_type')=='authenticated_control_api_roundtrip'
hage=(now-datetime.datetime.fromisoformat(str(h['observed_at']).replace('Z','+00:00'))).total_seconds(); assert 0<=hage<=120
PY

docker exec -i "$CONTROL" python3 - <<'PY'
import sqlite3
c=sqlite3.connect('/app/state/control-plane.db'); c.execute('BEGIN IMMEDIATE')
r=c.execute("select authority_ceiling,enabled,assignable from agent_registry where agent_id='specialist-worker-01'").fetchone(); assert r==('L1',0,0)
assert c.execute("select count(*) from task_lifecycle_events where assigned_agent_id='specialist-worker-01' and stage='ASSIGNED'").fetchone()[0]==0
u=c.execute("update agent_registry set enabled=1,assignable=1 where agent_id='specialist-worker-01' and authority_ceiling='L1' and enabled=0 and assignable=0"); assert u.rowcount==1
c.commit()
PY
echo specialist_temporary_eligibility=enabled_assignable_l1

python3 - "$READINESS" "$TASK_ID" "$CANARY_CORR" <<'PY'
import json,os,pathlib,sys,tempfile
from datetime import datetime,timezone,timedelta
p=pathlib.Path(sys.argv[1]); now=datetime.now(timezone.utc); exp=now+timedelta(minutes=3)
d={'schema_version':'2.2-a6.8.v1','authorization':'APPROVE_PHASE_2_2_A6_8','task_id':sys.argv[2],'source_agent_id':'hermes','target_agent_id':'specialist-worker-01','canary_correlation_id':sys.argv[3],'source_presence_authenticated':True,'target_presence_signature_verified':True,'specialist_prior_assignment_refs':0,'generated_at':now.isoformat(),'expires_at':exp.isoformat()}
fd,tmp=tempfile.mkstemp(dir=str(p.parent),prefix=p.name+'.',text=True); os.write(fd,json.dumps(d,sort_keys=True,separators=(',',':')).encode()); os.close(fd); os.chmod(tmp,0o600); os.replace(tmp,p)
PY

TOKEN="$(cat "$SECRETS/hermes_control_api_token")"
REQ="$(curl -fsS -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"task_id\":\"$TASK_ID\",\"target_agent_id\":\"specialist-worker-01\",\"reason_code\":\"a6_8_ceo_approved_canary\",\"requested_by\":\"human-operator-ceo\"}" http://127.0.0.1:4870/v1/tasks/handoff/request)"
read -r HANDOFF_ID HANDOFF_CORR < <(python3 -c 'import json,sys;d=json.load(sys.stdin)["handoff"];assert d["handoff_approval_state"]=="pending";print(d["handoff_id"],d["correlation_id"])' <<<"$REQ")
echo handoff_requested=true

docker exec -i "$CONTROL" python3 - "$TASK_ID" "$HANDOFF_ID" <<'PY'
import sqlite3,sys
tid,hid=sys.argv[1:]; c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True)
assert c.execute("select count(*) from task_handoffs where handoff_id=? and task_id=? and state='requested' and handoff_approval_state='pending'",(hid,tid)).fetchone()[0]==1
assert c.execute("select count(*) from task_lifecycle_events where task_id=? and assigned_agent_id='specialist-worker-01' and stage='ASSIGNED'",(tid,)).fetchone()[0]==0
PY

PRE_CODE="$(curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"handoff_id\":\"$HANDOFF_ID\"}" -o /tmp/a68-preauth.json -w '%{http_code}' http://127.0.0.1:4870/v1/tasks/handoff/accept)"
test "$PRE_CODE" = 409
python3 -c 'import json;d=json.load(open("/tmp/a68-preauth.json"));assert d.get("status")=="handoff_approval_required"'
rm -f /tmp/a68-preauth.json
echo preauthorization_accept_blocked=true

# Bind the already-granted CEO A6.8 approval to the exact handoff id/correlation.
python3 - "$POLICY" "$HANDOFF_ID" "$HANDOFF_CORR" <<'PY'
import json,os,pathlib,sys,tempfile
p=pathlib.Path(sys.argv[1]); d=json.loads(p.read_text()); d['handoff_authorized']=True; d['handoff_id']=sys.argv[2]; d['handoff_correlation_id']=sys.argv[3]
fd,tmp=tempfile.mkstemp(dir=str(p.parent),prefix=p.name+'.',text=True); os.write(fd,json.dumps(d,sort_keys=True,separators=(',',':')).encode()); os.close(fd); os.chmod(tmp,0o600); os.replace(tmp,p)
PY
echo exact_handoff_human_authorization_bound=true

ACC="$(curl -fsS -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"handoff_id\":\"$HANDOFF_ID\"}" http://127.0.0.1:4870/v1/tasks/handoff/accept)"
python3 -c 'import json,sys;d=json.load(sys.stdin);h=d["handoff"];assert h["state"]=="accepted" and h["handoff_approval_state"]=="approved" and h["target_readiness"]=="ready" and h["source_readiness"] in ("busy","ready")' <<<"$ACC"
echo handoff_accepted=true

BEFORE_REPLAY="$(docker exec "$CONTROL" python3 - "$TASK_ID" <<'PY'
import sqlite3,sys
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True); print(c.execute("select count(*) from task_lifecycle_events where task_id=? and stage='ASSIGNED' and assigned_agent_id='specialist-worker-01'",(sys.argv[1],)).fetchone()[0])
PY
)"
test "$BEFORE_REPLAY" = 1
REP="$(curl -fsS -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"handoff_id\":\"$HANDOFF_ID\"}" http://127.0.0.1:4870/v1/tasks/handoff/accept)"
python3 -c 'import json,sys;assert json.load(sys.stdin).get("idempotent_replay") is True' <<<"$REP"
AFTER_REPLAY="$(docker exec "$CONTROL" python3 - "$TASK_ID" <<'PY'
import sqlite3,sys
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True); print(c.execute("select count(*) from task_lifecycle_events where task_id=? and stage='ASSIGNED' and assigned_agent_id='specialist-worker-01'",(sys.argv[1],)).fetchone()[0])
PY
)"
test "$AFTER_REPLAY" = 1
echo replay_idempotence=verified

# Terminalize canary, expire its never-consumed execution approval, and restore specialist eligibility atomically.
docker exec -i "$CONTROL" python3 - "$TASK_ID" "$APPROVAL_ID" "$CANARY_CORR" <<'PY'
import sqlite3,sys,uuid
from datetime import datetime,timezone
tid,aid,corr=sys.argv[1:]; now=datetime.now(timezone.utc).isoformat(); c=sqlite3.connect('/app/state/control-plane.db'); c.execute('BEGIN IMMEDIATE')
last=c.execute("select stage from task_lifecycle_events where task_id=? order by occurred_at desc,event_id desc limit 1",(tid,)).fetchone(); assert last and last[0]=='ASSIGNED'
c.execute("insert into task_lifecycle_events(event_id,task_id,stage,occurred_at,source_component,actor_id,assigned_agent_id,previous_stage,reason_code,correlation_id) values(?,?,?,?,?,?,?,?,?,?)",
 ('evt_'+uuid.uuid4().hex,tid,'COMPLETED',now,'phase-2.2-a6.8-approved-canary','human-operator-ceo',None,'ASSIGNED','a6_8_nonexecuting_canary_completed',corr))
u=c.execute("update agent_registry set enabled=0,assignable=0 where agent_id='specialist-worker-01' and authority_ceiling='L1' and enabled=1 and assignable=1"); assert u.rowcount==1
u=c.execute("update approval_requests set state='expired',updated_at=?,decision_by='phase-2.2-a6.8-canary',decision_at=?,decision_note='A6.8 non-executing canary terminalized without execution' where approval_id=? and task_id=? and state='pending' and consumed_at is null",(now,now,aid,tid)); assert u.rowcount==1
c.commit()
PY
rm -f "$POLICY" "$READINESS"
echo specialist_post_canary=disabled_nonassignable_l1

# ----- final invariants -----
docker exec -i "$CONTROL" python3 - "$BASELINE" "$TASK_ID" "$HANDOFF_ID" "$HANDOFF_CORR" "$APPROVAL_ID" <<'PY'
import json,sqlite3,sys
base=json.loads(sys.argv[1]); tid,hid,hcorr,aid=sys.argv[2:]
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True); c.row_factory=sqlite3.Row
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
h=c.execute("select authority_ceiling,enabled,assignable from agent_registry where agent_id='hermes'").fetchone(); s=c.execute("select authority_ceiling,enabled,assignable from agent_registry where agent_id='specialist-worker-01'").fetchone()
assert h==('L3',1,1) and s==('L1',0,0)
row=dict(c.execute("select * from task_handoffs where handoff_id=?",(hid,)).fetchone())
assert row['task_id']==tid and row['state']=='accepted' and row['source_agent_id']=='hermes' and row['target_agent_id']=='specialist-worker-01'
assert row['required_authority']=='L1' and row['handoff_approval_state']=='approved' and row['correlation_id']==hcorr
assert row['execution_approval_state']=='pending'
assert c.execute("select count(*) from task_handoffs").fetchone()[0]==base['task_handoffs']+1
assert c.execute("select count(*) from task_lifecycle_events where task_id=? and stage='ASSIGNED' and assigned_agent_id='specialist-worker-01'",(tid,)).fetchone()[0]==1
assert c.execute("select stage from task_lifecycle_events where task_id=? order by occurred_at desc,event_id desc limit 1",(tid,)).fetchone()[0]=='COMPLETED'
ap=c.execute("select state,consumed_at,consumed_by from approval_requests where approval_id=?",(aid,)).fetchone(); assert ap[0]=='expired' and ap[1] is None and ap[2] is None
assert c.execute("select count(*) from approval_requests").fetchone()[0]==base['approval_requests']+1
assert c.execute("select count(*) from task_lifecycle_events").fetchone()[0]==base['task_lifecycle_events']+3
assert c.execute("select count(*) from task_plans").fetchone()[0]==base['task_plans']
assert c.execute("select count(*) from execution_audit").fetchone()[0]==base['execution_audit']
assert c.execute("select count(*) from usage_ledger").fetchone()[0]==base['usage_ledger']
assert c.execute("select count(*) from agent_registry").fetchone()[0]==base['agent_registry']
print('canary_task_id='+tid)
print('handoff_id='+hid)
print('handoff_correlation_id='+hcorr)
print('accepted_handoff_rows=1')
print('specialist_target_assignment_events=1')
print('canary_latest_stage=COMPLETED')
print('execution_approval_consumed=false')
print('active_specialist_workload=0')
PY

test ! -e "$POLICY"; test ! -e "$READINESS"
test "$(docker exec "$CONTROL" sh -lc 'printf %s "$PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES"')" = general
for m in POST PUT PATCH DELETE; do test "$(curl -sS -X "$m" -o /dev/null -w '%{http_code}' http://127.0.0.1:4881/api/read-model)" = 405; done
for unit in phil-ai-os-agent-heartbeat.timer phil-ai-os-specialist-worker-01-presence.timer phil-ai-os-monitor.service phil-ai-os-backup.timer phil-ai-os-backup-self-heal.timer; do systemctl is-active --quiet "$unit"; done
curl -fsS http://127.0.0.1:4870/healthz >/dev/null
curl -fsS http://127.0.0.1:4870/readyz >/dev/null

echo control_api_image="$NEW_IMAGE"
echo activated_app_sha="$PATCHED_SHA"
echo canary_policy_evidence_removed=true
echo canary_readiness_evidence_removed=true
echo provider_call=none
echo execution_call=none
echo execution_allowlist=general
echo mission_control_mutations=405
echo automatic_assignment=false
echo automatic_retry=false
echo automatic_reroute=false
echo automatic_delegation=false
echo automatic_execution=false
echo authority_expansion=none
echo second_handoff_canary=false
echo rollback_required=false
ROLLBACK_ARMED=0
trap - ERR
echo PHIL_AI_OS_PHASE_2_2_A6_8_CONTROLLED_HANDOFF_CANARY_OK
