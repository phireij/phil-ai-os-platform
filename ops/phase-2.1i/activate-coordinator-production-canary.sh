#!/usr/bin/env bash
set -euo pipefail

WD=/opt/phil-ai-os-platform/phil-ai-os-platform-phase1/infrastructure/core
COMPOSE="$WD/compose.yml"
CONTROL="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"
DB=/app/state/control-plane.db
HOSTNAME=hermes-agent-whow.srv1833510.hstgr.cloud
OLD_IMAGE=phil-ai-os/control-api:0.20.2-phase21h
NEW_IMAGE=phil-ai-os/control-api:0.20.3-phase21i
ROLLBACK_DIR="$WD/phase-2.1i-rollback"
COMPOSE_BACKUP="$ROLLBACK_DIR/compose.yml.pre-phase21i"
DB_BACKUP_NAME=control-plane.db.pre-phase21i
VOLUME_DIR=/var/lib/docker/volumes/phil-ai-os-core_control-api-state/_data
DB_BACKUP="$VOLUME_DIR/$DB_BACKUP_NAME"
BUILD_DIR="$(mktemp -d /tmp/philaios-phase21i-build.XXXXXX)"
BUILDER=/tmp/build-coordinator-app-candidate.py
MIGRATOR=/tmp/apply-coordinator-schema.py
success=0
mutation_started=0

wait_unit(){ local u="$1"; for _ in $(seq 1 15); do systemctl is-active --quiet "$u" && return 0; sleep 2; done; return 1; }
rollback(){
  echo rollback=started
  set +e
  if [ "$mutation_started" -eq 1 ]; then
    [ -f "$COMPOSE_BACKUP" ] && cp "$COMPOSE_BACKUP" "$COMPOSE"
    cd "$WD"; docker compose -f "$COMPOSE" stop control-api >/dev/null 2>&1 || true
    if [ -f "$DB_BACKUP" ]; then cp "$DB_BACKUP" "$VOLUME_DIR/control-plane.db"; chown --reference="$DB_BACKUP" "$VOLUME_DIR/control-plane.db" 2>/dev/null || true; fi
    docker compose -f "$COMPOSE" up -d --no-deps --force-recreate control-api >/dev/null 2>&1 || true
    for _ in $(seq 1 15); do curl -fsS --max-time 4 http://127.0.0.1:4870/healthz >/dev/null 2>&1 && curl -fsS --max-time 4 http://127.0.0.1:4870/readyz >/dev/null 2>&1 && break; sleep 2; done
  fi
  echo rollback=completed
}
cleanup(){ rc=$?; rm -rf "$BUILD_DIR" "$BUILDER" "$MIGRATOR" /tmp/philaios-phase21i-schema.log; if [ "$rc" -ne 0 ] && [ "$success" -ne 1 ]; then rollback; fi; }
trap cleanup EXIT

echo '=== PHASE 2.1I CONTROLLED PRODUCTION CANARY ==='
test -n "$CONTROL"; test -f "$COMPOSE"; test -f "$BUILDER"; test -f "$MIGRATOR"
test "$(docker inspect "$CONTROL" --format '{{.Config.Image}}')" = "$OLD_IMAGE"
cd "$WD"
test "$(docker compose -f "$COMPOSE" config --format json | python3 -c 'import json,sys;print(json.load(sys.stdin)["services"]["control-api"]["image"])')" = "$OLD_IMAGE"
curl -fsS --max-time 5 http://127.0.0.1:4870/healthz >/dev/null
curl -fsS --max-time 5 http://127.0.0.1:4870/readyz >/dev/null
grep -q '^PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=general$' < <(docker inspect "$CONTROL" --format '{{range .Config.Env}}{{println .}}{{end}}')
grep -q 'SCHEMA_VERSION = "2.1h.v1"' /opt/phil-ai-os/mission-control/read-model.py
grep -q 'READ ONLY · Phase 2.1H' /opt/phil-ai-os/mission-control/server.py
wait_unit phil-ai-os-monitor.service; wait_unit phil-ai-os-backup.timer; wait_unit phil-ai-os-backup-self-heal.timer; wait_unit phil-ai-os-mission-control-operator.service

OP_BEFORE="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/operator/" || true)"
APPROVAL_BEFORE="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/approval/" || true)"
MC_BEFORE="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/mission-control" || true)"
test "$OP_BEFORE" = 401; test "$APPROVAL_BEFORE" != 000; test "$MC_BEFORE" != 000

