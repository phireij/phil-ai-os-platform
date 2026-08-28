#!/usr/bin/env bash
set -euo pipefail

COMPOSE_DIR=/opt/phil-ai-os-platform/phil-ai-os-platform-phase1/infrastructure/core
COMPOSE="$COMPOSE_DIR/compose.yml"
BUILD_CTX=/opt/phil-ai-os-platform/phil-ai-os-platform-phase1/services/core/control-api
APP_SRC="$BUILD_CTX/app.py"
PATCHER=${1:-/tmp/phase2_2_a6_7_patch_control_api.py}
OLD_IMAGE='phil-ai-os/control-api:0.20.3-phase21i'
NEW_IMAGE='phil-ai-os/control-api:0.21.0-phase22a67'
EXPECTED_LIVE_SHA='ff72f77fdd2114e3d9f469aaac8ae8b548ba14a4e71d79498a51c499fd21fe04'
CONTROL="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"
test -n "$CONTROL"
test -r "$PATCHER"
test -f "$APP_SRC"

# Protected production preflight. The running image is authoritative. The host
# build-context source is separately snapshotted because A6.7 discovery proved
# it may drift from the running image.
curl -fsS http://127.0.0.1:4870/healthz >/dev/null
curl -fsS http://127.0.0.1:4870/readyz >/dev/null
systemctl is-active --quiet phil-ai-os-mission-control-operator.service
systemctl is-active --quiet phil-ai-os-agent-heartbeat.timer
systemctl is-active --quiet phil-ai-os-specialist-worker-01-presence.timer
systemctl is-active --quiet phil-ai-os-monitor.service
systemctl is-active --quiet phil-ai-os-backup.timer
systemctl is-active --quiet phil-ai-os-backup-self-heal.timer
test "$(docker inspect "$CONTROL" --format '{{.Config.Image}}')" = "$OLD_IMAGE"
LIVE_APP_SHA="$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')"
test "$LIVE_APP_SHA" = "$EXPECTED_LIVE_SHA"
HOST_APP_SHA="$(sha256sum "$APP_SRC" | awk '{print $1}')"
echo live_app_sha="$LIVE_APP_SHA"
echo host_build_source_sha="$HOST_APP_SHA"
if [ "$HOST_APP_SHA" != "$LIVE_APP_SHA" ]; then echo host_build_source_drift_detected=true; else echo host_build_source_drift_detected=false; fi
docker image inspect "$OLD_IMAGE" >/dev/null
test "$(docker exec "$CONTROL" sh -lc 'printf %s "$PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES"')" = general
for m in POST PUT PATCH DELETE; do
  test "$(curl -sS -X "$m" -o /dev/null -w '%{http_code}' http://127.0.0.1:4881/api/read-model)" = 405
done

# A6.4 specialist presence must still be fresh and non-eligible.
python3 - <<'PY'
import datetime,json,pathlib
p=pathlib.Path('/var/lib/phil-ai-os/agent-presence/specialist-worker-01.json')
e=json.loads(p.read_text()); pl=e['payload']
assert pl['agent_id']=='specialist-worker-01'
assert pl['authority_ceiling']=='L1'
assert pl['enabled'] is False and pl['assignable'] is False
ts=datetime.datetime.fromisoformat(pl['observed_at'])
age=(datetime.datetime.now(datetime.timezone.utc)-ts).total_seconds()
assert 0 <= age <= 120, age
print('specialist_prechange_presence_age_seconds='+str(round(age,3)))
PY

BASELINE="$(docker exec -i "$CONTROL" python3 - <<'PY'
import json,sqlite3
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True); c.row_factory=sqlite3.Row
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
assert c.execute("select count(*) from sqlite_master where type='table' and name='task_handoffs'").fetchone()[0]==0
reg=[dict(r) for r in c.execute('select * from agent_registry order by agent_id')]
assert len(reg)==2
h=next(r for r in reg if r['agent_id']=='hermes')
s=next(r for r in reg if r['agent_id']=='specialist-worker-01')
assert h['authority_ceiling']=='L3' and int(h['enabled'])==1 and int(h['assignable'])==1
assert s['authority_ceiling']=='L1' and int(s['enabled'])==0 and int(s['assignable'])==0
assert c.execute("select count(*) from task_lifecycle_events where assigned_agent_id='specialist-worker-01'").fetchone()[0]==0
tracked=['agent_registry','task_lifecycle_events','task_plans','approval_requests','execution_audit','usage_ledger']
counts={t:c.execute(f'select count(*) from {t}').fetchone()[0] for t in tracked}
print(json.dumps({'registry':reg,'counts':counts},sort_keys=True,separators=(',',':'),default=str))
PY
)"
echo baseline_captured=true

