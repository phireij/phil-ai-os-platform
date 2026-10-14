#!/usr/bin/env bash
# Read-only Hostinger VPS preflight. It never starts the session service or
# creates persistent conversation state.
set -euo pipefail

: "${IMAGE_DIGEST:?Set the reviewed immutable CEO-session image digest}"
: "${SECRET_VOLUME:?Set the protected Docker secret volume name}"

[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "$SECRET_VOLUME" =~ ^phil-ai-os-mc-google-session-secret-[0-9]+-[0-9]+$ ]]

IMAGE=ghcr.io/phireij/phil-ai-os-platform/mission-control-google-ceo-session
STATE_DIR=/var/lib/mission-control

test "$(docker volume inspect "$SECRET_VOLUME" --format '{{.Name}}')" = "$SECRET_VOLUME"
test "$(docker image inspect "$IMAGE@$IMAGE_DIGEST" --format '{{.Id}}')" != ''

# The command runs with no network and a disposable tmpfs state directory.
# It loads only the existing fail-closed configuration guard; it does not
# initialize ConversationStore, call an identity provider, or persist data.
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --tmpfs "$STATE_DIR:rw,noexec,nosuid,size=16m,mode=0700,uid=10003,gid=10003" \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
  --env 'MISSION_CONTROL_CONVERSATION_ENABLED=true' \
  --env "MISSION_CONTROL_CONVERSATION_STATE_FILE=$STATE_DIR/conversations.enc" \
  --env "MISSION_CONTROL_CONVERSATION_DELETION_LEDGER_FILE=$STATE_DIR/deletion-ledger.enc" \
  --env 'MISSION_CONTROL_CONVERSATION_KEY_FILE=/run/secrets/conversation_key' \
  --entrypoint python3 "$IMAGE@$IMAGE_DIGEST" \
  -c 'from conversation_store import ConversationConfig; config=ConversationConfig.from_environment(); assert config is not None; print("conversation_storage_preflight=green authority_effect=none storage_initialized=false network_access=false")'
