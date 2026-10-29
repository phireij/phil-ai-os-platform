#!/usr/bin/env bash
# Controlled replacement of the already-active CEO session. The encrypted
# conversation-state mount and its fail-closed configuration are required on
# both the candidate and replacement: an upgrade must never silently remove
# previously activated storage.
set -euo pipefail

: "${IMAGE_DIGEST:?Set the reviewed replacement image digest}"
: "${CURRENT_IMAGE_DIGEST:?Set the currently active image digest}"
: "${HOSTNAME:?Set the Mission Control hostname}"
[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "$CURRENT_IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
test "$HOSTNAME" = miscon.phireij.cloud
SAME_IMAGE_RECONFIGURATION=false
if [[ "$IMAGE_DIGEST" == "$CURRENT_IMAGE_DIGEST" ]]; then
  if [[ "${MISSION_CONTROL_ALLOW_SAME_IMAGE_RECONFIGURATION:-}" != true ]]; then
    echo 'google_ceo_session_upgrade_blocked=same_image_without_reconfiguration_guard rollback_attempted=false' >&2
    exit 1
  fi
  SAME_IMAGE_RECONFIGURATION=true
elif [[ -n "${MISSION_CONTROL_ALLOW_SAME_IMAGE_RECONFIGURATION:-}" ]]; then
  echo 'google_ceo_session_upgrade_blocked=reconfiguration_guard_requires_same_image rollback_attempted=false' >&2
  exit 1
fi

IMAGE=ghcr.io/phireij/phil-ai-os-platform/mission-control-google-ceo-session
SESSION=phil-ai-os-mission-control-google-ceo-session
ROLLBACK="${SESSION}-rollback"
LEGACY_ROLLBACK="${ROLLBACK}-legacy"
PREFLIGHT="${SESSION}-preflight"
STATE_VOLUME=phil-ai-os-mission-control-conversation-state-v1
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
  echo "google_ceo_session_upgrade_failed status=$status rollback_attempted=$OLD_STAGED" >&2
  exit "$status"
}
trap 'restore_and_exit "$?"' ERR
trap 'restore_and_exit 129' HUP
trap 'restore_and_exit 130' INT
trap 'restore_and_exit 143' TERM

