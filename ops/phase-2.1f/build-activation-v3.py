#!/usr/bin/env python3
import pathlib
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: build-activation-v3.py SOURCE_V2 OUTPUT_V3")

src_path = pathlib.Path(sys.argv[1])
out_path = pathlib.Path(sys.argv[2])
s = src_path.read_text()

old_pre = '''echo pre_operator_status="$OP_BEFORE"
echo pre_approval_status="$APPROVAL_BEFORE"
echo pre_mission_control_status="$MC_BEFORE"
test "$OP_BEFORE" = '401'; test "$APPROVAL_BEFORE" != '000'; test "$MC_BEFORE" != '000'
read BEFORE_APPROVALS BEFORE_AUDITS < <(docker exec "$CONTROL" python3 -c "import sqlite3; c=sqlite3.connect('$DB'); assert c.execute('pragma quick_check').fetchone()[0]=='ok'; a=[r[1] for r in c.execute('pragma table_info(approval_requests)')]; e=[r[1] for r in c.execute('pragma table_info(execution_audit)')]; assert 'task_id' not in a and 'task_id' not in e; print(c.execute('select count(*) from approval_requests').fetchone()[0], c.execute('select count(*) from execution_audit').fetchone()[0])")
echo preflight=green
'''
new_pre = '''echo pre_operator_status="$OP_BEFORE"
echo pre_approval_status="$APPROVAL_BEFORE"
echo pre_mission_control_status="$MC_BEFORE"
test "$OP_BEFORE" = '401'
test "$APPROVAL_BEFORE" = '404'
test "$MC_BEFORE" = '401'
LABEL_HASH_BEFORE="$(docker inspect "$CONTROL" --format '{{json .Config.Labels}}' | sha256sum | awk '{print $1}')"
echo pre_control_api_label_hash="$LABEL_HASH_BEFORE"
read BEFORE_APPROVALS BEFORE_AUDITS < <(docker exec "$CONTROL" python3 -c "import sqlite3; c=sqlite3.connect('$DB'); assert c.execute('pragma quick_check').fetchone()[0]=='ok'; a=[r[1] for r in c.execute('pragma table_info(approval_requests)')]; e=[r[1] for r in c.execute('pragma table_info(execution_audit)')]; assert 'task_id' not in a and 'task_id' not in e; print(c.execute('select count(*) from approval_requests').fetchone()[0], c.execute('select count(*) from execution_audit').fetchone()[0])")
echo preflight=green
'''

old_image_checkpoint = '''test "$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')" = "$CANDIDATE_HASH"
echo checkpoint=post_image_and_app_verified

docker exec -i "$CONTROL" python3 - <<PY
'''
new_image_checkpoint = '''test "$(docker exec "$CONTROL" sha256sum /app/app.py | awk '{print $1}')" = "$CANDIDATE_HASH"
echo checkpoint=post_image_and_app_verified
LABEL_HASH_AFTER="$(docker inspect "$CONTROL" --format '{{json .Config.Labels}}' | sha256sum | awk '{print $1}')"
echo post_control_api_label_hash="$LABEL_HASH_AFTER"
test "$LABEL_HASH_AFTER" = "$LABEL_HASH_BEFORE"
test "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:4870/phil-ai-os/approval/)" = '404'
test "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:4870/phil-ai-os/mission-control)" = '401'
echo checkpoint=post_local_routes_and_labels_preserved

docker exec -i "$CONTROL" python3 - <<PY
'''

old_public = '''OP_AFTER="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/operator/" || true)"
APPROVAL_AFTER="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/approval/" || true)"
MC_AFTER="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "https://$HOSTNAME/phil-ai-os/mission-control" || true)"
echo post_operator_status="$OP_AFTER"
echo post_approval_status="$APPROVAL_AFTER"
echo post_mission_control_status="$MC_AFTER"
test "$OP_AFTER" = "$OP_BEFORE"
test "$APPROVAL_AFTER" = "$APPROVAL_BEFORE"
test "$MC_AFTER" = "$MC_BEFORE"
echo checkpoint=post_public_routes_preserved
'''
new_public = '''OP_AFTER=000
APPROVAL_AFTER=000
MC_AFTER=000
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
  OP_AFTER="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 "https://$HOSTNAME/phil-ai-os/operator/" || true)"
  APPROVAL_AFTER="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 "https://$HOSTNAME/phil-ai-os/approval/" || true)"
  MC_AFTER="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 "https://$HOSTNAME/phil-ai-os/mission-control" || true)"
  if [ "$OP_AFTER" = "$OP_BEFORE" ] && [ "$APPROVAL_AFTER" = "$APPROVAL_BEFORE" ] && [ "$MC_AFTER" = "$MC_BEFORE" ]; then
    echo public_route_convergence_attempt="$i"
    break
  fi
  echo "public_route_convergence_wait=$i operator=$OP_AFTER approval=$APPROVAL_AFTER mission_control=$MC_AFTER"
  sleep 2
done
echo post_operator_status="$OP_AFTER"
echo post_approval_status="$APPROVAL_AFTER"
echo post_mission_control_status="$MC_AFTER"
test "$OP_AFTER" = "$OP_BEFORE"
test "$APPROVAL_AFTER" = "$APPROVAL_BEFORE"
test "$MC_AFTER" = "$MC_BEFORE"
echo checkpoint=post_public_routes_converged_to_baseline
'''

for label, old, new in [
    ("preflight route block", old_pre, new_pre),
    ("post-image block", old_image_checkpoint, new_image_checkpoint),
    ("public-route block", old_public, new_public),
]:
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"{label} match count={count}, expected=1")
    s = s.replace(old, new, 1)

s = s.replace(
    "=== PHASE 2.1F CONTROLLED PRODUCTION ACTIVATION V2 ===",
    "=== PHASE 2.1F CONTROLLED PRODUCTION ACTIVATION V3 ===",
    1,
)
s = s.replace(
    "PHIL_AI_OS_PHASE_2_1F_CONTROLLED_PRODUCTION_ACTIVATION_V2_OK",
    "PHIL_AI_OS_PHASE_2_1F_CONTROLLED_PRODUCTION_ACTIVATION_V3_OK",
    1,
)

out_path.write_text(s)
print("activation_v3_source=v2_asserted_transform")
print("activation_v3_label_hash_gate=enabled")
print("activation_v3_local_route_gate=404_401")
print("activation_v3_public_convergence_window_seconds=60")
print("activation_v3_rollback=preserved")
print("PHIL_AI_OS_PHASE_2_1F_ACTIVATION_V3_BUILD_OK")
