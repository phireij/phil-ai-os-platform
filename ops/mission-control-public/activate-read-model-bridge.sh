#!/usr/bin/env bash
set -euo pipefail
: "${IMAGE_DIGEST:?Set IMAGE_DIGEST}"
: "${CEO_TOKEN_FILE:?Set CEO_TOKEN_FILE}"
: "${HOSTNAME:?Set HOSTNAME}"
IMAGE="ghcr.io/${GITHUB_REPOSITORY:-phireij/phil-ai-os-platform}/mission-control-read-model-bridge"
CONTAINER="phil-ai-os-mission-control-read-model-bridge"
TRAEFIK_CONTAINER=""
on_error() {
  status=$?
  echo "bridge_deploy_failed status=$status" >&2
  docker logs --tail 100 "$CONTAINER" 2>&1 || true
  exit "$status"
}
trap on_error ERR
while read -r candidate; do
  image="$(docker inspect "$candidate" --format '{{.Config.Image}}')"
  service="$(docker inspect "$candidate" --format '{{index .Config.Labels "com.docker.compose.service"}}')"
  if [[ "$image" == traefik:* || "$service" == traefik ]]; then TRAEFIK_CONTAINER="$candidate"; break; fi
done < <(docker ps --format '{{.Names}}')
test -n "$TRAEFIK_CONTAINER"
test -s "$CEO_TOKEN_FILE"
BEFORE="$(docker ps --format '{{.Names}}|{{.Image}}' | grep -v "^$CONTAINER|" | sort)"
if docker ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER"; then docker rm -f "$CONTAINER" >/dev/null; fi
docker pull "$IMAGE@$IMAGE_DIGEST" >/dev/null
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
echo "container=$CONTAINER image=$IMAGE@$IMAGE_DIGEST route=https://$HOSTNAME/api/agent-posture traefik_container=$TRAEFIK_CONTAINER existing_workloads_unchanged=true"