read A0 E0 L0 C0 < <(docker exec "$CONTROL" python3 -c "import sqlite3;c=sqlite3.connect('$DB');assert c.execute('pragma quick_check').fetchone()[0]=='ok';names={r[0] for r in c.execute(\"select name from sqlite_master where type='table'\")};assert 'task_lifecycle_events' in names;assert 'agent_registry' not in names;assert 'task_plans' not in names;print(c.execute('select count(*) from approval_requests').fetchone()[0],c.execute('select count(*) from execution_audit').fetchone()[0],c.execute('select count(*) from task_lifecycle_events').fetchone()[0],c.execute('select count(*) from approval_requests where task_id is not null').fetchone()[0])")
test "$L0" = 0; test "$C0" = 0
echo preflight=green

mkdir -p "$ROLLBACK_DIR"; cp "$COMPOSE" "$COMPOSE_BACKUP"; chmod 600 "$COMPOSE_BACKUP"; rm -f "$DB_BACKUP"
docker exec "$CONTROL" python3 -c "import sqlite3;s=sqlite3.connect('$DB');d=sqlite3.connect('/app/state/$DB_BACKUP_NAME');s.backup(d);d.close();s.close()"
python3 - "$DB_BACKUP" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]);assert c.execute('pragma quick_check').fetchone()[0]=='ok';c.close()
PY
echo rollback_snapshot=verified

docker cp "$CONTROL:/app/app.py" "$BUILD_DIR/app.py.base"
python3 "$BUILDER" "$BUILD_DIR/app.py.base" "$BUILD_DIR/app.py"
python3 -m py_compile "$BUILD_DIR/app.py"
CANDIDATE_HASH="$(sha256sum "$BUILD_DIR/app.py" | awk '{print $1}')"
cat > "$BUILD_DIR/Dockerfile" <<EOF
FROM $OLD_IMAGE
COPY app.py /app/app.py
EOF
docker build --pull=false -t "$NEW_IMAGE" "$BUILD_DIR" >/dev/null
test "$(docker run --rm --entrypoint sha256sum "$NEW_IMAGE" /app/app.py | awk '{print $1}')" = "$CANDIDATE_HASH"
echo candidate_image_built=true

mutation_started=1
python3 "$MIGRATOR" "$VOLUME_DIR/control-plane.db" | tee /tmp/philaios-phase21i-schema.log
grep -q 'PHIL_AI_OS_PHASE_2_1I_COORDINATOR_SCHEMA_COPY_OK' /tmp/philaios-phase21i-schema.log
python3 - "$VOLUME_DIR/control-plane.db" <<PY
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]);assert c.execute('pragma quick_check').fetchone()[0]=='ok'
assert c.execute('select count(*) from agent_registry').fetchone()[0]==1
r=c.execute('select agent_id,role,authority_ceiling,enabled,assignable,source_component from agent_registry').fetchone();assert r==('hermes','operational_worker','L3',1,1,'control-api'),r
assert c.execute('select count(*) from task_plans').fetchone()[0]==0
assert c.execute('select count(*) from task_lifecycle_events').fetchone()[0]==$L0
assert c.execute('select count(*) from approval_requests').fetchone()[0]==$A0
assert c.execute('select count(*) from execution_audit').fetchone()[0]==$E0
c.close()
PY
echo coordinator_schema=applied_empty

python3 - "$COMPOSE" "$OLD_IMAGE" "$NEW_IMAGE" <<'PY'
import pathlib,re,sys
p=pathlib.Path(sys.argv[1]);old=sys.argv[2];new=sys.argv[3];s=p.read_text();pat=re.compile(r'^(\s*image:\s*)'+re.escape(old)+r'\s*$',re.M);m=pat.findall(s);assert len(m)==1,f'image_anchor_count={len(m)}';p.write_text(pat.sub(lambda x:x.group(1)+new,s,count=1))
PY
cd "$WD"; test "$(docker compose -f "$COMPOSE" config --format json | python3 -c 'import json,sys;print(json.load(sys.stdin)["services"]["control-api"]["image"])')" = "$NEW_IMAGE"
docker compose -f "$COMPOSE" up -d --no-deps --force-recreate control-api >/dev/null
for _ in $(seq 1 15); do curl -fsS --max-time 4 http://127.0.0.1:4870/healthz >/dev/null 2>&1 && curl -fsS --max-time 4 http://127.0.0.1:4870/readyz >/dev/null 2>&1 && break; sleep 2; done
curl -fsS --max-time 5 http://127.0.0.1:4870/healthz >/dev/null; curl -fsS --max-time 5 http://127.0.0.1:4870/readyz >/dev/null
CONTROL="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"; test "$(docker inspect "$CONTROL" --format '{{.Config.Image}}')" = "$NEW_IMAGE"; test "$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')" = "$CANDIDATE_HASH"

