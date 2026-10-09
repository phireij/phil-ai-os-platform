#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE_DIGEST:?Set IMAGE_DIGEST to the immutable gateway image digest}"
: "${CEO_TOKEN_FILE:?Set CEO_TOKEN_FILE to the mounted CEO token file on the VPS}"
: "${HOSTNAME:?Set HOSTNAME to the dedicated Mission Control gateway hostname}"

IMAGE="ghcr.io/${GITHUB_REPOSITORY:-phireij/phil-ai-os-platform}/mission-control-gateway"
CONTAINER="phil-ai-os-mission-control-gateway"
NETWORK="${DEPLOY_NET:-bridge}"

test -f "$CEO_TOKEN_FILE"
test -s "$CEO_TOKEN_FILE"
test "$HOSTNAME" != "miscon.phireij.cloud" || test "${ALLOW_SHARED_HOSTNAME:-false}" = "true"

TRAEFIK_CONTAINER=""
while read -r candidate; do
  image="$(docker inspect "$candidate" --format '{{.Config.Image}}')"
  service="$(docker inspect "$candidate" --format '{{index .Config.Labels "com.docker.compose.service"}}')"
  if [[ "$image" == traefik:* || "$service" == "traefik" ]]; then
    TRAEFIK_CONTAINER="$candidate"
    break
  fi
done < <(docker ps --format '{{.Names}}')
test -n "$TRAEFIK_CONTAINER"

BEFORE="$(docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}' | sort)"
if docker ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER"; then
  docker rm -f "$CONTAINER" >/dev/null
fi

docker pull "$IMAGE@$IMAGE_DIGEST" >/dev/null
docker run -d \
  --name "$CONTAINER" \
  --restart unless-stopped \
  --network "$NETWORK" \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --env "MISSION_CONTROL_CEO_TOKEN_FILE=/run/secrets/mission_control_ceo_token" \
  --mount "type=bind,src=$CEO_TOKEN_FILE,dst=/run/secrets/mission_control_ceo_token,readonly" \
  --label "traefik.enable=true" \
  --label "traefik.http.routers.mission-control-gateway.rule=Host(\`$HOSTNAME\`)" \
  --label "traefik.http.routers.mission-control-gateway.entrypoints=web,websecure" \
  --label "traefik.http.routers.mission-control-gateway.tls=true" \
  --label "traefik.http.routers.mission-control-gateway.tls.certresolver=letsencrypt" \
  --label "traefik.http.routers.mission-control-gateway.service=mission-control-gateway" \
  --label "traefik.http.services.mission-control-gateway.loadbalancer.server.port=8090" \
  "$IMAGE@$IMAGE_DIGEST" >/dev/null

sleep 5
test "$(docker inspect "$CONTAINER" --format '{{.State.Running}}')" = "true"
AFTER="$(docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}' | sort)"
test "$BEFORE" = "$(printf '%s\n' "$AFTER" | grep -v "^$CONTAINER|")"
echo "container=$CONTAINER image=$IMAGE@$IMAGE_DIGEST traefik_container=$TRAEFIK_CONTAINER existing_workloads_unchanged=true"
