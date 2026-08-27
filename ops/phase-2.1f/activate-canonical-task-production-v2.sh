#!/usr/bin/env bash
set -euo pipefail

WD=/opt/phil-ai-os-platform/phil-ai-os-platform-phase1/infrastructure/core
COMPOSE="$WD/compose.yml"
CONTROL="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"
HERMES="$(docker ps --format '{{.Names}}' | grep -m1 '^hermes-agent-whow')"
DB=/app/state/control-plane.db
HOSTNAME=hermes-agent-whow.srv1833510.hstgr.cloud
OLD_IMAGE=phil-ai-os/control-api:0.20.0
NEW_IMAGE=phil-ai-os/control-api:0.20.1-phase21f
OLD_APP_HASH=c950ff968d54d083ae36c318fc97d279be78dd1543913c28d1e3d2b57fd29046
ROLLBACK_DIR="$WD/phase-2.1f-rollback"
COMPOSE_BACKUP="$ROLLBACK_DIR/compose.yml.pre-phase21f"
DB_BACKUP_NAME=control-plane.db.pre-phase21f
VOLUME_DIR=/var/lib/docker/volumes/phil-ai-os-core_control-api-state/_data
DB_BACKUP="$VOLUME_DIR/$DB_BACKUP_NAME"
BUILD_DIR="$(mktemp -d /tmp/philaios-phase-2-1f-build.XXXXXX)"
BUILDER=/tmp/philaios-phase-2-1f-app-builder.py
success=0
mutation_started=0

wait_active() {
  local unit="$1"
  local i
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    if systemctl is-active --quiet "$unit"; then
      echo "post_unit_${unit//[^A-Za-z0-9]/_}=active"
      return 0
    fi
    sleep 2
  done
  echo "post_unit_${unit//[^A-Za-z0-9]/_}=$(systemctl is-active "$unit" 2>/dev/null || true)"
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
    for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
      if curl -fsS --max-time 4 http://127.0.0.1:4870/healthz >/dev/null 2>&1 && curl -fsS --max-time 4 http://127.0.0.1:4870/readyz >/dev/null 2>&1; then break; fi
      sleep 2
    done
  fi
  echo rollback=completed
}

cleanup() {
  rc=$?
  rm -rf "$BUILD_DIR" "$BUILDER"
  if [ "$rc" -ne 0 ] && [ "$success" -ne 1 ]; then rollback; fi
}
trap cleanup EXIT

echo '=== PHASE 2.1F CONTROLLED PRODUCTION ACTIVATION V2 ==='
test -n "$CONTROL"; test -n "$HERMES"; test -f "$COMPOSE"; test -f "$BUILDER"
curl -fsS --max-time 5 http://127.0.0.1:4870/healthz >/dev/null
curl -fsS --max-time 5 http://127.0.0.1:4870/readyz >/dev/null
test "$(docker inspect "$CONTROL" --format '{{.Config.Image}}')" = "$OLD_IMAGE"
test "$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')" = "$OLD_APP_HASH"
COMPOSE_IMAGE="$(docker compose -f "$COMPOSE" config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["control-api"]["image"])')"
test "$COMPOSE_IMAGE" = "$OLD_IMAGE"
grep -q '^PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=general$' < <(docker inspect "$CONTROL" --format '{{range .Config.Env}}{{println .}}{{end}}')
wait_active phil-ai-os-monitor.service
wait_active phil-ai-os-backup.timer
wait_active phil-ai-os-backup-self-heal.timer
wait_active phil-ai-os-mission-control-operator.service
OP_BEFORE="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/operator/" || true)"
APPROVAL_BEFORE="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/approval/" || true)"
MC_BEFORE="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/mission-control" || true)"
echo pre_operator_status="$OP_BEFORE"
echo pre_approval_status="$APPROVAL_BEFORE"
echo pre_mission_control_status="$MC_BEFORE"
test "$OP_BEFORE" = '401'; test "$APPROVAL_BEFORE" != '000'; test "$MC_BEFORE" != '000'
read BEFORE_APPROVALS BEFORE_AUDITS < <(docker exec "$CONTROL" python3 -c "import sqlite3; c=sqlite3.connect('$DB'); assert c.execute('pragma quick_check').fetchone()[0]=='ok'; a=[r[1] for r in c.execute('pragma table_info(approval_requests)')]; e=[r[1] for r in c.execute('pragma table_info(execution_audit)')]; assert 'task_id' not in a and 'task_id' not in e; print(c.execute('select count(*) from approval_requests').fetchone()[0], c.execute('select count(*) from execution_audit').fetchone()[0])")
echo preflight=green

mkdir -p "$ROLLBACK_DIR"
cp "$COMPOSE" "$COMPOSE_BACKUP"
chmod 600 "$COMPOSE_BACKUP"
rm -f "$DB_BACKUP"
docker exec "$CONTROL" python3 -c "import sqlite3; src=sqlite3.connect('$DB'); dst=sqlite3.connect('/app/state/$DB_BACKUP_NAME'); src.backup(dst); dst.close(); src.close()"
test -f "$DB_BACKUP"
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
python3 - "$VOLUME_DIR/control-plane.db" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1])
try:
    c.execute('BEGIN IMMEDIATE')
    a=[r[1] for r in c.execute('pragma table_info(approval_requests)')]
    e=[r[1] for r in c.execute('pragma table_info(execution_audit)')]
    if 'task_id' not in a: c.execute('ALTER TABLE approval_requests ADD COLUMN task_id TEXT')
    if 'task_id' not in e: c.execute('ALTER TABLE execution_audit ADD COLUMN task_id TEXT')
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_approval_requests_task_id_nonnull ON approval_requests(task_id) WHERE task_id IS NOT NULL')
    c.commit()
    assert c.execute('pragma quick_check').fetchone()[0]=='ok'
