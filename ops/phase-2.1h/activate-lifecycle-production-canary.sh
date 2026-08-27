#!/usr/bin/env bash
set -euo pipefail

WD=/opt/phil-ai-os-platform/phil-ai-os-platform-phase1/infrastructure/core
COMPOSE="$WD/compose.yml"
CONTROL="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"
DB=/app/state/control-plane.db
HOSTNAME=hermes-agent-whow.srv1833510.hstgr.cloud
OLD_IMAGE=phil-ai-os/control-api:0.20.1-phase21f
NEW_IMAGE=phil-ai-os/control-api:0.20.2-phase21h
ROLLBACK_DIR="$WD/phase-2.1h-rollback"
COMPOSE_BACKUP="$ROLLBACK_DIR/compose.yml.pre-phase21h"
DB_BACKUP_NAME=control-plane.db.pre-phase21h
VOLUME_DIR=/var/lib/docker/volumes/phil-ai-os-core_control-api-state/_data
DB_BACKUP="$VOLUME_DIR/$DB_BACKUP_NAME"
BUILD_DIR="$(mktemp -d /tmp/philaios-phase21h-build.XXXXXX)"
BUILDER=/tmp/build-lifecycle-writer-candidate.py
MIGRATOR=/tmp/apply-lifecycle-ledger-migration.py
success=0
mutation_started=0

wait_unit() {
  local unit="$1"
  for _ in $(seq 1 15); do
    systemctl is-active --quiet "$unit" && return 0
    sleep 2
  done
  return 1
}

rollback() {
  echo rollback=started
  set +e
  if [ "$mutation_started" -eq 1 ]; then
    [ -f "$COMPOSE_BACKUP" ] && cp "$COMPOSE_BACKUP" "$COMPOSE"
    cd "$WD"
    docker compose -f "$COMPOSE" stop control-api >/dev/null 2>&1 || true
    if [ -f "$DB_BACKUP" ]; then
      cp "$DB_BACKUP" "$VOLUME_DIR/control-plane.db"
      chown --reference="$DB_BACKUP" "$VOLUME_DIR/control-plane.db" 2>/dev/null || true
    fi
    docker compose -f "$COMPOSE" up -d --no-deps --force-recreate control-api >/dev/null 2>&1 || true
    for _ in $(seq 1 15); do
      if curl -fsS --max-time 4 http://127.0.0.1:4870/healthz >/dev/null 2>&1 && curl -fsS --max-time 4 http://127.0.0.1:4870/readyz >/dev/null 2>&1; then break; fi
      sleep 2
    done
  fi
  echo rollback=completed
}

cleanup() {
  rc=$?
  rm -rf "$BUILD_DIR" "$BUILDER" "$MIGRATOR"
  if [ "$rc" -ne 0 ] && [ "$success" -ne 1 ]; then rollback; fi
}
trap cleanup EXIT

echo '=== PHASE 2.1H CONTROLLED PRODUCTION CANARY ==='
test -n "$CONTROL"; test -f "$COMPOSE"; test -f "$BUILDER"; test -f "$MIGRATOR"
test "$(docker inspect "$CONTROL" --format '{{.Config.Image}}')" = "$OLD_IMAGE"
curl -fsS --max-time 5 http://127.0.0.1:4870/healthz >/dev/null
curl -fsS --max-time 5 http://127.0.0.1:4870/readyz >/dev/null
grep -q '^PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=general$' < <(docker inspect "$CONTROL" --format '{{range .Config.Env}}{{println .}}{{end}}')
grep -q 'SCHEMA_VERSION = "2.1g.v1"' /opt/phil-ai-os/mission-control/read-model.py
grep -q 'READ ONLY · Phase 2.1G' /opt/phil-ai-os/mission-control/server.py
wait_unit phil-ai-os-monitor.service
wait_unit phil-ai-os-backup.timer
wait_unit phil-ai-os-backup-self-heal.timer
wait_unit phil-ai-os-mission-control-operator.service

OP_BEFORE="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/operator/" || true)"
APPROVAL_BEFORE="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/approval/" || true)"
MC_BEFORE="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/mission-control" || true)"
test "$OP_BEFORE" = 401; test "$APPROVAL_BEFORE" != 000; test "$MC_BEFORE" != 000

read BEFORE_APPROVALS BEFORE_AUDITS BEFORE_TASKS < <(docker exec "$CONTROL" python3 -c "import sqlite3; c=sqlite3.connect('$DB'); assert c.execute('pragma quick_check').fetchone()[0]=='ok'; assert c.execute(\"select count(*) from sqlite_master where type='table' and name='task_lifecycle_events'\").fetchone()[0]==0; print(c.execute('select count(*) from approval_requests').fetchone()[0],c.execute('select count(*) from execution_audit').fetchone()[0],c.execute('select count(*) from approval_requests where task_id is not null').fetchone()[0])")
echo preflight=green

