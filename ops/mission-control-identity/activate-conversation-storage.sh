#!/usr/bin/env bash
# Controlled activation of encrypted conversation storage for the existing CEO
# session. The previous session remains available as a stopped rollback.
set -euo pipefail

: "${IMAGE_DIGEST:?Set the immutable digest of the active CEO-session image}"
: "${HOSTNAME:?Set the Mission Control hostname}"
[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
test "$HOSTNAME" = miscon.phireij.cloud

IMAGE=ghcr.io/phireij/phil-ai-os-platform/mission-control-google-ceo-session
SESSION=phil-ai-os-mission-control-google-ceo-session
ROLLBACK="${SESSION}-storage-rollback"
PREFLIGHT="${SESSION}-storage-preflight"
STATE_VOLUME=phil-ai-os-mission-control-conversation-state-v1
BACKUP_VOLUME=phil-ai-os-mission-control-conversation-backup-v1
STATE_DIR=/var/lib/mission-control
STATE_DATA_DIR=$STATE_DIR/state
PREFLIGHT_STARTED=false
OLD_STAGED=false
SESSION_STARTED=false

restore_and_exit() {
  local status="$1"
  trap - ERR HUP INT TERM
  if [[ "$PREFLIGHT_STARTED" == true ]]; then docker rm -f "$PREFLIGHT" >/dev/null 2>&1 || true; fi
  if [[ "$SESSION_STARTED" == true ]]; then docker rm -f "$SESSION" >/dev/null 2>&1 || true; fi
  if [[ "$OLD_STAGED" == true ]] && docker inspect "$ROLLBACK" >/dev/null 2>&1; then
    docker rename "$ROLLBACK" "$SESSION" || true
    docker start "$SESSION" >/dev/null || true
  fi
  echo "conversation_storage_activation_failed status=$status rollback_attempted=$OLD_STAGED" >&2
  exit "$status"
}
trap 'restore_and_exit "$?"' ERR
trap 'restore_and_exit 129' HUP
trap 'restore_and_exit 130' INT
trap 'restore_and_exit 143' TERM

echo 'conversation_storage_activation_phase=initial_container_guard'
if docker inspect "$ROLLBACK" >/dev/null 2>&1; then
  echo 'conversation_storage_activation_blocked=storage_rollback_already_exists' >&2
  exit 1
fi
if docker inspect "$PREFLIGHT" >/dev/null 2>&1; then
  echo 'conversation_storage_activation_phase=stale_preflight_identity'
  STALE_IMAGE="$(docker inspect "$PREFLIGHT" --format '{{.Config.Image}}')"
  ACTIVE_SECRET_VOLUME="$(docker inspect "$SESSION" --format '{{range .Mounts}}{{if eq .Destination "/run/secrets"}}{{.Name}}{{end}}{{end}}')"
  STALE_SECRET_VOLUME="$(docker inspect "$PREFLIGHT" --format '{{range .Mounts}}{{if eq .Destination "/run/secrets"}}{{.Name}}{{end}}{{end}}')"
  STALE_STATE_VOLUME="$(docker inspect "$PREFLIGHT" --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mission-control"}}{{.Name}}{{end}}{{end}}')"
  if [[ "$(docker inspect "$PREFLIGHT" --format '{{.HostConfig.NetworkMode}}')" != none ]] || \
     [[ "$(docker inspect "$PREFLIGHT" --format '{{.HostConfig.ReadonlyRootfs}}')" != true ]] || \
     [[ "$(docker inspect "$PREFLIGHT" --format '{{.HostConfig.RestartPolicy.Name}}')" != no ]] || \
     [[ "$(docker inspect "$PREFLIGHT" --format '{{index .Config.Labels "traefik.enable"}}')" != false ]] || \
     [[ "$STALE_SECRET_VOLUME" != "$ACTIVE_SECRET_VOLUME" ]] || \
     [[ "$STALE_STATE_VOLUME" != "$STATE_VOLUME" ]] || \
     [[ ! "$STALE_IMAGE" =~ ^ghcr\.io/phireij/phil-ai-os-platform/mission-control-google-ceo-session@sha256:[0-9a-f]{64}$ ]]; then
    echo 'conversation_storage_activation_blocked=stale_preflight_identity_mismatch' >&2
    exit 1
  fi
  echo 'conversation_storage_activation_phase=stale_preflight_cleanup'
  docker rm -f "$PREFLIGHT" >/dev/null