echo 'google_ceo_session_upgrade_phase=initial_container_guard'
if docker inspect "$ROLLBACK" >/dev/null 2>&1; then
  echo 'google_ceo_session_upgrade_phase=prior_rollback_identity'
  CURRENT_SECRET_VOLUME="$(docker inspect "$SESSION" --format '{{range .Mounts}}{{if eq .Destination "/run/secrets"}}{{.Name}}{{end}}{{end}}')"
  ROLLBACK_SECRET_VOLUME="$(docker inspect "$ROLLBACK" --format '{{range .Mounts}}{{if eq .Destination "/run/secrets"}}{{.Name}}{{end}}{{end}}')"
  CURRENT_STATE_VOLUME="$(docker inspect "$SESSION" --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mission-control"}}{{.Name}}{{end}}{{end}}')"
  ROLLBACK_STATE_VOLUME="$(docker inspect "$ROLLBACK" --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mission-control"}}{{.Name}}{{end}}{{end}}')"
  ROLLBACK_ENV="$(docker inspect "$ROLLBACK" --format '{{range .Config.Env}}{{println .}}{{end}}')"
  ROLLBACK_IMAGE="$(docker inspect "$ROLLBACK" --format '{{.Config.Image}}')"
  # A pre-route storage rollback has no restart policy or Traefik labels. It
  # is not a viable online rollback, but may retain useful forensic metadata.
  # Archive only that exact stopped, immutable, volume-compatible shape.
  if [[ "$(docker inspect "$ROLLBACK" --format '{{.State.Running}}')" == false ]] && \
     [[ "$(docker inspect "$ROLLBACK" --format '{{.HostConfig.NetworkMode}}')" == bridge ]] && \
     [[ "$(docker inspect "$ROLLBACK" --format '{{.HostConfig.ReadonlyRootfs}}')" == true ]] && \
     [[ "$(docker inspect "$ROLLBACK" --format '{{.HostConfig.RestartPolicy.Name}}')" == no ]] && \
     [[ "$(docker inspect "$ROLLBACK" --format '{{index .Config.Labels "traefik.enable"}}')" == "" ]] && \
     [[ "$(docker inspect "$ROLLBACK" --format '{{index .Config.Labels "traefik.http.routers.mission-control-google-ceo-session.service"}}')" == "" ]] && \
     [[ "$ROLLBACK_SECRET_VOLUME" == "$CURRENT_SECRET_VOLUME" ]] && \
     [[ "$CURRENT_STATE_VOLUME" == "$STATE_VOLUME" ]] && \
     [[ "$ROLLBACK_STATE_VOLUME" == "$STATE_VOLUME" ]] && \
     [[ "$ROLLBACK_IMAGE" =~ ^ghcr\.io/phireij/phil-ai-os-platform/mission-control-google-ceo-session@sha256:[0-9a-f]{64}$ ]]; then
    if docker inspect "$LEGACY_ROLLBACK" >/dev/null 2>&1; then
      echo 'google_ceo_session_upgrade_blocked=legacy_rollback_archive_unavailable rollback_attempted=false' >&2
      exit 1
    fi
    echo 'google_ceo_session_upgrade_phase=prior_rollback_route_less_legacy_archive'
    docker rename "$ROLLBACK" "$LEGACY_ROLLBACK"
  else
  if [[ "$(docker inspect "$ROLLBACK" --format '{{.State.Running}}')" != false ]] || \
     [[ "$(docker inspect "$ROLLBACK" --format '{{.HostConfig.NetworkMode}}')" != bridge ]] || \
     [[ "$(docker inspect "$ROLLBACK" --format '{{.HostConfig.ReadonlyRootfs}}')" != true ]] || \
     [[ "$(docker inspect "$ROLLBACK" --format '{{.HostConfig.RestartPolicy.Name}}')" != unless-stopped ]] || \
     [[ "$(docker inspect "$ROLLBACK" --format '{{index .Config.Labels "traefik.enable"}}')" != true ]] || \
     [[ "$(docker inspect "$ROLLBACK" --format '{{index .Config.Labels "traefik.http.routers.mission-control-google-ceo-session.service"}}')" != mission-control-google-ceo-session ]] || \
     [[ "$ROLLBACK_SECRET_VOLUME" != "$CURRENT_SECRET_VOLUME" ]] || \
     [[ "$CURRENT_STATE_VOLUME" != "$STATE_VOLUME" ]] || \
     [[ ! "$ROLLBACK_IMAGE" =~ ^ghcr\.io/phireij/phil-ai-os-platform/mission-control-google-ceo-session@sha256:[0-9a-f]{64}$ ]]; then
    echo 'google_ceo_session_upgrade_blocked=prior_rollback_identity_mismatch rollback_attempted=false' >&2
    exit 1
  fi
  if [[ -z "$ROLLBACK_STATE_VOLUME" ]]; then
    # The pre-storage upgrade path retained a stopped rollback that cannot
    # restore encrypted conversation state. Keep it as an explicitly named
    # legacy artifact rather than deleting it; the new rollback will preserve
    # the active state volume.
    if docker inspect "$LEGACY_ROLLBACK" >/dev/null 2>&1 || \
       grep -q '^MISSION_CONTROL_CONVERSATION_ENABLED=' <<<"$ROLLBACK_ENV"; then
      echo 'google_ceo_session_upgrade_blocked=legacy_rollback_archive_unavailable rollback_attempted=false' >&2
      exit 1
    fi
    echo 'google_ceo_session_upgrade_phase=prior_rollback_legacy_archive'
    docker rename "$ROLLBACK" "$LEGACY_ROLLBACK"
  elif [[ "$ROLLBACK_STATE_VOLUME" == "$STATE_VOLUME" ]]; then
    echo 'google_ceo_session_upgrade_phase=prior_rollback_replacement'
    docker rm "$ROLLBACK" >/dev/null
  else
    echo 'google_ceo_session_upgrade_blocked=prior_rollback_identity_mismatch rollback_attempted=false' >&2
    exit 1
  fi
  fi
