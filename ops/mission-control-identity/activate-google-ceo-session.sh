#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE_DIGEST:?Set immutable image digest}"
: "${SECRET_VOLUME:?Set the per-run protected Docker secret volume}"
: "${HOSTNAME:?Set the Mission Control hostname}"
[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "$SECRET_VOLUME" =~ ^phil-ai-os-mc-google-session-secret-[0-9]+-[0-9]+$ ]]
test "$HOSTNAME" = miscon.phireij.cloud

IMAGE=ghcr.io/phireij/phil-ai-os-platform/mission-control-google-ceo-session
PROBE=phil-ai-os-mission-control-google-identity-probe
ROLLBACK="${PROBE}-rollback"
SESSION=phil-ai-os-mission-control-google-ceo-session
PREFLIGHT="${SESSION}-preflight"
EXPECTED_PROBE=ghcr.io/phireij/phil-ai-os-platform/mission-control-google-identity-probe@sha256:bb98a21f6d81b904eda969c548132e7963d5383d893fb1a20c9ef47e502b99c8
PREFLIGHT_STARTED=false
PROBE_STAGED=false
SESSION_STARTED=false

restore_and_exit() {
  local status="$1"
  trap - ERR HUP INT TERM
  if [[ "$PREFLIGHT_STARTED" == true ]]; then docker rm -f "$PREFLIGHT" >/dev/null 2>&1 || true; fi
  if [[ "$SESSION_STARTED" == true ]]; then docker rm -f "$SESSION" >/dev/null 2>&1 || true; fi
  if [[ "$PROBE_STAGED" == true ]] && docker inspect "$ROLLBACK" >/dev/null 2>&1; then
    docker rename "$ROLLBACK" "$PROBE" || true
    docker start "$PROBE" >/dev/null || true
  fi
  echo "google_ceo_session_activation_failed status=$status rollback_attempted=$PROBE_STAGED" >&2
  exit "$status"
}
trap 'restore_and_exit "$?"' ERR
trap 'restore_and_exit 129' HUP
trap 'restore_and_exit 130' INT
trap 'restore_and_exit 143' TERM

test "$(docker volume inspect "$SECRET_VOLUME" --format '{{.Name}}')" = "$SECRET_VOLUME"
if docker inspect "$ROLLBACK" >/dev/null 2>&1 || docker inspect "$SESSION" >/dev/null 2>&1 || docker inspect "$PREFLIGHT" >/dev/null 2>&1; then
  echo 'Refusing activation: session, rollback, or preflight container already exists' >&2
  exit 1
fi
test "$(docker inspect "$PROBE" --format '{{.State.Running}}')" = true
test "$(docker inspect "$PROBE" --format '{{.Config.Image}}')" = "$EXPECTED_PROBE"
test "$(docker inspect "$PROBE" --format '{{.HostConfig.NetworkMode}}')" = bridge

TRAEFIK_CONTAINER=''
while read -r candidate; do
  image="$(docker inspect "$candidate" --format '{{.Config.Image}}')"
  service="$(docker inspect "$candidate" --format '{{index .Config.Labels "com.docker.compose.service"}}')"
  if [[ "$image" == traefik:* || "$service" == traefik ]]; then TRAEFIK_CONTAINER="$candidate"; break; fi
done < <(docker ps --format '{{.Names}}')
test -n "$TRAEFIK_CONTAINER"

# The current probe is the only permitted router for this host's /auth path.
python3 - "$PROBE" "$HOSTNAME" <<'PY'
import json
import subprocess
import sys

probe, hostname = sys.argv[1:]
names = subprocess.check_output(['docker', 'ps', '--format', '{{.Names}}'], text=True).splitlines()
for name in names:
    if name == probe:
        continue
    item = json.loads(subprocess.check_output(['docker', 'inspect', name], text=True))[0]
    labels = (item.get('Config') or {}).get('Labels') or {}
    for key, rule in labels.items():
        if key.startswith('traefik.http.routers.') and key.endswith('.rule'):
            if hostname in rule and '/auth' in rule:
                raise SystemExit('google_ceo_session_route_collision')
print('google_ceo_session_route_collision=none')
PY

BEFORE="$(docker ps --format '{{.Names}}|{{.Image}}' | awk -F'|' -v p="$PROBE" '$1 != p' | sort)"
docker pull "$IMAGE@$IMAGE_DIGEST" >/dev/null
docker run --rm --network none --user 0:0 --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
  --entrypoint /bin/sh "$IMAGE@$IMAGE_DIGEST" \
  -c 'test "$(stat -c "%u:%a" /run/secrets/client_secret)" = "10003:400" && test "$(stat -c "%u:%a" /run/secrets/ceo_binding)" = "10003:400" && test -s /run/secrets/client_secret && test -s /run/secrets/ceo_binding'

OIDC_ENV=(
  --env 'MISSION_CONTROL_GOOGLE_OIDC_ENABLED=true'
  --env 'MISSION_CONTROL_GOOGLE_OIDC_ISSUER=https://accounts.google.com'
  --env 'MISSION_CONTROL_GOOGLE_REDIRECT_URI=https://miscon.phireij.cloud/auth/google/callback'
  --env 'MISSION_CONTROL_GOOGLE_CLIENT_ID=531519060424-c2n6uclfuko18tubr9ejs9o2fhf8s4c1.apps.googleusercontent.com'
  --env 'MISSION_CONTROL_GOOGLE_CLIENT_SECRET_FILE=/run/secrets/client_secret'
  --env 'MISSION_CONTROL_GOOGLE_CEO_SUBJECT_FILE=/run/secrets/ceo_binding'
)

PREFLIGHT_STARTED=true
docker run -d --name "$PREFLIGHT" --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  "${OIDC_ENV[@]}" \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets,readonly" \
  --label 'traefik.enable=false' \
  "$IMAGE@$IMAGE_DIGEST" >/dev/null
sleep 2
test "$(docker inspect "$PREFLIGHT" --format '{{.State.Running}}')" = true
docker rm -f "$PREFLIGHT" >/dev/null
PREFLIGHT_STARTED=false

docker rename "$PROBE" "$ROLLBACK"
PROBE_STAGED=true
docker stop "$ROLLBACK" >/dev/null

SESSION_STARTED=true
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
test "$(docker inspect "$SESSION" --format '{{.State.Running}}')" = true
test "$(docker inspect "$SESSION" --format '{{.Config.Image}}')" = "$IMAGE@$IMAGE_DIGEST"
test "$(docker inspect "$SESSION" --format '{{.HostConfig.NetworkMode}}')" = bridge
test "$(docker inspect "$SESSION" --format '{{.HostConfig.ReadonlyRootfs}}')" = true
AFTER="$(docker ps --format '{{.Names}}|{{.Image}}' | awk -F'|' -v s="$SESSION" '$1 != s' | sort)"
test "$BEFORE" = "$AFTER"

trap - ERR HUP INT TERM
echo "google_ceo_session_activated=true image=$IMAGE@$IMAGE_DIGEST route=https://$HOSTNAME/auth/google existing_workloads_unchanged=true probe_rollback_staged=true conversation_authority=none"
