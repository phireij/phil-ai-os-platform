#!/usr/bin/env bash
# Stages exactly one Google client secret from stdin into a newly created,
# per-run Docker volume. The caller must supply the secret through stdin only.
set -euo pipefail

: "${IMAGE:?Set the immutable Google identity-probe image repository}"
: "${IMAGE_DIGEST:?Set the immutable Google identity-probe image digest}"
: "${SECRET_VOLUME:?Set the newly allocated per-run secret volume}"

test "$IMAGE" = 'ghcr.io/phireij/phil-ai-os-platform/mission-control-google-identity-probe'
[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "$SECRET_VOLUME" =~ ^phil-ai-os-mc-google-probe-secret-[0-9]+$ ]]
! docker volume inspect "$SECRET_VOLUME" >/dev/null 2>&1

created=false
cleanup() {
  if [[ "$created" == true ]]; then
    docker volume rm "$SECRET_VOLUME" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT HUP INT TERM

docker volume create "$SECRET_VOLUME" >/dev/null
created=true
docker run --rm -i \
  --user 0:0 \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --entrypoint /bin/sh \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets" \
  "$IMAGE@$IMAGE_DIGEST" \
  -c 'umask 077; cat > /run/secrets/client_secret; chown 10002:10002 /run/secrets/client_secret; chmod 400 /run/secrets/client_secret; test -s /run/secrets/client_secret; test "$(wc -c < /run/secrets/client_secret)" -le 4096'

trap - EXIT HUP INT TERM
created=false
echo 'google_probe_secret_volume_staged=true'