fi
if docker inspect "$PREFLIGHT" >/dev/null 2>&1; then
  echo 'google_ceo_session_upgrade_phase=stale_preflight_identity'
  if [[ "$(docker inspect "$PREFLIGHT" --format '{{.HostConfig.NetworkMode}}')" != none ]] || \
     [[ "$(docker inspect "$PREFLIGHT" --format '{{.HostConfig.ReadonlyRootfs}}')" != true ]] || \
     [[ "$(docker inspect "$PREFLIGHT" --format '{{.HostConfig.RestartPolicy.Name}}')" != no ]] || \
     [[ "$(docker inspect "$PREFLIGHT" --format '{{index .Config.Labels "traefik.enable"}}')" != false ]]; then
    echo 'google_ceo_session_upgrade_blocked=stale_preflight_identity_mismatch rollback_attempted=false' >&2
    exit 1
  fi
  echo 'google_ceo_session_upgrade_phase=stale_preflight_cleanup'
  docker rm -f "$PREFLIGHT" >/dev/null
fi
echo 'google_ceo_session_upgrade_phase=existing_session_running'
test "$(docker inspect "$SESSION" --format '{{.State.Running}}')" = true
echo 'google_ceo_session_upgrade_phase=existing_session_image'
test "$(docker inspect "$SESSION" --format '{{.Config.Image}}')" = "$IMAGE@$CURRENT_IMAGE_DIGEST"
echo 'google_ceo_session_upgrade_phase=existing_session_network'
test "$(docker inspect "$SESSION" --format '{{.HostConfig.NetworkMode}}')" = bridge
echo 'google_ceo_session_upgrade_phase=existing_session_read_only'
test "$(docker inspect "$SESSION" --format '{{.HostConfig.ReadonlyRootfs}}')" = true
echo 'google_ceo_session_upgrade_phase=existing_session_secret_volume'
SECRET_VOLUME="$(docker inspect "$SESSION" --format '{{range .Mounts}}{{if eq .Destination "/run/secrets"}}{{.Name}}{{end}}{{end}}')"
[[ "$SECRET_VOLUME" =~ ^phil-ai-os-mc-google-session-secret-[0-9]+-[0-9]+$ ]]
echo 'google_ceo_session_upgrade_phase=existing_session_storage_mount'
ACTIVE_STATE_VOLUME="$(docker inspect "$SESSION" --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mission-control"}}{{.Name}}{{end}}{{end}}')"
test "$ACTIVE_STATE_VOLUME" = "$STATE_VOLUME"
echo 'google_ceo_session_upgrade_phase=existing_session_storage_configuration'
ACTIVE_ENV="$(docker inspect "$SESSION" --format '{{range .Config.Env}}{{println .}}{{end}}')"
for expected in \
  'MISSION_CONTROL_CONVERSATION_ENABLED=true' \
  "MISSION_CONTROL_CONVERSATION_STATE_FILE=$STATE_DATA_DIR/conversations.enc" \
  "MISSION_CONTROL_CONVERSATION_DELETION_LEDGER_FILE=$STATE_DATA_DIR/deletion-ledger.enc" \
  'MISSION_CONTROL_CONVERSATION_KEY_FILE=/run/secrets/conversation_key'; do
  grep -Fx "$expected" <<<"$ACTIVE_ENV" >/dev/null
done
ACTIVE_TELEGRAM_DELIVERY=false
if grep -Fx 'MISSION_CONTROL_TELEGRAM_DELIVERY_ENABLED=true' <<<"$ACTIVE_ENV" >/dev/null; then
  for expected in \
    'MISSION_CONTROL_TELEGRAM_DELIVERY_ENABLED=true' \
    'MISSION_CONTROL_TELEGRAM_BOT_TOKEN_FILE=/run/secrets/telegram/bot_token' \
    'MISSION_CONTROL_TELEGRAM_CHAT_ID_FILE=/run/secrets/telegram/chat_id'; do
    grep -Fx "$expected" <<<"$ACTIVE_ENV" >/dev/null
  done
  ACTIVE_TELEGRAM_DELIVERY=true
elif grep -q '^MISSION_CONTROL_TELEGRAM_' <<<"$ACTIVE_ENV"; then
  echo 'google_ceo_session_upgrade_blocked=telegram_delivery_configuration_invalid rollback_attempted=false' >&2
  exit 1
fi

