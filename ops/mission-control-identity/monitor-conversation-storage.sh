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
  --entrypoint python3 "$SESSION_IMAGE" \
  -c 'import stat
from pathlib import Path
from conversation_store import MAGIC

for name in ("conversations.enc", "deletion-ledger.enc"):
    path = Path("/mnt/conversation-state/state") / name
    details = path.lstat()
    assert stat.S_ISREG(details.st_mode) and stat.S_IMODE(details.st_mode) == 0o600
    with path.open("rb") as handle:
        assert handle.read(len(MAGIC)) == MAGIC
print("conversation_storage_monitor=green state_content_exposed=false network_access=false authority_effect=none")'
