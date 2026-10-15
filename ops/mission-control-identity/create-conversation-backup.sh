#!/usr/bin/env bash
# Explicitly approved persistent encrypted backup. The CEO session is paused
# only while SQLite snapshots are read, and is restarted even after failure.
set -euo pipefail
: "${IMAGE_DIGEST:?}"; : "${SECRET_VOLUME:?}"; : "${STATE_VOLUME:?}"; : "${BACKUP_VOLUME:?}"
[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "$SECRET_VOLUME" =~ ^phil-ai-os-mc-google-session-secret-[0-9]+-[0-9]+$ ]]
[[ "$STATE_VOLUME" = phil-ai-os-mission-control-conversation-state-v1 ]]
[[ "$BACKUP_VOLUME" = phil-ai-os-mission-control-conversation-backup-v1 ]]
IMAGE=ghcr.io/phireij/phil-ai-os-platform/mission-control-google-ceo-session
SESSION=phil-ai-os-mission-control-google-ceo-session
STATE_DIR=/var/lib/mission-control
PAUSED=false
resume() { [[ "$PAUSED" == true ]] && docker start "$SESSION" >/dev/null || true; }
trap resume ERR HUP INT TERM
test "$(docker inspect "$SESSION" --format '{{.State.Running}}')" = true
test "$(docker inspect "$SESSION" --format '{{.Config.Image}}')" = "$IMAGE@$IMAGE_DIGEST"
test "$(docker inspect "$SESSION" --format '{{.HostConfig.ReadonlyRootfs}}')" = true
test "$(docker volume inspect "$SECRET_VOLUME" --format '{{.Name}}')" = "$SECRET_VOLUME"
test "$(docker volume inspect "$STATE_VOLUME" --format '{{.Name}}')" = "$STATE_VOLUME"
test "$(docker volume inspect "$BACKUP_VOLUME" --format '{{.Name}}')" = "$BACKUP_VOLUME"
BACKUP_NAME="conversation-$(date -u +%Y%m%dT%H%M%SZ).enc"
[[ "$BACKUP_NAME" =~ ^conversation-[0-9]{8}T[0-9]{6}Z\.enc$ ]]
docker run --rm --network none --read-only --cap-drop ALL --cap-add FOWNER --security-opt no-new-privileges:true --user 0:0 \
  --mount "type=volume,src=$BACKUP_VOLUME,dst=/mnt/backup" --entrypoint python3 "$IMAGE@$IMAGE_DIGEST" \
  -c 'import os; path="/mnt/backup/backups"; os.makedirs(path, mode=0o700, exist_ok=True); os.chmod(path, 0o700); os.chown(path,10003,10003); assert os.stat(path).st_mode & 0o777 == 0o700'
docker stop --time 20 "$SESSION" >/dev/null; PAUSED=true
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true --user 10003:10003 \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
  --mount "type=volume,src=$STATE_VOLUME,dst=$STATE_DIR,readonly" \
  --mount "type=volume,src=$BACKUP_VOLUME,dst=/mnt/backup" \
  --env MISSION_CONTROL_CONVERSATION_ENABLED=true \
  --env MISSION_CONTROL_CONVERSATION_STATE_FILE=$STATE_DIR/state/conversations.enc \
  --env MISSION_CONTROL_CONVERSATION_DELETION_LEDGER_FILE=$STATE_DIR/state/deletion-ledger.enc \
  --env MISSION_CONTROL_CONVERSATION_KEY_FILE=/run/secrets/conversation_key \
  --env BACKUP_NAME="$BACKUP_NAME" --entrypoint python3 "$IMAGE@$IMAGE_DIGEST" \
  -c 'import os,stat; from pathlib import Path; from conversation_recovery import create_backup,BACKUP_MAGIC; from conversation_store import ConversationConfig; p=Path("/mnt/backup/backups")/os.environ["BACKUP_NAME"]; c=ConversationConfig.from_environment(); assert c is not None; create_backup(c,p); d=p.lstat(); assert stat.S_ISREG(d.st_mode) and stat.S_IMODE(d.st_mode)==0o600 and p.read_bytes().startswith(BACKUP_MAGIC); print("conversation_backup_created=true backup_content_exposed=false")'
docker start "$SESSION" >/dev/null; PAUSED=false
test "$(docker inspect "$SESSION" --format '{{.State.Running}}')" = true
trap - ERR HUP INT TERM
echo "conversation_backup_completed=true backup_name=$BACKUP_NAME session_resumed=true live_state_replaced=false"