ACTIVE_OPENAI_CONFIGURATION=false
if grep -Fx 'MISSION_CONTROL_OPENAI_ENABLED=true' <<<"$ACTIVE_ENV" >/dev/null; then
  for expected in \
    'MISSION_CONTROL_OPENAI_API_KEY_FILE=/run/secrets/openai/api_key' \
    'MISSION_CONTROL_OPENAI_POLICY_FILE=/run/secrets/openai/policy.json'; do
    grep -Fx "$expected" <<<"$ACTIVE_ENV" >/dev/null
  done
  ACTIVE_OPENAI_CONFIGURATION=true
elif grep -q '^MISSION_CONTROL_OPENAI_' <<<"$ACTIVE_ENV"; then
  echo 'google_ceo_session_upgrade_blocked=openai_configuration_invalid rollback_attempted=false' >&2
  exit 1
fi
if grep -Fx 'MISSION_CONTROL_OPENAI_DISPATCH_ENABLED=true' <<<"$ACTIVE_ENV" >/dev/null; then
  echo 'google_ceo_session_upgrade_blocked=active_provider_dispatch_requires_separate_upgrade_review rollback_attempted=false' >&2
  exit 1
fi

echo 'google_ceo_session_upgrade_phase=route_collision_guard'
python3 - "$SESSION" "$HOSTNAME" <<'PY'
import json
import subprocess
import sys

session, hostname = sys.argv[1:]
names = subprocess.check_output(['docker', 'ps', '--format', '{{.Names}}'], text=True).splitlines()
for name in names:
    if name == session:
        continue
    item = json.loads(subprocess.check_output(['docker', 'inspect', name], text=True))[0]
    labels = (item.get('Config') or {}).get('Labels') or {}
    for key, rule in labels.items():
        if key.startswith('traefik.http.routers.') and key.endswith('.rule'):
            if hostname in rule and '/auth/google' in rule:
                raise SystemExit('google_ceo_session_route_collision')
print('google_ceo_session_route_collision=none')
PY

BEFORE="$(docker ps --format '{{.Names}}|{{.Image}}' | awk -F'|' -v s="$SESSION" '$1 != s' | sort)"
echo 'google_ceo_session_upgrade_phase=replacement_image_pull'
if ! docker pull "$IMAGE@$IMAGE_DIGEST" >/dev/null; then
  echo 'google_ceo_session_upgrade_blocked=replacement_image_pull_failed rollback_attempted=false' >&2
  exit 1
fi

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
CONVERSATION_PREFLIGHT_ENV=(
  "${CONVERSATION_ENV[@]}"
  --env 'MISSION_CONTROL_CONVERSATION_READONLY_PREFLIGHT=true'
)
REQUESTED_TELEGRAM_DELIVERY="${MISSION_CONTROL_TELEGRAM_DELIVERY_ENABLED:-}"
if [[ -n "$REQUESTED_TELEGRAM_DELIVERY" && "$REQUESTED_TELEGRAM_DELIVERY" != true ]]; then
  echo 'google_ceo_session_upgrade_blocked=telegram_delivery_configuration_invalid rollback_attempted=false' >&2
  exit 1
fi
TELEGRAM_DELIVERY_ENABLED=false
if [[ "$ACTIVE_TELEGRAM_DELIVERY" == true ]]; then
  TELEGRAM_DELIVERY_ENABLED=true
elif [[ "$REQUESTED_TELEGRAM_DELIVERY" == true ]]; then
  if [[ "${MISSION_CONTROL_ALLOW_TELEGRAM_ENABLEMENT:-}" != true ]]; then
    echo 'google_ceo_session_upgrade_blocked=telegram_enablement_guard_required rollback_attempted=false' >&2
    exit 1
  fi
  TELEGRAM_DELIVERY_ENABLED=true
fi
TELEGRAM_ENV=()
if [[ "$TELEGRAM_DELIVERY_ENABLED" == true ]]; then
  TELEGRAM_ENV=(
    --env 'MISSION_CONTROL_TELEGRAM_DELIVERY_ENABLED=true'
    --env 'MISSION_CONTROL_TELEGRAM_BOT_TOKEN_FILE=/run/secrets/telegram/bot_token'
    --env 'MISSION_CONTROL_TELEGRAM_CHAT_ID_FILE=/run/secrets/telegram/chat_id'
  )
fi