HERMES_SCRIPT_HASH="$(sha256sum /usr/local/sbin/philaios-agent-heartbeat | awk '{print $1}')"
HERMES_SERVICE_HASH="$(systemctl cat phil-ai-os-agent-heartbeat.service | sha256sum | awk '{print $1}')"
HERMES_TIMER_HASH="$(systemctl cat phil-ai-os-agent-heartbeat.timer | sha256sum | awk '{print $1}')"

# Fresh standard backup and exact rollback snapshot.
systemctl start phil-ai-os-backup.service
echo prechange_backup_service=completed
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ROLLBACK_DIR="/var/lib/phil-ai-os/rollback/phase22-a67-$STAMP"
install -d -m 700 "$ROLLBACK_DIR"
cp -a "$APP_SRC" "$ROLLBACK_DIR/app.py.host-before"
cp -a "$COMPOSE" "$ROLLBACK_DIR/compose.yml.before"
docker cp "$CONTROL":/app/app.py "$ROLLBACK_DIR/app.py.live-before"
test "$(sha256sum "$ROLLBACK_DIR/app.py.live-before" | awk '{print $1}')" = "$EXPECTED_LIVE_SHA"
docker exec -i "$CONTROL" python3 - <<'PY'
import sqlite3
src=sqlite3.connect('/app/state/control-plane.db')
dst=sqlite3.connect('/tmp/phase22-a67-prechange.db')
src.backup(dst); dst.close(); src.close()
PY
docker cp "$CONTROL":/tmp/phase22-a67-prechange.db "$ROLLBACK_DIR/control-plane.db.before"
docker exec "$CONTROL" rm -f /tmp/phase22-a67-prechange.db
chmod 600 "$ROLLBACK_DIR/control-plane.db.before"
STATE_SOURCE="$(docker inspect "$CONTROL" --format '{{range .Mounts}}{{if eq .Destination "/app/state"}}{{.Source}}{{end}}{{end}}')"
test -n "$STATE_SOURCE"
DB_HOST_PATH="$STATE_SOURCE/control-plane.db"
DB_UID="$(stat -c %u "$DB_HOST_PATH")"
DB_GID="$(stat -c %g "$DB_HOST_PATH")"
DB_MODE="$(stat -c %a "$DB_HOST_PATH")"
echo rollback_snapshot="$ROLLBACK_DIR"

# Isolated candidate build against copied live DB and the verified running source.
# Still no production mutation.
WORK="$(mktemp -d /tmp/phase22-a67.XXXXXX)"
cleanup_work(){ rm -rf "$WORK"; }
trap cleanup_work EXIT
docker cp "$CONTROL":/app/app.py "$WORK/app.py"
test "$(sha256sum "$WORK/app.py" | awk '{print $1}')" = "$EXPECTED_LIVE_SHA"
mkdir -p "$WORK/state" "$WORK/secrets"
cp "$ROLLBACK_DIR/control-plane.db.before" "$WORK/state/control-plane.db"
printf '%s\n' 'phase22-a67-isolated-token' > "$WORK/secrets/hermes_control_api_token"
chmod 600 "$WORK/secrets/hermes_control_api_token"
python3 "$PATCHER" "$WORK/app.py"
python3 -m py_compile "$WORK/app.py"
PATCHED_SHA="$(sha256sum "$WORK/app.py" | awk '{print $1}')"
test "$PATCHED_SHA" != "$EXPECTED_LIVE_SHA"
echo candidate_app_sha256="$PATCHED_SHA"

PHIL_AI_OS_STATE_DIR="$WORK/state" \
PHIL_AI_OS_SECRETS_DIR="$WORK/secrets" \
PHIL_AI_OS_RUNTIME_STATE_DIR="$COMPOSE_DIR/runtime/state" \
PHIL_AI_OS_PORT=4871 \
PHIL_AI_OS_ROUTED_EXECUTION_ENABLED=false \
PHIL_AI_OS_LIVE_TEST_ENABLED=false \
PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=general \
python3 "$WORK/app.py" >"$WORK/candidate.log" 2>&1 &
CAND_PID=$!
cleanup_candidate(){ kill "$CAND_PID" >/dev/null 2>&1 || true; wait "$CAND_PID" >/dev/null 2>&1 || true; }
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:4871/healthz >/dev/null 2>&1; then break; fi
  sleep 0.25
done
curl -fsS http://127.0.0.1:4871/healthz >/dev/null
for r in request accept reject; do
  test "$(curl -sS -X POST -o /dev/null -w '%{http_code}' "http://127.0.0.1:4871/v1/tasks/handoff/$r")" = 401
