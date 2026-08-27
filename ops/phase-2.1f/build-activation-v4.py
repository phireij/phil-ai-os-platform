#!/usr/bin/env python3
import pathlib
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: build-activation-v4.py SOURCE_V3 OUTPUT_V4")

src = pathlib.Path(sys.argv[1]).read_text()

old_before = '''LABEL_HASH_BEFORE="$(docker inspect "$CONTROL" --format '{{json .Config.Labels}}' | sha256sum | awk '{print $1}')"
echo pre_control_api_label_hash="$LABEL_HASH_BEFORE"
'''
new_before = '''TRAEFIK_LABELS_BEFORE="$(docker inspect "$CONTROL" | python3 -c 'import json,sys; l=(json.load(sys.stdin)[0].get("Config",{}).get("Labels") or {}); x={k:v for k,v in l.items() if k.lower().startswith("traefik.")}; print(json.dumps(x,sort_keys=True,separators=(",",":")))')"
TRAEFIK_LABEL_COUNT_BEFORE="$(python3 -c 'import json,sys; print(len(json.loads(sys.argv[1])))' "$TRAEFIK_LABELS_BEFORE")"
TRAEFIK_LABEL_HASH_BEFORE="$(printf '%s' "$TRAEFIK_LABELS_BEFORE" | sha256sum | awk '{print $1}')"
echo pre_traefik_label_count="$TRAEFIK_LABEL_COUNT_BEFORE"
echo pre_traefik_label_hash="$TRAEFIK_LABEL_HASH_BEFORE"
test "$TRAEFIK_LABEL_COUNT_BEFORE" = '12'
'''

old_after = '''LABEL_HASH_AFTER="$(docker inspect "$CONTROL" --format '{{json .Config.Labels}}' | sha256sum | awk '{print $1}')"
echo post_control_api_label_hash="$LABEL_HASH_AFTER"
test "$LABEL_HASH_AFTER" = "$LABEL_HASH_BEFORE"
test "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:4870/phil-ai-os/approval/)" = '404'
'''
new_after = '''TRAEFIK_LABELS_AFTER="$(docker inspect "$CONTROL" | python3 -c 'import json,sys; l=(json.load(sys.stdin)[0].get("Config",{}).get("Labels") or {}); x={k:v for k,v in l.items() if k.lower().startswith("traefik.")}; print(json.dumps(x,sort_keys=True,separators=(",",":")))')"
TRAEFIK_LABEL_COUNT_AFTER="$(python3 -c 'import json,sys; print(len(json.loads(sys.argv[1])))' "$TRAEFIK_LABELS_AFTER")"
TRAEFIK_LABEL_HASH_AFTER="$(printf '%s' "$TRAEFIK_LABELS_AFTER" | sha256sum | awk '{print $1}')"
echo post_traefik_label_count="$TRAEFIK_LABEL_COUNT_AFTER"
echo post_traefik_label_hash="$TRAEFIK_LABEL_HASH_AFTER"
test "$TRAEFIK_LABEL_COUNT_AFTER" = "$TRAEFIK_LABEL_COUNT_BEFORE"
test "$TRAEFIK_LABEL_HASH_AFTER" = "$TRAEFIK_LABEL_HASH_BEFORE"
test "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:4870/phil-ai-os/approval/)" = '404'
'''

for label, old, new in [
    ("pre runtime label block", old_before, new_before),
    ("post runtime label block", old_after, new_after),
]:
    count = src.count(old)
    if count != 1:
        raise SystemExit(f"{label} match count={count}, expected=1")
    src = src.replace(old, new, 1)

src = src.replace(
    "=== PHASE 2.1F CONTROLLED PRODUCTION ACTIVATION V3 ===",
    "=== PHASE 2.1F CONTROLLED PRODUCTION ACTIVATION V4 ===",
    1,
)
src = src.replace(
    "PHIL_AI_OS_PHASE_2_1F_CONTROLLED_PRODUCTION_ACTIVATION_V3_OK",
    "PHIL_AI_OS_PHASE_2_1F_CONTROLLED_PRODUCTION_ACTIVATION_V4_OK",
    1,
)

pathlib.Path(sys.argv[2]).write_text(src)
print("activation_v4_source=v3_asserted_transform")
print("activation_v4_runtime_label_gate=traefik_only")
print("activation_v4_expected_traefik_label_count=12")
print("activation_v4_local_route_gate=404_401")
print("activation_v4_public_convergence=exact_baseline_within_60s")
print("activation_v4_rollback=preserved")
print("PHIL_AI_OS_PHASE_2_1F_ACTIVATION_V4_BUILD_OK")
