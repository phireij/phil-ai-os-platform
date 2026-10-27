#!/usr/bin/env bash
# Prepare a one-time, reversible Google-subject reenrollment container.
# The existing protected digest remains unchanged until a separate finalizer
# validates and installs a newly enrolled digest.
set -euo pipefail

: "${IMAGE_DIGEST:?Set immutable image digest}"
: "${CLIENT_SECRET_FILE:?Set protected Google client-secret file}"
: "${HOSTNAME:?Set Mission Control hostname}"
: "${REENROLLMENT_ACKNOWLEDGEMENT:?Set explicit acknowledgement}"

CURRENT=/opt/phil-ai-os-platform/mission-control/secrets/google-ceo-subject-digest
PENDING=/opt/phil-ai-os-platform/mission-control/secrets/google-ceo-subject-digest-reenrollment-pending
CONTAINER=phil-ai-os-mission-control-google-identity-probe
ROLLBACK=${CONTAINER}-reenrollment-rollback
PREFLIGHT=${CONTAINER}-reenrollment-preflight
IMAGE=ghcr.io/phireij/phil-ai-os-platform/mission-control-google-identity-probe

[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
test "$CLIENT_SECRET_FILE" = /opt/phil-ai-os-platform/mission-control/secrets/google-identity-probe-client-secret
test "$HOSTNAME" = miscon.phireij.cloud
test "$REENROLLMENT_ACKNOWLEDGEMENT" = approve-google-subject-reenrollment
test "$(stat -c '%u:%g:%a' "$CLIENT_SECRET_FILE")" = '0:10002:640'
test "$(stat -c '%u:%g:%a' "$CURRENT")" = '0:0:400'
grep -Eq '^sha256:[a-f0-9]{64}$' "$CURRENT"
test ! -e "$PENDING"
! docker inspect "$ROLLBACK" >/dev/null 2>&1
! docker inspect "$PREFLIGHT" >/dev/null 2>&1

NEW_STARTED=false
OLD_STAGED=false
restore() {
  local status="$1"
  trap - EXIT ERR HUP INT TERM
  docker rm -f "$PREFLIGHT" >/dev/null 2>&1 || true
  if [[ "$NEW_STARTED" == true ]]; then docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; fi
  if [[ "$OLD_STAGED" == true ]] && docker inspect "$ROLLBACK" >/dev/null 2>&1; then
    docker rename "$ROLLBACK" "$CONTAINER" || true
    docker start "$CONTAINER" >/dev/null || true
  fi
  rm -f -- "$PENDING"
  exit "$status"
}
trap 'restore "$?"' EXIT ERR HUP INT TERM

install -o root -g 10002 -m 660 /dev/null "$PENDING"
printf 'pending\n' > "$PENDING"
test "$(stat -c '%u:%g:%a' "$PENDING")" = '0:10002:660'
test "$(cat "$PENDING")" = pending

MOUNTS=(
  --mount "type=bind,src=$CLIENT_SECRET_FILE,dst=/run/secrets/client_secret,readonly"
  --mount "type=bind,src=$PENDING,dst=/run/secrets/ceo_subject_digest"
)
ENV=(
  --env 'MISSION_CONTROL_GOOGLE_PROBE_ENABLED=true'
  --env 'MISSION_CONTROL_GOOGLE_CLIENT_ID=531519060424-c2n6uclfuko18tubr9ejs9o2fhf8s4c1.apps.googleusercontent.com'
  --env 'MISSION_CONTROL_GOOGLE_CLIENT_SECRET_FILE=/run/secrets/client_secret'
  --env 'MISSION_CONTROL_GOOGLE_SUBJECT_ENROLLMENT_ENABLED=true'
  --env 'MISSION_CONTROL_GOOGLE_SUBJECT_ENROLLMENT_FILE=/run/secrets/ceo_subject_digest'
)

docker pull "$IMAGE@$IMAGE_DIGEST" >/dev/null
docker run -d --name "$PREFLIGHT" --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m "${ENV[@]}" "${MOUNTS[@]}" --label 'traefik.enable=false' "$IMAGE@$IMAGE_DIGEST" >/dev/null
sleep 2
test "$(docker inspect "$PREFLIGHT" --format '{{.State.Running}}')" = true
docker rm -f "$PREFLIGHT" >/dev/null

docker rename "$CONTAINER" "$ROLLBACK"
OLD_STAGED=true
docker stop "$ROLLBACK" >/dev/null
NEW_STARTED=true
docker run -d --name "$CONTAINER" --restart unless-stopped --network bridge --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m "${ENV[@]}" "${MOUNTS[@]}" \
  --label 'traefik.enable=true' --label 'traefik.docker.network=bridge' \
  --label "traefik.http.routers.mission-control-google-probe.rule=Host(\`$HOSTNAME\`) && PathPrefix(\`/auth/google\`)" \
  --label 'traefik.http.routers.mission-control-google-probe.priority=120' \
  --label 'traefik.http.routers.mission-control-google-probe.entrypoints=websecure' \
  --label 'traefik.http.routers.mission-control-google-probe.tls=true' \
  --label 'traefik.http.routers.mission-control-google-probe.tls.certresolver=letsencrypt' \
  --label 'traefik.http.routers.mission-control-google-probe.service=mission-control-google-probe' \
  --label 'traefik.http.services.mission-control-google-probe.loadbalancer.server.port=8092' \
  "$IMAGE@$IMAGE_DIGEST" >/dev/null
sleep 3
test "$(docker inspect "$CONTAINER" --format '{{.State.Running}}')" = true
test "$(docker inspect "$CONTAINER" --format '{{.HostConfig.ReadonlyRootfs}}')" = true
trap - EXIT ERR HUP INT TERM
echo "google_subject_reenrollment_prepared=true pending_file_mode=$(stat -c '%u:%g:%a' "$PENDING") authority_effect=none"
