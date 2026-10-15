#!/usr/bin/env bash
# Networkless, read-only conversation-storage health probe. It reports only
# configuration and encrypted-file markers; it never reads/decrypts content.
set -euo pipefail

: "${SESSION_IMAGE:?Set the exact active CEO-session image reference}"
: "${SECRET_VOLUME:?Set the protected Docker secret volume name}"
: "${STATE_VOLUME:?Set the encrypted conversation-state volume name}"
: "${BACKUP_VOLUME:?Set the encrypted conversation-backup volume name}"

[[ "$SESSION_IMAGE" =~ ^ghcr\.io/phireij/phil-ai-os-platform/mission-control-google-ceo-session@sha256:[0-9a-f]{64}$ ]]
[[ "$SECRET_VOLUME" =~ ^phil-ai-os-mc-google-session-secret-[0-9]+-[0-9]+$ ]]
[[ "$STATE_VOLUME" = 'phil-ai-os-mission-control-conversation-state-v1' ]]
[[ "$BACKUP_VOLUME" = 'phil-ai-os-mission-control-conversation-backup-v1' ]]

test "$(docker volume inspect "$SECRET_VOLUME" --format '{{.Name}}')" = "$SECRET_VOLUME"
test "$(docker volume inspect "$STATE_VOLUME" --format '{{.Name}}')" = "$STATE_VOLUME"
test "$(docker volume inspect "$BACKUP_VOLUME" --format '{{.Name}}')" = "$BACKUP_VOLUME"
test "$(docker image inspect "$SESSION_IMAGE" --format '{{.Id}}')" != ''

docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --user 10003:10003 \
  --mount "type=volume,src=$STATE_VOLUME,dst=/mnt/conversation-state,readonly" \
  --mount "type=volume,src=$BACKUP_VOLUME,dst=/mnt/conversation-backup,readonly" \
  --entrypoint python3 "$SESSION_IMAGE" \
  -c 'import re, stat, time
from pathlib import Path
from conversation_store import MAGIC
from conversation_recovery import BACKUP_MAGIC, BACKUP_MAX_AGE_SECONDS

for name in ("conversations.enc", "deletion-ledger.enc"):
    path = Path("/mnt/conversation-state/state") / name
    details = path.lstat()
    assert stat.S_ISREG(details.st_mode) and stat.S_IMODE(details.st_mode) == 0o600
    with path.open("rb") as handle:
        assert handle.read(len(MAGIC)) == MAGIC
backup_directory = Path("/mnt/conversation-backup/backups")
directory_info = backup_directory.lstat()
assert backup_directory.is_dir() and not backup_directory.is_symlink(), "conversation_backup_directory_invalid"
assert stat.S_IMODE(directory_info.st_mode) == 0o700, "conversation_backup_directory_insecure"
backups = sorted(path for path in backup_directory.iterdir() if not path.name.startswith("."))
assert backups, "conversation_backup_missing"
now = int(time.time())
for path in backups:
    assert re.fullmatch(r"conversation-[0-9]{8}T[0-9]{6}Z\\.enc", path.name), "conversation_backup_name_invalid"
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600, "conversation_backup_file_insecure"
    with path.open("rb") as handle:
        assert handle.read(len(BACKUP_MAGIC)) == BACKUP_MAGIC, "conversation_backup_header_invalid"
        created_at = int.from_bytes(handle.read(8), "big")
    assert created_at <= now and now - created_at < BACKUP_MAX_AGE_SECONDS, "conversation_backup_expired"
print(f"conversation_storage_monitor=green backup_inventory_count={len(backups)} state_content_exposed=false backup_content_exposed=false network_access=false authority_effect=none")'
