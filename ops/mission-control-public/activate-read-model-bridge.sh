#!/usr/bin/env bash
set -euo pipefail
: "${IMAGE_DIGEST:?Set IMAGE_DIGEST}"
: "${CEO_TOKEN_FILE:?Set CEO_TOKEN_FILE}"
: "${HOSTNAME:?Set HOSTNAME}"
[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
IMAGE="ghcr.io/${GITHUB_REPOSITORY:-phireij/phil-ai-os-platform}/mission-control-read-model-bridge"
CONTAINER="phil-ai-os-mission-control-read-model-bridge"
ROLLBACK="${CONTAINER}-rollback"
PREFLIGHT="${CONTAINER}-preflight"
PREFLIGHT_STARTED=false
OLD_STAGED=false
NEW_STARTED=false
restore_on_error() {
  status=$?
  trap - ERR HUP INT TERM
  if [[ "$status" -eq 0 ]]; then status=1; fi
  if [[ "$PREFLIGHT_STARTED" == true ]]; then docker rm -f "$PREFLIGHT" >/dev/null 2>&1 || true; fi
  if [[ "$OLD_STAGED" == true ]]; then
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
    if docker inspect "$ROLLBACK" >/dev/null 2>&1; then
      docker rename "$ROLLBACK" "$CONTAINER" || true
      docker start "$CONTAINER" >/dev/null || true
    fi
  elif [[ "$NEW_STARTED" == true ]]; then
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  fi
  echo "bridge_deploy_failed status=$status rollback_attempted=$OLD_STAGED" >&2
  exit "$status"
}
trap restore_on_error ERR HUP INT TERM
while read -r candidate; do
  image="$(docker inspect "$candidate" --format '{{.Config.Image}}')"
  service="$(docker inspect "$candidate" --format '{{index .Config.Labels "com.docker.compose.service"}}')"
  if [[ "$image" == traefik:* || "$service" == traefik ]]; then TRAEFIK_CONTAINER="$candidate"; break; fi
done < <(docker ps --format '{{.Names}}')
test -n "$TRAEFIK_CONTAINER"
test -s "$CEO_TOKEN_FILE"
test "$(docker inspect "$CONTAINER" --format '{{.State.Running}}')" = true
if docker inspect "$ROLLBACK" >/dev/null 2>&1 || docker inspect "$PREFLIGHT" >/dev/null 2>&1; then
  echo "Refusing deploy: bridge rollback or preflight container already exists" >&2
  exit 1
fi
BEFORE="$(docker ps --format '{{.Names}}|{{.Image}}' | grep -v "^$CONTAINER|" | sort)"
docker pull "$IMAGE@$IMAGE_DIGEST" >/dev/null
PREFLIGHT_STARTED=true
docker run -d --name "$PREFLIGHT" --network host --read-only --cap-drop ALL --security-opt no-new-privileges:true --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --env 'MISSION_CONTROL_BRIDGE_HOST=127.0.0.1' \
  --env 'MISSION_CONTROL_BRIDGE_PORT=18091' \
  --env 'MISSION_CONTROL_CEO_TOKEN_FILE=/run/secrets/mission_control_ceo_token' \
  --env 'MISSION_CONTROL_READ_MODEL_URL=http://127.0.0.1:4881/api/read-model' \
  --mount "type=bind,src=$CEO_TOKEN_FILE,dst=/run/secrets/mission_control_ceo_token,readonly" \
  --label 'traefik.enable=false' \
  "$IMAGE@$IMAGE_DIGEST" >/dev/null
sleep 2
test "$(docker inspect "$PREFLIGHT" --format '{{.State.Running}}')" = true
docker exec "$PREFLIGHT" python3 -c '
import json
from pathlib import Path
from urllib.request import Request, urlopen
token = Path("/run/secrets/mission_control_ceo_token").read_text().strip()
assert token
request = Request("http://127.0.0.1:18091/api/agent-posture", headers={"Authorization": "Bearer " + token})
with urlopen(request, timeout=15) as response:
    body = json.load(response)
    assert response.status == 200
assert body["contract_version"] == 2 and body["authority_effect"] == "none"
assert all(agent["readiness"]["grants_authority"] is False for agent in body["multi_agent"]["agents"])
'
docker rm -f "$PREFLIGHT" >/dev/null
PREFLIGHT_STARTED=false
docker rename "$CONTAINER" "$ROLLBACK"
OLD_STAGED=true
docker stop "$ROLLBACK" >/dev/null
NEW_STARTED=true
docker run -d --name "$CONTAINER" --restart unless-stopped --network host --read-only --cap-drop ALL --security-opt no-new-privileges:true --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --env "MISSION_CONTROL_CEO_TOKEN_FILE=/run/secrets/mission_control_ceo_token" \
  --env "MISSION_CONTROL_READ_MODEL_URL=http://127.0.0.1:4881/api/read-model" \
  --mount "type=bind,src=$CEO_TOKEN_FILE,dst=/run/secrets/mission_control_ceo_token,readonly" \
  --label "traefik.enable=true" \
  --label "traefik.http.routers.mission-control-agent-posture.rule=Host(\`$HOSTNAME\`) && Path(\`/api/agent-posture\`)" \
  --label 'traefik.http.routers.mission-control-agent-posture.priority=110' \
  --label 'traefik.http.routers.mission-control-agent-posture.entrypoints=web,websecure' \
  --label 'traefik.http.routers.mission-control-agent-posture.tls=true' \
  --label 'traefik.http.routers.mission-control-agent-posture.tls.certresolver=letsencrypt' \
  --label 'traefik.http.routers.mission-control-agent-posture.service=mission-control-agent-posture' \
  --label 'traefik.http.services.mission-control-agent-posture.loadbalancer.server.port=8091' \
  "$IMAGE@$IMAGE_DIGEST" >/dev/null
sleep 5
test "$(docker inspect "$CONTAINER" --format '{{.State.Running}}')" = true
test "$(docker inspect "$CONTAINER" --format '{{.Config.Image}}')" = "$IMAGE@$IMAGE_DIGEST"
test "$(docker inspect "$CONTAINER" --format '{{.HostConfig.NetworkMode}}')" = host
test "$(docker inspect "$CONTAINER" --format '{{.HostConfig.ReadonlyRootfs}}')" = true
AFTER="$(docker ps --format '{{.Names}}|{{.Image}}' | sort)"
test "$BEFORE" = "$(printf '%s\n' "$AFTER" | grep -v "^$CONTAINER|")"
trap - ERR HUP INT TERM
echo "container=$CONTAINER image=$IMAGE@$IMAGE_DIGEST route=https://$HOSTNAME/api/agent-posture rollback_container=$ROLLBACK traefik_container=$TRAEFIK_CONTAINER existing_workloads_unchanged=true"
