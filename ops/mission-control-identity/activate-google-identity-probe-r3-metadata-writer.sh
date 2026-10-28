#!/usr/bin/env bash
# Replaces only the existing identity probe with a private R3 metadata writer.
# It never adds a public route, session, or action adapter.
set -euo pipefail

: "${IMAGE_DIGEST:?Set immutable image digest}"
: "${CLIENT_SECRET_FILE:?Set protected Google client-secret file}"
: "${SIGNING_KEY_FILE:?Set protected R3 signing-key file}"
: "${SUBJECT_FILE:?Set protected CEO subject-digest file}"
: "${WRITER_PASSWORD_FILE:?Set protected writer-password file}"
: "${DB_NETWORK:?Set the dedicated private database network}"
: "${HOSTNAME:?Set the Mission Control hostname}"
: "${MISSION_CONTROL_R3_METADATA_WRITER_ACTIVATION_ACKNOWLEDGEMENT:?Set explicit acknowledgement}"

[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
test "$CLIENT_SECRET_FILE" = /opt/phil-ai-os-platform/mission-control/secrets/google-identity-probe-client-secret
test "$SIGNING_KEY_FILE" = /opt/phil-ai-os-platform/mission-control/secrets/google-r3-attestation-hmac-key
test "$SUBJECT_FILE" = /opt/phil-ai-os-platform/mission-control/secrets/google-ceo-subject-digest
test "$WRITER_PASSWORD_FILE" = /opt/phil-ai-os-platform/mission-control/secrets/mission-control-postgres-attestation-writer-password
test "$DB_NETWORK" = buzz-prod_buzz-net
test "$HOSTNAME" = miscon.phireij.cloud
test "$MISSION_CONTROL_R3_METADATA_WRITER_ACTIVATION_ACKNOWLEDGEMENT" = 'approve-r3-metadata-writer-runtime'
test "$(stat -c '%u:%g:%a' "$CLIENT_SECRET_FILE")" = '0:10002:640'
test "$(stat -c '%u:%g:%a' "$SIGNING_KEY_FILE")" = '0:10002:640'
test "$(stat -c '%u:%g:%a' "$SUBJECT_FILE")" = '0:10002:640'
test "$(stat -c '%u:%g:%a' "$WRITER_PASSWORD_FILE")" = '0:10002:640'

IMAGE='ghcr.io/phireij/phil-ai-os-platform/mission-control-google-identity-probe'
CONTAINER='phil-ai-os-mission-control-google-identity-probe'
PREFLIGHT="${CONTAINER}-r3-writer-preflight"
ROLLBACK="${CONTAINER}-r3-writer-rollback"
NEW_CREATED=false
OLD_STAGED=false

restore_and_exit() {
  local status="$1"
  trap - EXIT ERR HUP INT TERM
  docker rm -f "$PREFLIGHT" >/dev/null 2>&1 || true
  if [[ "$NEW_CREATED" == true ]]; then docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; fi
  if [[ "$OLD_STAGED" == true ]] && docker inspect "$ROLLBACK" >/dev/null 2>&1; then
    docker rename "$ROLLBACK" "$CONTAINER" || true
    docker start "$CONTAINER" >/dev/null || true
  fi
  echo "r3_metadata_writer_activation_failed status=$status rollback_attempted=$OLD_STAGED" >&2
  exit "$status"
}
trap 'restore_and_exit "$?"' EXIT ERR HUP INT TERM

! docker inspect "$PREFLIGHT" >/dev/null 2>&1
! docker inspect "$ROLLBACK" >/dev/null 2>&1
test "$(docker inspect "$CONTAINER" --format '{{.State.Running}}')" = true
test "$(docker inspect "$CONTAINER" --format '{{.HostConfig.NetworkMode}}')" = bridge

BEFORE="$(docker ps --format '{{.Names}}|{{.Image}}' | awk -F'|' -v c="$CONTAINER" '$1 != c' | sort)"
docker pull "$IMAGE@$IMAGE_DIGEST" >/dev/null

MOUNTS=(
  --mount "type=bind,src=$CLIENT_SECRET_FILE,dst=/run/secrets/client_secret,readonly"
  --mount "type=bind,src=$SIGNING_KEY_FILE,dst=/run/secrets/r3_signing_key,readonly"
  --mount "type=bind,src=$SUBJECT_FILE,dst=/run/secrets/ceo_subject_digest,readonly"
  --mount "type=bind,src=$WRITER_PASSWORD_FILE,dst=/run/secrets/attestation_writer_password,readonly"
)
RUNTIME_ENV=(
  --env 'MISSION_CONTROL_GOOGLE_PROBE_ENABLED=true'
  --env 'MISSION_CONTROL_GOOGLE_CLIENT_ID=531519060424-c2n6uclfuko18tubr9ejs9o2fhf8s4c1.apps.googleusercontent.com'
  --env 'MISSION_CONTROL_GOOGLE_CLIENT_SECRET_FILE=/run/secrets/client_secret'
  --env 'MISSION_CONTROL_R3_ATTESTATION_RUNTIME_ENABLED=true'
  --env 'MISSION_CONTROL_R3_ATTESTATION_HANDOFF_ENABLED=true'
  --env 'MISSION_CONTROL_R3_ATTESTATION_ISSUER=https://accounts.google.com'
  --env 'MISSION_CONTROL_R3_ATTESTATION_SIGNING_KEY_FILE=/run/secrets/r3_signing_key'
  --env 'MISSION_CONTROL_GOOGLE_CEO_SUBJECT_FILE=/run/secrets/ceo_subject_digest'
  --env 'MISSION_CONTROL_R3_ATTESTATION_METADATA_WRITER_ENABLED=true'
  --env 'MISSION_CONTROL_R3_ATTESTATION_DATABASE=mission_control'
  --env 'MISSION_CONTROL_R3_ATTESTATION_WRITER_ROLE=mission_control_attestation_writer'
  --env 'MISSION_CONTROL_R3_ATTESTATION_DATABASE_HOST=buzz-prod-postgres-1'
  --env 'MISSION_CONTROL_R3_ATTESTATION_DATABASE_PORT=5432'
  --env 'MISSION_CONTROL_R3_ATTESTATION_WRITER_PASSWORD_FILE=/run/secrets/attestation_writer_password'
)

docker run -d --name "$PREFLIGHT" --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  "${RUNTIME_ENV[@]}" "${MOUNTS[@]}" --label 'traefik.enable=false' "$IMAGE@$IMAGE_DIGEST" >/dev/null
sleep 2
test "$(docker inspect "$PREFLIGHT" --format '{{.State.Running}}')" = true
docker exec "$PREFLIGHT" sh -c 'test -r /run/secrets/ceo_subject_digest && test "$(stat -c "%u:%g:%a" /run/secrets/ceo_subject_digest)" = "0:10002:640"'
docker rm -f "$PREFLIGHT" >/dev/null

docker rename "$CONTAINER" "$ROLLBACK"
OLD_STAGED=true
docker stop "$ROLLBACK" >/dev/null

NEW_CREATED=true
docker create --name "$CONTAINER" --restart unless-stopped --network bridge \
  --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  "${RUNTIME_ENV[@]}" "${MOUNTS[@]}" \
  --label 'traefik.enable=true' \
  --label 'traefik.docker.network=bridge' \
  --label "traefik.http.routers.mission-control-google-probe.rule=Host(\`$HOSTNAME\`) && PathPrefix(\`/auth/google\`)" \
  --label 'traefik.http.routers.mission-control-google-probe.priority=120' \
  --label 'traefik.http.routers.mission-control-google-probe.entrypoints=websecure' \
  --label 'traefik.http.routers.mission-control-google-probe.tls=true' \
  --label 'traefik.http.routers.mission-control-google-probe.tls.certresolver=letsencrypt' \
  --label 'traefik.http.routers.mission-control-google-probe.service=mission-control-google-probe' \
  --label 'traefik.http.services.mission-control-google-probe.loadbalancer.server.port=8092' \
  "$IMAGE@$IMAGE_DIGEST" >/dev/null
docker network connect "$DB_NETWORK" "$CONTAINER"
docker start "$CONTAINER" >/dev/null
sleep 3
test "$(docker inspect "$CONTAINER" --format '{{.State.Running}}')" = true
test "$(docker inspect "$CONTAINER" --format '{{.HostConfig.ReadonlyRootfs}}')" = true
test "$(docker inspect "$CONTAINER" --format '{{.Config.Image}}')" = "$IMAGE@$IMAGE_DIGEST"
test "$(docker inspect "$CONTAINER" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' | xargs)" = 'bridge buzz-prod_buzz-net'
docker exec "$CONTAINER" python3 -c 'import socket; connection = socket.create_connection(("buzz-prod-postgres-1", 5432), 3); connection.close()'
docker exec "$CONTAINER" python3 -c '
from urllib.request import Request, urlopen
request = Request("http://127.0.0.1:8092/auth/google/healthz", headers={"Host": "miscon.phireij.cloud"})
with urlopen(request, timeout=5) as response:
    assert response.status == 200
    assert response.read(100) == b"probe_ready;authority_effect=none"
'
AFTER="$(docker ps --format '{{.Names}}|{{.Image}}' | awk -F'|' -v c="$CONTAINER" '$1 != c' | sort)"
test "$BEFORE" = "$AFTER"
docker rm "$ROLLBACK" >/dev/null
OLD_STAGED=false
trap - EXIT ERR HUP INT TERM
echo "r3_metadata_writer_activated=true image=$IMAGE@$IMAGE_DIGEST private_database_network=$DB_NETWORK public_route_unchanged=true authority_effect=none"
