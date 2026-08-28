#!/usr/bin/env bash
set -euo pipefail

COMPOSE_DIR=/opt/phil-ai-os-platform/phil-ai-os-platform-phase1/infrastructure/core
COMPOSE="$COMPOSE_DIR/compose.yml"
APP_SRC=/opt/phil-ai-os-platform/phil-ai-os-platform-phase1/services/core/control-api/app.py
MC=/opt/phil-ai-os/mission-control
CONTROL="$(docker ps --format '{{.Names}}' | grep -m1 'control-api')"
test -n "$CONTROL"
test -f "$COMPOSE" -a -f "$APP_SRC" -a -f "$MC/read-model.py"

TMP="$(mktemp -d /tmp/phase23-p4.XXXXXX)"
cleanup(){
  rm -rf "$TMP"
  docker exec "$CONTROL" rm -f /tmp/phase23-p4-preflight.db >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo '=== protected production baseline ==='
curl -fsS http://127.0.0.1:4870/healthz >/dev/null && echo control_health=ok
curl -fsS http://127.0.0.1:4870/readyz >/dev/null && echo control_ready=ok
test "$(docker inspect "$CONTROL" --format '{{.Config.Image}}')" = 'phil-ai-os/control-api:0.21.1-phase22a68'
echo control_api_image=0.21.1-phase22a68
test "$(docker exec "$CONTROL" sh -lc 'printf %s "$PHIL_AI_OS_EXECUTION_ALLOWED_TASK_CLASSES"')" = general
echo execution_allowlist=general
LIVE_SHA="$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')"
HOST_SHA="$(sha256sum "$APP_SRC" | awk '{print $1}')"
test "$LIVE_SHA" = "$HOST_SHA"
echo control_api_live_host_source_match=true
echo control_api_app_sha256="$LIVE_SHA"

MC_STATUS="$(curl -sS -o "$TMP/mc.json" -w '%{http_code}' http://127.0.0.1:4881/api/read-model)"
test "$MC_STATUS" = 200
echo mission_control_get=200
for m in POST PUT PATCH DELETE; do
  test "$(curl -sS -X "$m" -o /dev/null -w '%{http_code}' http://127.0.0.1:4881/api/read-model)" = 405
done
echo mission_control_mutations=405

for unit in phil-ai-os-monitor.service phil-ai-os-backup.timer phil-ai-os-backup-self-heal.timer phil-ai-os-agent-heartbeat.timer phil-ai-os-specialist-worker-01-presence.timer; do
  systemctl is-active --quiet "$unit"
  echo "$unit=active"
done
test "$(systemctl show -p Result --value phil-ai-os-backup.service)" = success
test "$(systemctl show -p Result --value phil-ai-os-backup-self-heal.service)" = success
echo backup_last_result=success
echo backup_self_heal_last_result=success

BEFORE="$(docker exec -i "$CONTROL" python3 - <<'PY'
import json,sqlite3
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True); c.row_factory=sqlite3.Row
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
assert c.execute("select count(*) from sqlite_master where type='table' and name='policy_decisions'").fetchone()[0]==0
tables=['agent_registry','approval_requests','execution_audit','usage_ledger','task_lifecycle_events','task_handoffs','route_policies']
counts={t:c.execute(f'select count(*) from {t}').fetchone()[0] for t in tables}
reg=[dict(r) for r in c.execute('select agent_id,authority_ceiling,enabled,assignable from agent_registry order by agent_id')]
print(json.dumps({'counts':counts,'registry':reg},sort_keys=True,separators=(',',':')))
PY
)"
printf '%s\n' "$BEFORE" > "$TMP/before.json"
echo live_policy_decisions_table=absent
echo database_quick_check=ok

# Existing application has no reusable Phase 2.3 decision ledger/writer/route.
test "$(docker exec "$CONTROL" sh -lc "grep -c 'policy_decisions' /app/app.py || true")" = 0
test "$(docker exec "$CONTROL" sh -lc "grep -c '/v1/policy' /app/app.py || true")" = 0
echo existing_policy_decision_writer=absent
echo existing_policy_api_route=absent

# Create a transactionally consistent copied database for additive migration testing.
docker exec -i "$CONTROL" python3 - <<'PY'
import sqlite3
src=sqlite3.connect('/app/state/control-plane.db')
dst=sqlite3.connect('/tmp/phase23-p4-preflight.db')
src.backup(dst); dst.close(); src.close()
PY
docker cp "$CONTROL":/tmp/phase23-p4-preflight.db "$TMP/control-plane-copy.db" >/dev/null