done
test "$(curl -sS -X POST -H 'Authorization: Bearer phase22-a67-isolated-token' -H 'Content-Type: application/json' -d '{"task_id":"tsk_missing","target_agent_id":"specialist-worker-01"}' -o /dev/null -w '%{http_code}' http://127.0.0.1:4871/v1/tasks/handoff/request)" = 404
test "$(curl -sS -X POST -H 'Authorization: Bearer phase22-a67-isolated-token' -H 'Content-Type: application/json' -d '{"handoff_id":"hof_missing"}' -o /dev/null -w '%{http_code}' http://127.0.0.1:4871/v1/tasks/handoff/accept)" = 404
test "$(curl -sS -X POST -H 'Authorization: Bearer phase22-a67-isolated-token' -H 'Content-Type: application/json' -d '{"handoff_id":"hof_missing"}' -o /dev/null -w '%{http_code}' http://127.0.0.1:4871/v1/tasks/handoff/reject)" = 404
python3 - "$WORK/state/control-plane.db" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1])
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
assert c.execute("select count(*) from sqlite_master where type='table' and name='task_handoffs'").fetchone()[0]==1
assert c.execute('select count(*) from task_handoffs').fetchone()[0]==0
PY
cleanup_candidate
echo isolated_candidate_validation=green

# Automatic containment after the authorized mutation starts.
MUTATED=0
rollback(){
  rc=$?
  if [ "$MUTATED" -eq 1 ]; then
    set +e
    echo rollback_attempted=true
    cp -a "$ROLLBACK_DIR/app.py.host-before" "$APP_SRC"
    cp -a "$ROLLBACK_DIR/compose.yml.before" "$COMPOSE"
    cd "$COMPOSE_DIR"
    docker compose stop control-api >/dev/null 2>&1
    cp "$ROLLBACK_DIR/control-plane.db.before" "$DB_HOST_PATH"
    chown "$DB_UID:$DB_GID" "$DB_HOST_PATH"
    chmod "$DB_MODE" "$DB_HOST_PATH"
    rm -f "$DB_HOST_PATH-wal" "$DB_HOST_PATH-shm"
    docker compose up -d --no-deps --force-recreate control-api >/dev/null 2>&1
    for _ in $(seq 1 40); do
      if curl -fsS http://127.0.0.1:4870/healthz >/dev/null 2>&1; then break; fi
      sleep 1
    done
    curl -fsS http://127.0.0.1:4870/healthz >/dev/null 2>&1
    echo rollback_completed=true
  fi
  exit "$rc"
}
trap rollback ERR

# Authorized A6.7 production mutation begins here: synchronize the build context
# to the verified running source plus the isolated A6.7 patch, then build a new tag.
MUTATED=1
cp "$WORK/app.py" "$APP_SRC"
python3 - "$COMPOSE" "$OLD_IMAGE" "$NEW_IMAGE" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); old=sys.argv[2]; new=sys.argv[3]
t=p.read_text(); needle='image: '+old
assert t.count(needle)==1, t.count(needle)
p.write_text(t.replace(needle,'image: '+new,1))
PY
cd "$COMPOSE_DIR"
docker compose config >/dev/null
docker compose build control-api
docker image inspect "$NEW_IMAGE" >/dev/null
docker compose up -d --no-deps --force-recreate control-api

for _ in $(seq 1 50); do
  if curl -fsS http://127.0.0.1:4870/healthz >/dev/null 2>&1 && curl -fsS http://127.0.0.1:4870/readyz >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS http://127.0.0.1:4870/healthz >/dev/null
curl -fsS http://127.0.0.1:4870/readyz >/dev/null
CONTROL_NEW="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"
test -n "$CONTROL_NEW"
test "$(docker inspect "$CONTROL_NEW" --format '{{.Config.Image}}')" = "$NEW_IMAGE"
test "$(docker exec "$CONTROL_NEW" sha256sum /app/app.py | awk '{print $1}')" = "$PATCHED_SHA"
test "$(sha256sum "$APP_SRC" | awk '{print $1}')" = "$PATCHED_SHA"

# Routes are reachable only behind existing bearer auth. No authenticated handoff
# mutation is invoked during A6.7 activation.
for r in request accept reject; do
  test "$(curl -sS -X POST -o /dev/null -w '%{http_code}' "http://127.0.0.1:4870/v1/tasks/handoff/$r")" = 401
done

