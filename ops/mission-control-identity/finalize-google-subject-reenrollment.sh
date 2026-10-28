#!/usr/bin/env bash
# Finalize a previously prepared one-time Google-subject reenrollment.
# The script validates a digest-only pending record, atomically installs it,
# restores the ordinary R3 metadata-only probe, and rolls back to the former
# digest and former probe on any failure before completion.
set -euo pipefail

: "${IMAGE_DIGEST:?Set immutable image digest}"
: "${R3_ACTIVATOR_FILE:?Set hash-verified R3 activator path}"
: "${FINALIZATION_ACKNOWLEDGEMENT:?Set explicit acknowledgement}"

CURRENT=/opt/phil-ai-os-platform/mission-control/secrets/google-ceo-subject-digest
PENDING=/opt/phil-ai-os-platform/mission-control/secrets/google-ceo-subject-digest-reenrollment-pending
BACKUP=/opt/phil-ai-os-platform/mission-control/secrets/google-ceo-subject-digest-reenrollment-backup
CONTAINER=phil-ai-os-mission-control-google-identity-probe
REENROLLMENT_ROLLBACK=${CONTAINER}-reenrollment-rollback
R3_ACTIVATOR_SHA256=154120fa74cb0594d32de1401c68317cc2a0352588d2ddb4b21c20130d625578

[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
test "$FINALIZATION_ACKNOWLEDGEMENT" = approve-google-subject-reenrollment-finalization
test -f "$R3_ACTIVATOR_FILE"
test "$(sha256sum "$R3_ACTIVATOR_FILE" | awk '{print $1}')" = "$R3_ACTIVATOR_SHA256"
test "$(stat -c '%u:%g:%a' "$CURRENT")" = '0:10002:640'
test "$(stat -c '%u:%g:%a' "$PENDING")" = '0:10002:660'
grep -Eq '^sha256:[a-f0-9]{64}$' "$CURRENT"
grep -Eq '^sha256:[a-f0-9]{64}$' "$PENDING"
! cmp -s "$CURRENT" "$PENDING"
test ! -e "$BACKUP"
test "$(docker inspect "$CONTAINER" --format '{{.State.Running}}')" = true
docker inspect "$REENROLLMENT_ROLLBACK" >/dev/null
test "$(docker inspect "$REENROLLMENT_ROLLBACK" --format '{{.State.Running}}')" = false

COMMITTED=false
cleanup() {
  local status="$1"
  trap - EXIT ERR HUP INT TERM
  if [[ "$COMMITTED" == false ]]; then
    rm -f -- "$PENDING" "$BACKUP"
    exit "$status"
  fi
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  install -o root -g 10002 -m 640 "$BACKUP" "$CURRENT" || true
  if docker inspect "$REENROLLMENT_ROLLBACK" >/dev/null 2>&1; then
    docker rename "$REENROLLMENT_ROLLBACK" "$CONTAINER" || true
    docker start "$CONTAINER" >/dev/null || true
  fi
  rm -f -- "$PENDING" "$BACKUP"
  echo "google_subject_reenrollment_finalization_failed=true rollback_attempted=true authority_effect=none" >&2
  exit "$status"
}
trap 'cleanup "$?"' EXIT ERR HUP INT TERM

install -o root -g 10002 -m 640 "$CURRENT" "$BACKUP"
install -o root -g 10002 -m 640 "$PENDING" "$CURRENT"
cmp -s "$CURRENT" "$PENDING"
COMMITTED=true

IMAGE_DIGEST="$IMAGE_DIGEST" \
CLIENT_SECRET_FILE=/opt/phil-ai-os-platform/mission-control/secrets/google-identity-probe-client-secret \
SIGNING_KEY_FILE=/opt/phil-ai-os-platform/mission-control/secrets/google-r3-attestation-hmac-key \
SUBJECT_FILE="$CURRENT" \
WRITER_PASSWORD_FILE=/opt/phil-ai-os-platform/mission-control/secrets/mission-control-postgres-attestation-writer-password \
DB_NETWORK=buzz-prod_buzz-net \
HOSTNAME=miscon.phireij.cloud \
MISSION_CONTROL_R3_METADATA_WRITER_ACTIVATION_ACKNOWLEDGEMENT=approve-r3-metadata-writer-runtime \
bash "$R3_ACTIVATOR_FILE" >/dev/null

test "$(docker inspect "$CONTAINER" --format '{{.State.Running}}')" = true
docker exec "$CONTAINER" python3 -c '
from urllib.request import Request, urlopen
request = Request("http://127.0.0.1:8092/auth/google/healthz", headers={"Host": "miscon.phireij.cloud"})
with urlopen(request, timeout=5) as response:
    assert response.status == 200
    assert response.read(100) == b"probe_ready;authority_effect=none"
'
docker rm "$REENROLLMENT_ROLLBACK" >/dev/null
rm -f -- "$PENDING" "$BACKUP"
COMMITTED=false
trap - EXIT ERR HUP INT TERM
echo 'google_subject_reenrollment_finalized=true r3_metadata_writer_restored=true authority_effect=none'