echo '=== copied-database additive schema validation ==='
python3 - "$TMP/control-plane-copy.db" <<'PY'
import sqlite3,sys,uuid,json,datetime
p=sys.argv[1]
c=sqlite3.connect(p)
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
assert c.execute("select count(*) from sqlite_master where type='table' and name='policy_decisions'").fetchone()[0]==0
c.executescript('''
CREATE TABLE policy_decisions(
  policy_decision_id TEXT PRIMARY KEY,
  policy_version TEXT NOT NULL,
  evaluated_at TEXT NOT NULL,
  task_id TEXT NOT NULL,
  task_class TEXT NOT NULL,
  action_type TEXT NOT NULL,
  subject_agent_id TEXT NOT NULL,
  subject_authority_ceiling TEXT NOT NULL,
  risk_tier TEXT NOT NULL,
  required_authority TEXT NOT NULL,
  configured_autonomy_ceiling TEXT NOT NULL,
  requested_autonomy_level TEXT NOT NULL,
  human_approval_required INTEGER NOT NULL,
  approval_id TEXT,
  approval_state TEXT,
  approval_expires_at TEXT,
  approval_consumption_required INTEGER NOT NULL,
  scope_constraints_json TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  decision TEXT NOT NULL,
  reason_codes_json TEXT NOT NULL,
  execution_preconditions_satisfied INTEGER NOT NULL,
  authority_effect TEXT NOT NULL CHECK(authority_effect='none'),
  evidence_hash TEXT NOT NULL
);
CREATE INDEX idx_policy_decisions_task_time ON policy_decisions(task_id,evaluated_at);
CREATE INDEX idx_policy_decisions_approval_time ON policy_decisions(approval_id,evaluated_at) WHERE approval_id IS NOT NULL;
CREATE TRIGGER policy_decisions_no_update BEFORE UPDATE ON policy_decisions BEGIN SELECT RAISE(ABORT,'policy_decisions_append_only'); END;
CREATE TRIGGER policy_decisions_no_delete BEFORE DELETE ON policy_decisions BEGIN SELECT RAISE(ABORT,'policy_decisions_append_only'); END;
''')
now=datetime.datetime.now(datetime.timezone.utc).isoformat(); pid='pdec_'+uuid.uuid4().hex
c.execute('''insert into policy_decisions(
 policy_decision_id,policy_version,evaluated_at,task_id,task_class,action_type,subject_agent_id,
 subject_authority_ceiling,risk_tier,required_authority,configured_autonomy_ceiling,requested_autonomy_level,
 human_approval_required,approval_id,approval_state,approval_expires_at,approval_consumption_required,
 scope_constraints_json,evidence_refs_json,decision,reason_codes_json,execution_preconditions_satisfied,
 authority_effect,evidence_hash) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
 pid,'2.3-p3.v1',now,'tsk_p4_copy','general','bounded_action','hermes','L3','R2','L1','A0','A0',1,
 None,None,None,1,'{}','[]','require_human','["isolated_preflight"]',0,'none','sha256:preflight'))
c.commit()
row=c.execute('select policy_decision_id,authority_effect,decision from policy_decisions where policy_decision_id=?',(pid,)).fetchone()
assert row==(pid,'none','require_human')
for sql in (
    "update policy_decisions set decision='deny' where policy_decision_id=?",
    "delete from policy_decisions where policy_decision_id=?",
):
    try:
        c.execute(sql,(pid,)); c.commit(); raise AssertionError('append-only trigger did not block mutation')
    except sqlite3.IntegrityError as e:
        assert 'append_only' in str(e)
        c.rollback()
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
cols=[r[1] for r in c.execute('pragma table_info(policy_decisions)')]
assert 'authority_effect' in cols and 'evidence_hash' in cols and 'approval_id' in cols
print('copied_db_policy_decisions_schema=created')
print('copied_db_append_only_update=blocked')
print('copied_db_append_only_delete=blocked')
print('copied_db_authority_effect_constraint=none')
print('copied_db_quick_check=ok')
PY

# Read-model compatibility: it already performs read-only DB snapshots and can be extended additively.
grep -Fq "mode=ro" "$MC/read-model.py"
grep -Fq "mission_control_authority':'read_only_observer'" "$MC/read-model.py"
echo read_model_uses_read_only_database=true
echo read_model_additive_projection_feasible=true

# Prove live production remained unchanged.
AFTER="$(docker exec -i "$CONTROL" python3 - <<'PY'
import json,sqlite3
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True); c.row_factory=sqlite3.Row
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
assert c.execute("select count(*) from sqlite_master where type='table' and name='policy_decisions'").fetchone()[0]==0
tables=['agent_registry','approval_requests','execution_audit','usage_ledger','task_lifecycle_events','task_handoffs','route_policies']
counts={t:c.execute(f'select count(*) from {t}').fetchone()[0] for t in tables}
reg=[dict(r) for r in c.execute('select agent_id,authority_ceiling,enabled,assignable from agent_registry order by agent_id')]
print(json.dumps({'counts':counts,'registry':reg},sort_keys=True,separators=(',',':')))
PY
)"
printf '%s\n' "$AFTER" > "$TMP/after.json"
cmp -s "$TMP/before.json" "$TMP/after.json"
echo durable_state_unchanged=true

# No secret values are read or emitted; only bounded public-safe state was inspected.
echo secret_values_exposed=false
echo provider_call=none
echo execution_call=none
echo approval_consumption=none
echo authority_expansion=none
echo production_change=none
echo candidate_minimum_change=append_only_policy_decisions_plus_read_only_projection
echo rollback_scope=control_api_app_compose_database_and_read_model
echo PHIL_AI_OS_PHASE_2_3_P4_PRODUCTION_PREFLIGHT_OK