REQUESTED_OPENAI_CONFIGURATION="${MISSION_CONTROL_OPENAI_ENABLED:-false}"
if [[ "$REQUESTED_OPENAI_CONFIGURATION" != true && "$REQUESTED_OPENAI_CONFIGURATION" != false ]]; then
  echo 'google_ceo_session_upgrade_blocked=openai_configuration_invalid rollback_attempted=false' >&2
  exit 1
fi
OPENAI_CONFIGURATION_ENABLED=false
if [[ "$ACTIVE_OPENAI_CONFIGURATION" == true ]]; then
  OPENAI_CONFIGURATION_ENABLED=true
elif [[ "$REQUESTED_OPENAI_CONFIGURATION" == true ]]; then
  if [[ "${MISSION_CONTROL_ALLOW_OPENAI_CONFIGURATION:-}" != true ]]; then
    echo 'google_ceo_session_upgrade_blocked=openai_configuration_guard_required rollback_attempted=false' >&2
    exit 1
  fi
  OPENAI_CONFIGURATION_ENABLED=true
fi
OPENAI_ENV=()
if [[ "$OPENAI_CONFIGURATION_ENABLED" == true ]]; then
  OPENAI_ENV=(
    --env 'MISSION_CONTROL_OPENAI_ENABLED=true'
    --env 'MISSION_CONTROL_OPENAI_API_KEY_FILE=/run/secrets/openai/api_key'
    --env 'MISSION_CONTROL_OPENAI_POLICY_FILE=/run/secrets/openai/policy.json'
  )
fi

echo 'google_ceo_session_upgrade_phase=existing_secret_volume_preflight'
if ! docker run --rm --network none --user 0:0 --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
  --entrypoint /bin/sh "$IMAGE@$IMAGE_DIGEST" \
  -c 'test "$(stat -c "%u:%a" /run/secrets/client_secret)" = "10003:400" && test "$(stat -c "%u:%a" /run/secrets/ceo_binding)" = "10003:400" && test -s /run/secrets/client_secret && test -s /run/secrets/ceo_binding'; then
  echo 'google_ceo_session_upgrade_blocked=existing_secret_volume_preflight_failed rollback_attempted=false' >&2
  exit 1
fi
if [[ "$TELEGRAM_DELIVERY_ENABLED" == true ]] && ! docker run --rm --network none --user 0:0 --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
  --entrypoint /bin/sh "$IMAGE@$IMAGE_DIGEST" \
  -c 'test "$(stat -c "%a" /run/secrets/telegram)" = "1733" && test "$(stat -c "%u:%a" /run/secrets/telegram/bot_token)" = "10003:400" && test "$(stat -c "%u:%a" /run/secrets/telegram/chat_id)" = "10003:400" && test -s /run/secrets/telegram/bot_token && test -s /run/secrets/telegram/chat_id'; then
  echo 'google_ceo_session_upgrade_blocked=telegram_secret_volume_preflight_failed rollback_attempted=false' >&2
  exit 1
fi
if [[ "$OPENAI_CONFIGURATION_ENABLED" == true ]] && ! docker run --rm --network none --user 0:0 --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
  --entrypoint /bin/sh "$IMAGE@$IMAGE_DIGEST" \
  -c 'test "$(stat -c "%a" /run/secrets/openai)" = "1733" && test "$(stat -c "%u:%a" /run/secrets/openai/api_key)" = "10003:400" && test "$(stat -c "%u:%a" /run/secrets/openai/policy.json)" = "10003:400" && test -s /run/secrets/openai/api_key && test -s /run/secrets/openai/policy.json'; then
  echo 'google_ceo_session_upgrade_blocked=openai_secret_volume_preflight_failed rollback_attempted=false' >&2
  exit 1
fi
if [[ "$OPENAI_CONFIGURATION_ENABLED" == true ]] && ! docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --env 'MISSION_CONTROL_OPENAI_ENABLED=true' \
  --env 'MISSION_CONTROL_OPENAI_API_KEY_FILE=/run/secrets/openai/api_key' \
  --env 'MISSION_CONTROL_OPENAI_POLICY_FILE=/run/secrets/openai/policy.json' \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
  --entrypoint python3 "$IMAGE@$IMAGE_DIGEST" \
  -c 'import time; from provider_activation import ProviderActivationConfig; ProviderActivationConfig.from_environment().runtime(int(time.time())); print("openai_configuration_valid=true network_access=false")'; then
  echo 'google_ceo_session_upgrade_blocked=openai_configuration_validation_failed rollback_attempted=false' >&2
  exit 1
