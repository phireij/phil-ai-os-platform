#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE_DIGEST:?Set IMAGE_DIGEST to the immutable gateway image digest}"
: "${CEO_TOKEN_FILE:?Set CEO_TOKEN_FILE to the mounted CEO token file on the VPS}"
: "${HOSTNAME:?Set HOSTNAME to the dedicated Mission Control gateway hostname}"
ROUTE_PATH_PREFIX="${ROUTE_PATH_PREFIX:-/api}"
CONTROL_API_NETWORK="${CONTROL_API_NETWORK:-phil-ai-os-core_core-net}"
CONTROL_API_TOKEN_SOURCE_FILE="${CONTROL_API_TOKEN_SOURCE_FILE:-/opt/phil-ai-os-platform/phil-ai-os-platform-phase1/infrastructure/core/secrets/hermes_control_api_token}"
CONTROL_API_SECRET_VOLUME="${CONTROL_API_SECRET_VOLUME:-phil-ai-os-mission-control-gateway-secrets}"

IMAGE="ghcr.io/${GITHUB_REPOSITORY:-phireij/phil-ai-os-platform}/mission-control-gateway"
CONTAINER="phil-ai-os-mission-control-gateway"
NETWORK="${DEPLOY_NET:-bridge}"

test -f "$CEO_TOKEN_FILE"
test -s "$CEO_TOKEN_FILE"
test "$(stat -c '%u:%a' "$CEO_TOKEN_FILE")" = "0:640"
test -f "$CONTROL_API_TOKEN_SOURCE_FILE"
test -s "$CONTROL_API_TOKEN_SOURCE_FILE"
if [[ "$HOSTNAME" == "miscon.phireij.cloud" ]]; then
  test "${ALLOW_SHARED_HOSTNAME:-false}" = "true"
  test "$ROUTE_PATH_PREFIX" = "/api"
fi

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
docker network inspect "$CONTROL_API_NETWORK" >/dev/null
docker volume create "$CONTROL_API_SECRET_VOLUME" >/dev/null
docker run --rm -i --user 0:0 --entrypoint /bin/sh -v "$CONTROL_API_SECRET_VOLUME:/run/staged-secrets" "$IMAGE@$IMAGE_DIGEST" -c 'cat > /run/staged-secrets/control_api_token; chown 10001:10001 /run/staged-secrets/control_api_token; chmod 400 /run/staged-secrets/control_api_token' < "$CONTROL_API_TOKEN_SOURCE_FILE"

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
  --env "PHIL_AI_OS_CONTROL_API_URL=http://phil-ai-os-core-control-api-1:4870" \
  --env "PHIL_AI_OS_CONTROL_API_TOKEN_FILE=/run/mission-control-secrets/control_api_token" \
  --mount "type=bind,src=$CEO_TOKEN_FILE,dst=/run/secrets/mission_control_ceo_token,readonly" \
  --mount "type=volume,src=$CONTROL_API_SECRET_VOLUME,dst=/run/mission-control-secrets,readonly" \
  --label "traefik.enable=true" \
  --label "traefik.docker.network=$NETWORK" \
  --label "traefik.http.routers.mission-control-gateway.rule=Host(\`$HOSTNAME\`) && PathPrefix(\`$ROUTE_PATH_PREFIX\`)" \
  --label "traefik.http.routers.mission-control-gateway.priority=100" \
  --label "traefik.http.routers.mission-control-gateway.entrypoints=web,websecure" \
  --label "traefik.http.routers.mission-control-gateway.tls=true" \
  --label "traefik.http.routers.mission-control-gateway.tls.certresolver=letsencrypt" \
  --label "traefik.http.routers.mission-control-gateway.service=mission-control-gateway" \
  --label "traefik.http.services.mission-control-gateway.loadbalancer.server.port=8090" \
  "$IMAGE@$IMAGE_DIGEST" >/dev/null

docker network connect "$CONTROL_API_NETWORK" "$CONTAINER"

sleep 5
test "$(docker inspect "$CONTAINER" --format '{{.State.Running}}')" = "true"
AFTER="$(docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}' | sort)"
test "$BEFORE" = "$(printf '%s\n' "$AFTER" | grep -v "^$CONTAINER|")"
echo "container=$CONTAINER image=$IMAGE@$IMAGE_DIGEST route=https://$HOSTNAME$ROUTE_PATH_PREFIX control_api_network=$CONTROL_API_NETWORK traefik_container=$TRAEFIK_CONTAINER existing_workloads_unchanged=true"
