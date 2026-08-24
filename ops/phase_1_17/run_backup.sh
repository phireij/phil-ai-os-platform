#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR=${PHIL_AI_OS_BACKUP_DIR:-/opt/phil-ai-os-platform/phil-ai-os-platform-phase1/backups/phase-1.17}
STATUS_FILE=${PHIL_AI_OS_BACKUP_STATUS_FILE:-/opt/phil-ai-os-platform/phil-ai-os-platform-phase1/backups/status/latest.json}
KEEP=${PHIL_AI_OS_BACKUP_KEEP:-14}
UTILITY=${PHIL_AI_OS_BACKUP_UTILITY:-/opt/phil-ai-os-platform/phase-1.17-backup.py}
TMP_HOST=/tmp/phil-ai-os-control-plane-snapshot.db
TMP_CONTAINER=/tmp/phil-ai-os-control-plane-snapshot.db

CONTROL=$(docker ps --format '{{.Names}}' | grep -m1 -E 'control[-_]?api|phil.*control')
test -n "$CONTROL"
mkdir -p "$BACKUP_DIR" "$(dirname "$STATUS_FILE")"
rm -f "$TMP_HOST"

docker exec "$CONTROL" python3 -c 'import sqlite3; s=sqlite3.connect("/app/state/control-plane.db"); d=sqlite3.connect("/tmp/phil-ai-os-control-plane-snapshot.db"); s.backup(d); d.close(); s.close()'
docker cp "$CONTROL:$TMP_CONTAINER" "$TMP_HOST"
docker exec "$CONTROL" rm -f "$TMP_CONTAINER"

python3 "$UTILITY" --source "$TMP_HOST" --backup-dir "$BACKUP_DIR" --status-file "$STATUS_FILE" --label scheduled
rm -f "$TMP_HOST"

mapfile -t old < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'control-plane-*-scheduled.db' -printf '%T@ %p\n' | sort -nr | awk -v keep="$KEEP" 'NR>keep {$1=""; sub(/^ /,""); print}')
for f in "${old[@]:-}"; do
  [ -n "$f" ] && rm -f -- "$f"
done

echo PHIL_AI_OS_PHASE_1_17_SCHEDULED_BACKUP_OK