fi

echo 'google_ceo_session_upgrade_phase=existing_state_volume_preflight'
if ! docker run --rm --network none --user 0:0 --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --mount "type=volume,src=$STATE_VOLUME,dst=$STATE_DIR,readonly" \
  --entrypoint /bin/sh "$IMAGE@$IMAGE_DIGEST" \
  -c 'test -d /var/lib/mission-control/state && test -r /var/lib/mission-control/state/conversations.enc && test -r /var/lib/mission-control/state/deletion-ledger.enc'; then
  echo 'google_ceo_session_upgrade_blocked=existing_state_volume_preflight_failed rollback_attempted=false' >&2
  exit 1
fi

PREFLIGHT_STARTED=true
echo 'google_ceo_session_upgrade_phase=candidate_container_start'
if ! docker run -d --name "$PREFLIGHT" --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  "${OIDC_ENV[@]}" "${CONVERSATION_PREFLIGHT_ENV[@]}" "${TELEGRAM_ENV[@]}" "${OPENAI_ENV[@]}" \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
  --mount "type=volume,src=$STATE_VOLUME,dst=$STATE_DIR,readonly" \
  --label 'traefik.enable=false' \
  "$IMAGE@$IMAGE_DIGEST" >/dev/null; then
  echo 'google_ceo_session_upgrade_blocked=candidate_container_start_failed rollback_attempted=false' >&2
  exit 1
fi
sleep 2
echo 'google_ceo_session_upgrade_phase=candidate_container_health'
if [[ "$(docker inspect "$PREFLIGHT" --format '{{.State.Running}}')" != true ]]; then
  echo 'google_ceo_session_upgrade_blocked=candidate_container_not_running rollback_attempted=false' >&2
  exit 1
fi
echo 'google_ceo_session_upgrade_phase=candidate_container_cleanup'
docker rm -f "$PREFLIGHT" >/dev/null
PREFLIGHT_STARTED=false

echo 'google_ceo_session_upgrade_phase=stage_old_session'
docker stop "$SESSION" >/dev/null
docker rename "$SESSION" "$ROLLBACK"
OLD_STAGED=true

SESSION_STARTED=true
echo 'google_ceo_session_upgrade_phase=start_replacement_session'
docker run -d --name "$SESSION" --restart unless-stopped --network bridge \
  --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  "${OIDC_ENV[@]}" "${CONVERSATION_ENV[@]}" "${TELEGRAM_ENV[@]}" "${OPENAI_ENV[@]}" \
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
echo 'google_ceo_session_upgrade_phase=verify_replacement_session'
test "$(docker inspect "$SESSION" --format '{{.State.Running}}')" = true
test "$(docker inspect "$SESSION" --format '{{.Config.Image}}')" = "$IMAGE@$IMAGE_DIGEST"
test "$(docker inspect "$SESSION" --format '{{.HostConfig.NetworkMode}}')" = bridge
test "$(docker inspect "$SESSION" --format '{{.HostConfig.ReadonlyRootfs}}')" = true
test "$(docker inspect "$SESSION" --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mission-control"}}{{.Name}}{{end}}{{end}}')" = "$STATE_VOLUME"
AFTER="$(docker ps --format '{{.Names}}|{{.Image}}' | awk -F'|' -v s="$SESSION" '$1 != s && $1 != "phil-ai-os-mission-control-google-ceo-session-rollback"' | sort)"
test "$BEFORE" = "$AFTER"

trap - ERR HUP INT TERM
echo "google_ceo_session_upgraded=true image=$IMAGE@$IMAGE_DIGEST same_image_reconfiguration=${MISSION_CONTROL_ALLOW_SAME_IMAGE_RECONFIGURATION:-false} telegram_delivery_enabled=$TELEGRAM_DELIVERY_ENABLED openai_configured=$OPENAI_CONFIGURATION_ENABLED openai_dispatch_enabled=false existing_workloads_unchanged=true rollback_retained=true state_volume=$STATE_VOLUME conversation_authority=enabled"