FINAL="$(docker exec -i "$CONTROL_NEW" python3 - <<'PY'
import json,sqlite3
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True); c.row_factory=sqlite3.Row
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
assert c.execute("select count(*) from sqlite_master where type='table' and name='task_handoffs'").fetchone()[0]==1
assert c.execute('select count(*) from task_handoffs').fetchone()[0]==0
reg=[dict(r) for r in c.execute('select * from agent_registry order by agent_id')]
assert len(reg)==2
h=next(r for r in reg if r['agent_id']=='hermes')
s=next(r for r in reg if r['agent_id']=='specialist-worker-01')
assert h['authority_ceiling']=='L3' and int(h['enabled'])==1 and int(h['assignable'])==1
assert s['authority_ceiling']=='L1' and int(s['enabled'])==0 and int(s['assignable'])==0
assert c.execute("select count(*) from task_lifecycle_events where assigned_agent_id='specialist-worker-01'").fetchone()[0]==0
tracked=['agent_registry','task_lifecycle_events','task_plans','approval_requests','execution_audit','usage_ledger']
counts={t:c.execute(f'select count(*) from {t}').fetchone()[0] for t in tracked}
print(json.dumps({'registry':reg,'counts':counts},sort_keys=True,separators=(',',':'),default=str))
PY
)"
python3 - "$BASELINE" "$FINAL" <<'PY'
import json,sys
b=json.loads(sys.argv[1]); f=json.loads(sys.argv[2])
assert f==b,(b,f)
PY

# Existing operational/governance boundaries remain unchanged.
test "$(sha256sum /usr/local/sbin/philaios-agent-heartbeat | awk '{print $1}')" = "$HERMES_SCRIPT_HASH"
test "$(systemctl cat phil-ai-os-agent-heartbeat.service | sha256sum | awk '{print $1}')" = "$HERMES_SERVICE_HASH"
test "$(systemctl cat phil-ai-os-agent-heartbeat.timer | sha256sum | awk '{print $1}')" = "$HERMES_TIMER_HASH"
systemctl is-active --quiet phil-ai-os-agent-heartbeat.timer
systemctl is-active --quiet phil-ai-os-specialist-worker-01-presence.timer
systemctl start phil-ai-os-specialist-worker-01-presence.service
python3 - <<'PY'
import datetime,json,pathlib
pl=json.loads(pathlib.Path('/var/lib/phil-ai-os/agent-presence/specialist-worker-01.json').read_text())['payload']
assert pl['agent_id']=='specialist-worker-01'
assert pl['authority_ceiling']=='L1' and pl['enabled'] is False and pl['assignable'] is False
ts=datetime.datetime.fromisoformat(pl['observed_at'])
age=(datetime.datetime.now(datetime.timezone.utc)-ts).total_seconds()
assert 0 <= age <= 120, age
print('specialist_postchange_presence_age_seconds='+str(round(age,3)))
PY
systemctl is-active --quiet phil-ai-os-monitor.service
systemctl is-active --quiet phil-ai-os-backup.timer
systemctl is-active --quiet phil-ai-os-backup-self-heal.timer
test "$(docker exec "$CONTROL_NEW" sh -lc 'printf %s "$PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES"')" = general
for m in POST PUT PATCH DELETE; do
  test "$(curl -sS -X "$m" -o /dev/null -w '%{http_code}' http://127.0.0.1:4881/api/read-model)" = 405
done

trap - ERR
MUTATED=0

echo control_api_image="$NEW_IMAGE"
echo live_source_baseline_sha="$EXPECTED_LIVE_SHA"
echo prior_host_build_source_sha="$HOST_APP_SHA"
echo activated_app_sha="$PATCHED_SHA"
echo task_handoffs_table=present
echo task_handoffs_rows=0
echo handoff_request_route=authenticated_fail_closed
echo handoff_accept_route=authenticated_fail_closed
echo handoff_reject_route=authenticated
echo required_authority_evidence=current_missing_fail_closed
echo readiness_integration=current_indeterminate_fail_closed
echo specialist_authority_ceiling=L1
echo specialist_enabled=false
echo specialist_assignable=false
echo specialist_assignment_refs=0
echo registry_delta=0
echo lifecycle_delta=0
echo plan_delta=0
echo approval_delta=0
echo execution_audit_delta=0
echo usage_delta=0
echo execution_allowlist=general
echo mission_control_mutations=405
echo handoff_created_by_activation=false
echo assignment_created_by_activation=false
echo handoff_authorization_granted=false
echo provider_call=none
echo execution_call=none
echo automatic_assignment=false
echo automatic_retry=false
echo automatic_reroute=false
echo automatic_delegation=false
echo automatic_execution=false
echo authority_expansion=none
echo rollback_required=false
echo PHIL_AI_OS_PHASE_2_2_A6_7_INERT_HANDOFF_WRITER_ACTIVATION_OK
