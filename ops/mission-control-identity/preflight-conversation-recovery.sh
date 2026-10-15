#!/usr/bin/env bash
# Read-only recovery-acceptance preflight. It validates only encrypted-file
# topology and the recovery program's CLI, without creating a backup or
# decrypting conversation data.
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

test "$(docker volume inspect "$SECRET_VOLUME" --format '{{.Name}}')" = "$SECRET_VOLUME"
test "$(docker volume inspect "$STATE_VOLUME" --format '{{.Name}}')" = "$STATE_VOLUME"
test "$(docker volume inspect "$BACKUP_VOLUME" --format '{{.Name}}')" = "$BACKUP_VOLUME"
test "$(docker image inspect "$IMAGE@$IMAGE_DIGEST" --format '{{.Id}}')" != ''

# Mount all persistent material read-only. The unprivileged process checks
# only names, modes, regular-file identity, and encrypted format markers.
# It does not print, decrypt, copy, or otherwise expose file contents.
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --user 10003:10003 \
  --mount "type=volume,src=$STATE_VOLUME,dst=/mnt/conversation-state,readonly" \
  --mount "type=volume,src=$BACKUP_VOLUME,dst=/mnt/conversation-backup,readonly" \
  --entrypoint python3 "$IMAGE@$IMAGE_DIGEST" \
  -c 'import os, stat
from pathlib import Path
from conversation_store import MAGIC
import conversation_recovery

state = Path("/mnt/conversation-state/state")
expected = (state / "conversations.enc", state / "deletion-ledger.enc")
for path in expected:
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode), "recovery_preflight_invalid_state_file"
    assert stat.S_IMODE(info.st_mode) == 0o600, "recovery_preflight_insecure_state_file"
    with path.open("rb") as handle:
        assert handle.read(len(MAGIC)) == MAGIC, "recovery_preflight_invalid_state_header"
backup = Path("/mnt/conversation-backup")
assert backup.is_dir() and not backup.is_symlink(), "recovery_preflight_invalid_backup_volume"
print("conversation_recovery_preflight=green recovery_exercise=false state_content_exposed=false network_access=false")'