fi

echo 'conversation_storage_activation_phase=existing_session_guard'
test "$(docker inspect "$SESSION" --format '{{.State.Running}}')" = true
test "$(docker inspect "$SESSION" --format '{{.Config.Image}}')" = "$IMAGE@$IMAGE_DIGEST"
test "$(docker inspect "$SESSION" --format '{{.HostConfig.NetworkMode}}')" = bridge
test "$(docker inspect "$SESSION" --format '{{.HostConfig.ReadonlyRootfs}}')" = true
if docker inspect "$SESSION" --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mission-control"}}{{.Name}}{{end}}{{end}}' | grep -q .; then
  echo 'conversation_storage_activation_blocked=session_already_has_state_mount' >&2
  exit 1
fi
SECRET_VOLUME="$(docker inspect "$SESSION" --format '{{range .Mounts}}{{if eq .Destination "/run/secrets"}}{{.Name}}{{end}}{{end}}')"
[[ "$SECRET_VOLUME" =~ ^phil-ai-os-mc-google-session-secret-[0-9]+-[0-9]+$ ]]
test "$(docker volume inspect "$SECRET_VOLUME" --format '{{.Name}}')" = "$SECRET_VOLUME"

echo 'conversation_storage_activation_phase=volume_nonexistence_guard'
STATE_VOLUME_EXISTS=false
BACKUP_VOLUME_EXISTS=false
docker volume inspect "$STATE_VOLUME" >/dev/null 2>&1 && STATE_VOLUME_EXISTS=true
docker volume inspect "$BACKUP_VOLUME" >/dev/null 2>&1 && BACKUP_VOLUME_EXISTS=true
if [[ "$STATE_VOLUME_EXISTS" != "$BACKUP_VOLUME_EXISTS" ]]; then
  echo 'conversation_storage_activation_blocked=conversation_volume_pair_mismatch' >&2
  exit 1
fi
if [[ "$STATE_VOLUME_EXISTS" == true ]]; then
  # A prior failed attempt may have created both volumes before any session
  # replacement. Reuse them only when the backup is empty and the state
  # volume is empty or contains exactly its empty seed directory.
  if ! docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true --user 0:0 \
    --mount "type=volume,src=$BACKUP_VOLUME,dst=/mnt/activation-volume,readonly" \
    --entrypoint /bin/sh "$IMAGE@$IMAGE_DIGEST" \
    -c 'test -z "$(find /mnt/activation-volume -mindepth 1 -print -quit)"'; then
    echo 'conversation_storage_activation_blocked=conversation_backup_volume_not_empty' >&2
    exit 1
  fi
  if ! docker run --rm --network none --read-only --cap-drop ALL --cap-add DAC_OVERRIDE --security-opt no-new-privileges:true --user 0:0 \
    --mount "type=volume,src=$STATE_VOLUME,dst=/mnt/activation-volume,readonly" \
    --entrypoint /bin/sh "$IMAGE@$IMAGE_DIGEST" \
    -c 'entries="$(find /mnt/activation-volume -mindepth 1 -maxdepth 1 -print)" || exit 1; if test -z "$entries"; then exit 0; fi; test "$entries" = /mnt/activation-volume/state && test -d /mnt/activation-volume/state || exit 1; contents="$(find /mnt/activation-volume/state -mindepth 1 -print -quit)" || exit 1; test -z "$contents"'; then
    echo 'conversation_storage_activation_blocked=conversation_volume_already_exists' >&2
    exit 1
  fi
  echo 'conversation_storage_activation_volume_retry=verified_empty_or_seed_only'