docker exec -i "$CONTROL" python3 - <<PY
import sqlite3,pathlib
c=sqlite3.connect('$DB');assert c.execute('pragma quick_check').fetchone()[0]=='ok'
assert c.execute('select count(*) from agent_registry').fetchone()[0]==1
assert c.execute('select count(*) from task_plans').fetchone()[0]==0
assert c.execute('select count(*) from task_lifecycle_events').fetchone()[0]==$L0
assert c.execute('select count(*) from approval_requests').fetchone()[0]==$A0
assert c.execute('select count(*) from execution_audit').fetchone()[0]==$E0
c.close();s=pathlib.Path('/app/app.py').read_text();assert 'path=="/v1/tasks/assign"' in s;assert 'path=="/v1/tasks/plan"' in s;assert 'authorized(self.headers)' in s
print('live_coordinator_contract=verified')
PY
ASSIGN_401="$(curl -sS -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' --data '{}' --max-time 5 http://127.0.0.1:4870/v1/tasks/assign || true)"
PLAN_401="$(curl -sS -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' --data '{}' --max-time 5 http://127.0.0.1:4870/v1/tasks/plan || true)"
test "$ASSIGN_401" = 401; test "$PLAN_401" = 401
read A1 E1 L1 P1 < <(docker exec "$CONTROL" python3 -c "import sqlite3;c=sqlite3.connect('$DB');print(c.execute('select count(*) from approval_requests').fetchone()[0],c.execute('select count(*) from execution_audit').fetchone()[0],c.execute('select count(*) from task_lifecycle_events').fetchone()[0],c.execute('select count(*) from task_plans').fetchone()[0])")
test "$A1" = "$A0"; test "$E1" = "$E0"; test "$L1" = "$L0"; test "$P1" = 0

grep -q '^PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=general$' < <(docker inspect "$CONTROL" --format '{{range .Config.Env}}{{println .}}{{end}}')
wait_unit phil-ai-os-monitor.service; wait_unit phil-ai-os-backup.timer; wait_unit phil-ai-os-backup-self-heal.timer; wait_unit phil-ai-os-mission-control-operator.service
converged=0
for _ in $(seq 1 12); do
  OP_AFTER="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/operator/" || true)"; APPROVAL_AFTER="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/approval/" || true)"; MC_AFTER="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/mission-control" || true)"
  if [ "$OP_AFTER" = "$OP_BEFORE" ] && [ "$APPROVAL_AFTER" = "$APPROVAL_BEFORE" ] && [ "$MC_AFTER" = "$MC_BEFORE" ]; then converged=1;break;fi
  sleep 5
done
test "$converged" = 1
for method in POST PUT PATCH DELETE; do test "$(curl -s -o /dev/null -w '%{http_code}' -X "$method" --max-time 5 http://127.0.0.1:4881/api/read-model)" = 405; done

success=1
echo control_api_image=0.20.3-phase21i
echo agent_registry=active_hermes_only
echo task_plans=active_empty
echo lifecycle_rows_unchanged=true
echo coordinator_assign_unauth=401
echo coordinator_plan_unauth=401
echo approval_rows_unchanged=true
echo execution_rows_unchanged=true
echo production_allowlist=general_only
echo operator_auth_boundary=preserved
echo browser_mutation_methods=405
echo monitor=active
echo backup_timer=active
echo backup_self_heal=active
echo synthetic_task=none
echo assignment_event=none
echo planned_event=none
echo provider_call=none
echo execution_call=none
echo approval_mutation=none
echo authority_expansion=none
echo PHIL_AI_OS_PHASE_2_1I_CONTROLLED_PRODUCTION_CANARY_OK