mkdir -p "$ROLLBACK_DIR"
cp "$COMPOSE" "$COMPOSE_BACKUP"
chmod 600 "$COMPOSE_BACKUP"
rm -f "$DB_BACKUP"
docker exec "$CONTROL" python3 -c "import sqlite3; src=sqlite3.connect('$DB'); dst=sqlite3.connect('/app/state/$DB_BACKUP_NAME'); src.backup(dst); dst.close(); src.close()"
python3 - "$DB_BACKUP" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]); assert c.execute('pragma quick_check').fetchone()[0]=='ok'; c.close()
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
python3 "$MIGRATOR" "$VOLUME_DIR/control-plane.db" >/tmp/philaios-phase21h-migration.log
grep -q 'PHIL_AI_OS_PHASE_2_1H_LEDGER_MIGRATION_APPLY_OK' /tmp/philaios-phase21h-migration.log
echo database_migration=applied

python3 - "$COMPOSE" "$OLD_IMAGE" "$NEW_IMAGE" <<'PY'
import pathlib,re,sys
p=pathlib.Path(sys.argv[1]); old=sys.argv[2]; new=sys.argv[3]; s=p.read_text()
pat=re.compile(r'^(\s*image:\s*)'+re.escape(old)+r'\s*$',re.M)
m=pat.findall(s); assert len(m)==1, f'control_api_image_anchor_count={len(m)}'
p.write_text(pat.sub(lambda x:x.group(1)+new,s,count=1))
PY
cd "$WD"
test "$(docker compose -f "$COMPOSE" config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["control-api"]["image"])')" = "$NEW_IMAGE"
docker compose -f "$COMPOSE" up -d --no-deps --force-recreate control-api >/dev/null

for _ in $(seq 1 15); do
  if curl -fsS --max-time 4 http://127.0.0.1:4870/healthz >/dev/null 2>&1 && curl -fsS --max-time 4 http://127.0.0.1:4870/readyz >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -fsS --max-time 5 http://127.0.0.1:4870/healthz >/dev/null
curl -fsS --max-time 5 http://127.0.0.1:4870/readyz >/dev/null
CONTROL="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"
test "$(docker inspect "$CONTROL" --format '{{.Config.Image}}')" = "$NEW_IMAGE"
test "$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')" = "$CANDIDATE_HASH"

docker exec -i "$CONTROL" python3 - <<PY
import inspect,sqlite3,importlib.util
c=sqlite3.connect('$DB')
try:
    assert c.execute('pragma quick_check').fetchone()[0]=='ok'
    assert c.execute("select count(*) from sqlite_master where type='table' and name='task_lifecycle_events'").fetchone()[0]==1
    assert c.execute('select count(*) from task_lifecycle_events').fetchone()[0]==0
    assert c.execute('select count(*) from approval_requests').fetchone()[0]==$BEFORE_APPROVALS
    assert c.execute('select count(*) from execution_audit').fetchone()[0]==$BEFORE_AUDITS
    assert c.execute('select count(*) from approval_requests where task_id is not null').fetchone()[0]==$BEFORE_TASKS
    triggers={r[0] for r in c.execute("select name from sqlite_master where type='trigger' and tbl_name='task_lifecycle_events'")}
    assert 'trg_task_lifecycle_events_no_update' in triggers
    assert 'trg_task_lifecycle_events_no_delete' in triggers
finally:
    c.close()
spec=importlib.util.spec_from_file_location('phase21h_live','/app/app.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
helper=inspect.getsource(mod.lifecycle_event_insert)
approval=inspect.getsource(mod.approval_create)
audit=inspect.getsource(mod.execution_audit_write)
assert 'assigned_agent_id=None' in helper
assert '"RECEIVED"' in approval and '"CLASSIFIED"' in approval and '"APPROVAL_PENDING"' in approval
assert '"AUDITED"' in audit
assert 'ASSIGNED' not in approval and 'ASSIGNED' not in audit
print('live_lifecycle_table=present')
print('live_lifecycle_rows=0')
print('append_only_triggers=present')
print('writer_contract=verified')
PY

grep -q '^PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=general$' < <(docker inspect "$CONTROL" --format '{{range .Config.Env}}{{println .}}{{end}}')
wait_unit phil-ai-os-monitor.service
wait_unit phil-ai-os-backup.timer
wait_unit phil-ai-os-backup-self-heal.timer
wait_unit phil-ai-os-mission-control-operator.service

converged=0
for _ in $(seq 1 12); do
  OP_AFTER="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/operator/" || true)"
  APPROVAL_AFTER="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/approval/" || true)"
  MC_AFTER="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/mission-control" || true)"
  if [ "$OP_AFTER" = "$OP_BEFORE" ] && [ "$APPROVAL_AFTER" = "$APPROVAL_BEFORE" ] && [ "$MC_AFTER" = "$MC_BEFORE" ]; then converged=1; break; fi
  sleep 5
done
test "$converged" = 1
for method in POST PUT PATCH DELETE; do
  test "$(curl -s -o /dev/null -w '%{http_code}' -X "$method" --max-time 5 http://127.0.0.1:4881/)" = 405
done

success=1
echo control_api_image=0.20.2-phase21h
echo lifecycle_ledger=active_empty
echo lifecycle_writer=active_bounded
echo assignment_inference=none
echo approval_rows_unchanged=true
echo execution_rows_unchanged=true
echo production_allowlist=general_only
echo operator_auth_boundary=preserved
echo browser_mutation_methods=405
echo monitor=active
echo backup_timer=active
echo backup_self_heal=active
echo synthetic_approval=none
echo provider_call=none
echo execution_call=none
echo authority_expansion=none
echo PHIL_AI_OS_PHASE_2_1H_CONTROLLED_PRODUCTION_CANARY_OK