fi

echo 'conversation_storage_activation_phase=route_collision_guard'
python3 - "$SESSION" "$HOSTNAME" <<'PY'
import json
import subprocess
import sys

session, hostname = sys.argv[1:]
for name in subprocess.check_output(['docker', 'ps', '--format', '{{.Names}}'], text=True).splitlines():
    if name == session:
        continue
    item = json.loads(subprocess.check_output(['docker', 'inspect', name], text=True))[0]
    for key, rule in ((item.get('Config') or {}).get('Labels') or {}).items():
        if key.startswith('traefik.http.routers.') and key.endswith('.rule') and hostname in rule and '/auth/google' in rule:
            raise SystemExit('conversation_storage_activation_route_collision')
print('conversation_storage_activation_route_collision=none')
PY

BEFORE="$(docker ps --format '{{.Names}}|{{.Image}}' | awk -F'|' -v s="$SESSION" '$1 != s' | sort)"

OIDC_ENV=(
  --env 'MISSION_CONTROL_GOOGLE_OIDC_ENABLED=true'
  --env 'MISSION_CONTROL_GOOGLE_OIDC_ISSUER=https://accounts.google.com'
  --env 'MISSION_CONTROL_GOOGLE_REDIRECT_URI=https://miscon.phireij.cloud/auth/google/callback'
  --env 'MISSION_CONTROL_GOOGLE_CLIENT_ID=531519060424-c2n6uclfuko18tubr9ejs9o2fhf8s4c1.apps.googleusercontent.com'
  --env 'MISSION_CONTROL_GOOGLE_CLIENT_SECRET_FILE=/run/secrets/client_secret'
  --env 'MISSION_CONTROL_GOOGLE_CEO_SUBJECT_FILE=/run/secrets/ceo_binding'
)
CONVERSATION_ENV=(
  --env 'MISSION_CONTROL_CONVERSATION_ENABLED=true'
  --env "MISSION_CONTROL_CONVERSATION_STATE_FILE=$STATE_DATA_DIR/conversations.enc"
  --env "MISSION_CONTROL_CONVERSATION_DELETION_LEDGER_FILE=$STATE_DATA_DIR/deletion-ledger.enc"
  --env 'MISSION_CONTROL_CONVERSATION_KEY_FILE=/run/secrets/conversation_key'
)

echo 'conversation_storage_activation_phase=secret_volume_preflight'
if ! docker run --rm --network none --user 0:0 --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
  --entrypoint /bin/sh "$IMAGE@$IMAGE_DIGEST" \
  -c 'test "$(stat -c "%u:%a" /run/secrets/client_secret)" = "10003:400" && test "$(stat -c "%u:%a" /run/secrets/ceo_binding)" = "10003:400" && test "$(stat -c "%u:%a" /run/secrets/conversation_key)" = "10003:400" && test -s /run/secrets/client_secret && test -s /run/secrets/ceo_binding && test -s /run/secrets/conversation_key'; then
  echo 'conversation_storage_activation_blocked=secret_volume_preflight_failed' >&2
  exit 1
fi

echo 'conversation_storage_activation_phase=create_dedicated_volumes'
if [[ "$STATE_VOLUME_EXISTS" == false ]]; then
  docker volume create "$STATE_VOLUME" >/dev/null
  docker volume create "$BACKUP_VOLUME" >/dev/null
fi

echo 'conversation_storage_activation_phase=state_volume_ownership'
docker run --rm --network none --read-only --cap-drop ALL --cap-add FOWNER --security-opt no-new-privileges:true --user 0:0 \
  --mount "type=volume,src=$STATE_VOLUME,dst=$STATE_DIR" \
  --entrypoint python3 "$IMAGE@$IMAGE_DIGEST" \
  -c 'import os; path="/var/lib/mission-control/state"; os.makedirs(path, mode=0o1777, exist_ok=True); os.chmod(path, 0o1777); metadata=os.stat(path); assert metadata.st_mode & 0o7777 == 0o1777'

