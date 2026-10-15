#!/usr/bin/env bash
# Explicitly approved restore exercise only. It pauses the existing CEO
# session briefly, creates an encrypted backup in tmpfs, restores it only to
# tmpfs quarantine files, and starts the exact same container again.
set -euo pipefail

: "${IMAGE_DIGEST:?Set the reviewed immutable CEO-session image digest}"
: "${SECRET_VOLUME:?Set the protected Docker secret volume name}"
: "${STATE_VOLUME:?Set the encrypted conversation-state volume name}"
: "${BACKUP_VOLUME:?Set the encrypted conversation-backup volume name}"

[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "$SECRET_VOLUME" =~ ^phil-ai-os-mc-google-session-secret-[0-9]+-[0-9]+$ ]]
[[ "$STATE_VOLUME" = 'phil-ai-os-mission-control-conversation-state-v1' ]]
[[ "$BACKUP_VOLUME" = 'phil-ai-os-mission-control-conversation-backup-v1' ]]

IMAGE=ghcr.io/phireij/phil-ai-os-platform/mission-control-google-ceo-session
SESSION=phil-ai-os-mission-control-google-ceo-session
STATE_DIR=/var/lib/mission-control
PAUSED=false
SESSION_ID=''

resume_session() {
  if [[ "$PAUSED" == true ]]; then
    docker start "$SESSION" >/dev/null || true
  fi
}
trap resume_session ERR HUP INT TERM

test "$(docker inspect "$SESSION" --format '{{.State.Running}}')" = true
test "$(docker inspect "$SESSION" --format '{{.Config.Image}}')" = "$IMAGE@$IMAGE_DIGEST"
test "$(docker inspect "$SESSION" --format '{{.HostConfig.ReadonlyRootfs}}')" = true
test "$(docker inspect "$SESSION" --format '{{range .Mounts}}{{if eq .Destination "/run/secrets"}}{{.Name}}{{end}}{{end}}')" = "$SECRET_VOLUME"
test "$(docker inspect "$SESSION" --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mission-control"}}{{.Name}}{{end}}{{end}}')" = "$STATE_VOLUME"
test "$(docker volume inspect "$SECRET_VOLUME" --format '{{.Name}}')" = "$SECRET_VOLUME"
test "$(docker volume inspect "$STATE_VOLUME" --format '{{.Name}}')" = "$STATE_VOLUME"
test "$(docker volume inspect "$BACKUP_VOLUME" --format '{{.Name}}')" = "$BACKUP_VOLUME"
test "$(docker image inspect "$IMAGE@$IMAGE_DIGEST" --format '{{.Id}}')" != ''

SESSION_ID="$(docker inspect "$SESSION" --format '{{.Id}}')"
BEFORE="$(docker ps --format '{{.Names}}|{{.Image}}' | awk -F'|' -v s="$SESSION" '$1 != s' | sort)"

echo 'conversation_quarantined_restore_phase=pause_existing_session'
docker stop --time 20 "$SESSION" >/dev/null
PAUSED=true
test "$(docker inspect "$SESSION" --format '{{.State.Running}}')" = false

echo 'conversation_quarantined_restore_phase=networkless_tmpfs_exercise'
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --user 10003:10003 \
  --tmpfs /work:rw,noexec,nosuid,size=384m,mode=0700,uid=10003,gid=10003 \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
  --mount "type=volume,src=$STATE_VOLUME,dst=$STATE_DIR,readonly" \
  --env 'MISSION_CONTROL_CONVERSATION_ENABLED=true' \
  --env "MISSION_CONTROL_CONVERSATION_STATE_FILE=$STATE_DIR/state/conversations.enc" \
  --env "MISSION_CONTROL_CONVERSATION_DELETION_LEDGER_FILE=$STATE_DIR/state/deletion-ledger.enc" \
  --env 'MISSION_CONTROL_CONVERSATION_KEY_FILE=/run/secrets/conversation_key' \
  --entrypoint python3 "$IMAGE@$IMAGE_DIGEST" \
  -c 'import os
from pathlib import Path
from conversation_recovery import create_backup, restore_to_quarantine
from conversation_store import ConversationConfig, MAGIC

config = ConversationConfig.from_environment()
assert config is not None
backup = Path("/work/recovery.backup")
quarantine_state = Path("/work/quarantine-conversations.enc")
quarantine_ledger = Path("/work/quarantine-deletion-ledger.enc")
created_at = create_backup(config, backup)
restored_at = restore_to_quarantine(config, backup, quarantine_state, quarantine_ledger)
assert created_at == restored_at
for path in (backup, quarantine_state, quarantine_ledger):
    info = path.lstat()
    assert path.is_file() and not path.is_symlink()
    assert info.st_mode & 0o777 == 0o600
assert quarantine_state.read_bytes().startswith(MAGIC)
assert quarantine_ledger.read_bytes().startswith(MAGIC)
print("conversation_quarantined_restore=green backup_persistent=false live_state_replaced=false offline_recovery_package_exercised=false")'

echo 'conversation_quarantined_restore_phase=resume_exact_session'
docker start "$SESSION" >/dev/null
PAUSED=false
test "$(docker inspect "$SESSION" --format '{{.State.Running}}')" = true
test "$(docker inspect "$SESSION" --format '{{.Id}}')" = "$SESSION_ID"
test "$(docker inspect "$SESSION" --format '{{.Config.Image}}')" = "$IMAGE@$IMAGE_DIGEST"
AFTER="$(docker ps --format '{{.Names}}|{{.Image}}' | awk -F'|' -v s="$SESSION" '$1 != s' | sort)"
test "$BEFORE" = "$AFTER"

trap - ERR HUP INT TERM
echo 'conversation_quarantined_restore_completed=true backup_persistent=false live_state_replaced=false offline_recovery_package_exercised=false existing_workloads_unchanged=true'