except Exception:
    c.rollback(); raise
finally:
    c.close()
PY
echo database_migration=applied

python3 - "$COMPOSE" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); s=p.read_text()
old='    image: phil-ai-os/control-api:${PHIL_AI_OS_VERSION:-0.20.0}'
new='    image: phil-ai-os/control-api:0.20.1-phase21f'
assert s.count(old)==1, 'control_api_image_anchor_count='+str(s.count(old))
p.write_text(s.replace(old,new,1))
PY
cd "$WD"
test "$(docker compose -f "$COMPOSE" config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["control-api"]["image"])')" = "$NEW_IMAGE"
docker compose -f "$COMPOSE" up -d --no-deps --force-recreate control-api >/dev/null

for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  if curl -fsS --max-time 4 http://127.0.0.1:4870/healthz >/dev/null 2>&1 && curl -fsS --max-time 4 http://127.0.0.1:4870/readyz >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -fsS --max-time 5 http://127.0.0.1:4870/healthz >/dev/null
curl -fsS --max-time 5 http://127.0.0.1:4870/readyz >/dev/null
echo checkpoint=post_control_api_health_ready
CONTROL="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"
echo post_image="$(docker inspect "$CONTROL" --format '{{.Config.Image}}')"
test "$(docker inspect "$CONTROL" --format '{{.Config.Image}}')" = "$NEW_IMAGE"
test "$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')" = "$CANDIDATE_HASH"
echo checkpoint=post_image_and_app_verified

docker exec -i "$CONTROL" python3 - <<PY
import inspect,sqlite3,importlib.util
c=sqlite3.connect('$DB')
try:
    assert c.execute('pragma quick_check').fetchone()[0]=='ok'
    a=[r[1] for r in c.execute('pragma table_info(approval_requests)')]
    e=[r[1] for r in c.execute('pragma table_info(execution_audit)')]
    assert 'task_id' in a and 'task_id' in e
    assert c.execute('select count(*) from approval_requests').fetchone()[0]==$BEFORE_APPROVALS
    assert c.execute('select count(*) from execution_audit').fetchone()[0]==$BEFORE_AUDITS
    assert c.execute('select count(*) from approval_requests where task_id is not null').fetchone()[0]==0
    assert c.execute('select count(*) from execution_audit where task_id is not null').fetchone()[0]==0
    assert 'idx_approval_requests_task_id_nonnull' in [r[1] for r in c.execute('pragma index_list(approval_requests)')]
finally:
    c.close()
spec=importlib.util.spec_from_file_location('phase21f_live','/app/app.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert 'task_id' not in inspect.signature(mod.execution_audit_write).parameters
source=inspect.getsource(mod.approval_create)
assert 'task_id = "tsk_" + uuid.uuid4().hex' in source
assert '"task_id": task_id' in source
print('live_schema_task_id_columns=present')
print('historical_task_ids_remain_null=true')
print('live_application_contract=verified')
PY
echo checkpoint=post_schema_and_application_contract

ALLOWLIST="$(docker inspect "$CONTROL" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep '^PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=' || true)"
echo post_allowlist="$ALLOWLIST"
test "$ALLOWLIST" = 'PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES=general'
echo checkpoint=post_general_only_allowlist

wait_active phil-ai-os-monitor.service
wait_active phil-ai-os-backup.timer
wait_active phil-ai-os-backup-self-heal.timer
wait_active phil-ai-os-mission-control-operator.service
echo checkpoint=post_recovery_and_operator_services

OP_AFTER="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/operator/" || true)"
APPROVAL_AFTER="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/approval/" || true)"
MC_AFTER="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/mission-control" || true)"
echo post_operator_status="$OP_AFTER"
echo post_approval_status="$APPROVAL_AFTER"
echo post_mission_control_status="$MC_AFTER"
test "$OP_AFTER" = "$OP_BEFORE"
test "$APPROVAL_AFTER" = "$APPROVAL_BEFORE"
test "$MC_AFTER" = "$MC_BEFORE"
echo checkpoint=post_public_routes_preserved

for method in POST PUT PATCH DELETE; do
  code="$(curl -s -o /dev/null -w '%{http_code}' -X "$method" --max-time 5 http://127.0.0.1:4881/)"
  echo "post_operator_${method}_status=$code"
  test "$code" = '405'
done
echo checkpoint=post_browser_mutation_methods_blocked

success=1
echo phase_2_1f_image="$NEW_IMAGE"
echo canonical_task_schema=active
echo canonical_task_generation=server_side_approval_create
echo canonical_task_audit_propagation=approval_id_authoritative
echo historical_backfill=none
echo approval_rows_unchanged=true
echo execution_audit_rows_unchanged=true
echo production_allowlist=general_only
echo monitor=active
echo backup_timer=active
echo backup_self_heal=active
echo operator_auth_boundary=preserved
echo browser_mutation_methods=405
echo existing_approval_route=preserved
echo existing_mission_control_route=preserved
echo provider_call=none
echo governed_execution_call=none
echo approval_canary_mutation=none
echo authority_expansion=none
echo PHIL_AI_OS_PHASE_2_1F_CONTROLLED_PRODUCTION_ACTIVATION_V2_OK