PREFLIGHT_STARTED=true
echo 'conversation_storage_activation_phase=candidate_storage_initialization'
docker run -d --name "$PREFLIGHT" --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  "${OIDC_ENV[@]}" "${CONVERSATION_ENV[@]}" \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
  --mount "type=volume,src=$STATE_VOLUME,dst=$STATE_DIR" \
  --label 'traefik.enable=false' \
  "$IMAGE@$IMAGE_DIGEST" >/dev/null
sleep 2
echo 'conversation_storage_activation_phase=candidate_storage_health'
if [[ "$(docker inspect "$PREFLIGHT" --format '{{.State.Running}}')" != true ]]; then
  # The bounded logs contain only startup diagnostics from the local candidate;
  # secrets and recovery material are never passed as command arguments.
  docker logs --tail 20 "$PREFLIGHT" >&2 || true
  echo 'conversation_storage_activation_blocked=candidate_storage_not_running' >&2
  exit 1
fi
echo 'conversation_storage_activation_phase=candidate_storage_cleanup'
docker rm -f "$PREFLIGHT" >/dev/null
PREFLIGHT_STARTED=false

echo 'conversation_storage_activation_phase=stage_old_session'
docker stop "$SESSION" >/dev/null
docker rename "$SESSION" "$ROLLBACK"
OLD_STAGED=true

SESSION_STARTED=true
echo 'conversation_storage_activation_phase=start_storage_enabled_session'
docker run -d --name "$SESSION" --restart unless-stopped --network bridge \
  --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  "${OIDC_ENV[@]}" "${CONVERSATION_ENV[@]}" \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
  --mount "type=volume,src=$STATE_VOLUME,dst=$STATE_DIR" \
  --label 'traefik.enable=true' \
  --label 'traefik.docker.network=bridge' \
  --label "traefik.http.routers.mission-control-google-ceo-session.rule=Host(\`$HOSTNAME\`) && (PathPrefix(\`/auth/google\`) || PathPrefix(\`/api/conversations\`) || PathPrefix(\`/api/notifications\`) || PathPrefix(\`/api/task-proposals\`))" \
  --label 'traefik.http.routers.mission-control-google-ceo-session.priority=120' \
  --label 'traefik.http.routers.mission-control-google-ceo-session.entrypoints=websecure' \
  --label 'traefik.http.routers.mission-control-google-ceo-session.tls=true' \
  --label 'traefik.http.routers.mission-control-google-ceo-session.tls.certresolver=letsencrypt' \
  --label 'traefik.http.routers.mission-control-google-ceo-session.service=mission-control-google-ceo-session' \
  --label 'traefik.http.services.mission-control-google-ceo-session.loadbalancer.server.port=8093' \
  "$IMAGE@$IMAGE_DIGEST" >/dev/null
sleep 5

echo 'conversation_storage_activation_phase=verify_storage_enabled_session'
test "$(docker inspect "$SESSION" --format '{{.State.Running}}')" = true
test "$(docker inspect "$SESSION" --format '{{.Config.Image}}')" = "$IMAGE@$IMAGE_DIGEST"
test "$(docker inspect "$SESSION" --format '{{.HostConfig.NetworkMode}}')" = bridge
test "$(docker inspect "$SESSION" --format '{{.HostConfig.ReadonlyRootfs}}')" = true
test "$(docker inspect "$SESSION" --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mission-control"}}{{.Name}}{{end}}{{end}}')" = "$STATE_VOLUME"
AFTER="$(docker ps --format '{{.Names}}|{{.Image}}' | awk -F'|' -v s="$SESSION" '$1 != s' | sort)"
test "$BEFORE" = "$AFTER"

trap - ERR HUP INT TERM
echo "conversation_storage_activated=true state_volume=$STATE_VOLUME backup_volume=$BACKUP_VOLUME existing_workloads_unchanged=true rollback_retained=true conversation_authority=enabled provider_authority=none task_authority=none"
