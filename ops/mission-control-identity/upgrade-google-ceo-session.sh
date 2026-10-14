#!/usr/bin/env bash
# Controlled replacement of the already-active CEO session. Conversation
# storage is deliberately not configured by this rollout.
set -euo pipefail

: "${IMAGE_DIGEST:?Set the reviewed replacement image digest}"
: "${CURRENT_IMAGE_DIGEST:?Set the currently active image digest}"
: "${HOSTNAME:?Set the Mission Control hostname}"
[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "$CURRENT_IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
test "$HOSTNAME" = miscon.phireij.cloud
test "$IMAGE_DIGEST" != "$CURRENT_IMAGE_DIGEST"

IMAGE=ghcr.io/phireij/phil-ai-os-platform/mission-control-google-ceo-session
SESSION=phil-ai-os-mission-control-google-ceo-session
ROLLBACK="${SESSION}-rollback"
PREFLIGHT="${SESSION}-preflight"
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
  echo 'Refusing upgrade: rollback container already exists' >&2
  exit 1
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

echo 'google_ceo_session_upgrade_phase=existing_secret_volume_preflight'
if ! docker run --rm --network none --user 0:0 --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
  --entrypoint /bin/sh "$IMAGE@$IMAGE_DIGEST" \
  -c 'test "$(stat -c "%u:%a" /run/secrets/client_secret)" = "10003:400" && test "$(stat -c "%u:%a" /run/secrets/ceo_binding)" = "10003:400" && test -s /run/secrets/client_secret && test -s /run/secrets/ceo_binding'; then
  echo 'google_ceo_session_upgrade_blocked=existing_secret_volume_preflight_failed rollback_attempted=false' >&2
  exit 1
fi

PREFLIGHT_STARTED=true
echo 'google_ceo_session_upgrade_phase=candidate_container_start'
if ! docker run -d --name "$PREFLIGHT" --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  "${OIDC_ENV[@]}" \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
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
  "${OIDC_ENV[@]}" \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
  --label 'traefik.enable=true' \
  --label 'traefik.docker.network=bridge' \
  --label "traefik.http.routers.mission-control-google-ceo-session.rule=Host(\`$HOSTNAME\`) && PathPrefix(\`/auth/google\`)" \
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
AFTER="$(docker ps --format '{{.Names}}|{{.Image}}' | awk -F'|' -v s="$SESSION" '$1 != s && $1 != "phil-ai-os-mission-control-google-ceo-session-rollback"' | sort)"
test "$BEFORE" = "$AFTER"

trap - ERR HUP INT TERM
echo "google_ceo_session_upgraded=true image=$IMAGE@$IMAGE_DIGEST existing_workloads_unchanged=true rollback_retained=true conversation_authority=none"
