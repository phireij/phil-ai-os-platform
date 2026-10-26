#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE_DIGEST:?Set immutable image digest}"
: "${SECRET_FILE:?Set the root-owned protected Google client secret file}"
: "${HOSTNAME:?Set the Mission Control hostname}"
: "${MISSION_CONTROL_GOOGLE_PROBE_ACTIVATION_ACKNOWLEDGEMENT:?Set the explicit activation acknowledgement}"
[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
test "$SECRET_FILE" = /opt/phil-ai-os-platform/mission-control/secrets/google-identity-probe-client-secret
test "$(stat -c '%u:%g:%a' "$SECRET_FILE")" = '0:10002:640'
test "$HOSTNAME" = miscon.phireij.cloud
test "$MISSION_CONTROL_GOOGLE_PROBE_ACTIVATION_ACKNOWLEDGEMENT" = 'approve-google-identity-probe-route'

IMAGE="ghcr.io/phireij/phil-ai-os-platform/mission-control-google-identity-probe"
CONTAINER=phil-ai-os-mission-control-google-identity-probe
PREFLIGHT="${CONTAINER}-preflight"
ROLLBACK="${CONTAINER}-rollback"
NEW_STARTED=false
OLD_STAGED=false
PREFLIGHT_STARTED=false

restore_and_exit() {
  local status="$1"
  trap - ERR HUP INT TERM
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
  echo "google_probe_activation_failed status=$status rollback_attempted=$OLD_STAGED" >&2
  exit "$status"
}
trap 'restore_and_exit "$?"' ERR
trap 'restore_and_exit 129' HUP
trap 'restore_and_exit 130' INT
trap 'restore_and_exit 143' TERM

if docker inspect "$ROLLBACK" >/dev/null 2>&1; then
  echo 'Refusing activation: rollback container already exists' >&2
  exit 1
fi

# A prior failed inert preflight can leave behind only its stopped, isolated
# temporary container. Verify every relevant invariant before removing it; a
# rollback container is never treated as disposable recovery state.
if docker inspect "$PREFLIGHT" >/dev/null 2>&1; then
  if ! python3 - "$PREFLIGHT" "$IMAGE" "$SECRET_FILE" <<'PY'
import json
import subprocess
import sys

name, image, secret_file = sys.argv[1:]
item = json.loads(subprocess.check_output(['docker', 'inspect', name], text=True))[0]
config = item.get('Config') or {}
host = item.get('HostConfig') or {}
labels = config.get('Labels') or {}
mounts = item.get('Mounts') or []

assert (item.get('State') or {}).get('Running') is False
assert (host.get('RestartPolicy') or {}).get('Name') == 'no'
assert host.get('NetworkMode') == 'none'
assert host.get('ReadonlyRootfs') is True
assert config.get('Image', '').startswith(f'{image}@sha256:')
assert labels.get('traefik.enable') == 'false'
assert all(not key.startswith('traefik.') or key == 'traefik.enable' for key in labels)
assert [(mount.get('Type'), mount.get('Destination'), mount.get('RW'), mount.get('Source')) for mount in mounts] == [
    ('bind', '/run/secrets/client_secret', False, secret_file),
]
PY
  then
    echo 'google_probe_stale_preflight_contract_failed' >&2
    exit 1
  fi
  docker rm "$PREFLIGHT" >/dev/null
  ! docker inspect "$PREFLIGHT" >/dev/null 2>&1
  echo 'google_probe_stale_preflight_removed=true'
fi

TRAEFIK_CONTAINER=''
while read -r candidate; do
  image="$(docker inspect "$candidate" --format '{{.Config.Image}}')"
  service="$(docker inspect "$candidate" --format '{{index .Config.Labels "com.docker.compose.service"}}')"
  if [[ "$image" == traefik:* || "$service" == traefik ]]; then TRAEFIK_CONTAINER="$candidate"; break; fi
done < <(docker ps --format '{{.Names}}')
test -n "$TRAEFIK_CONTAINER"

# Refuse another live router that already claims this host's /auth path.
python3 - "$CONTAINER" "$HOSTNAME" <<'PY'
import json
import subprocess
import sys

own, hostname = sys.argv[1:]
names = subprocess.check_output(['docker', 'ps', '--format', '{{.Names}}'], text=True).splitlines()
for name in names:
    if name == own:
        continue
    item = json.loads(subprocess.check_output(['docker', 'inspect', name], text=True))[0]
    labels = (item.get('Config') or {}).get('Labels') or {}
    for key, rule in labels.items():
        if key.startswith('traefik.http.routers.') and key.endswith('.rule'):
            if hostname in rule and '/auth' in rule:
                raise SystemExit('google_probe_route_collision')
print('google_probe_route_collision=none')
PY

BEFORE="$(docker ps --format '{{.Names}}|{{.Image}}' | awk -F'|' -v c="$CONTAINER" '$1 != c' | sort)"
docker pull "$IMAGE@$IMAGE_DIGEST" >/dev/null
if ! docker run --rm --network none --user 0:0 --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --mount "type=bind,src=$SECRET_FILE,dst=/run/secrets/client_secret,readonly" \
  --entrypoint /bin/sh "$IMAGE@$IMAGE_DIGEST" \
  -c 'test "$(stat -c "%u:%g:%a" /run/secrets/client_secret)" = "0:10002:640" && test -s /run/secrets/client_secret'; then
  echo 'google_probe_secret_mount_preflight_failed' >&2
  exit 1
fi

PREFLIGHT_STARTED=true
docker run -d --name "$PREFLIGHT" --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --env 'MISSION_CONTROL_GOOGLE_PROBE_ENABLED=true' \
  --env 'MISSION_CONTROL_GOOGLE_CLIENT_ID=531519060424-c2n6uclfuko18tubr9ejs9o2fhf8s4c1.apps.googleusercontent.com' \
  --env 'MISSION_CONTROL_GOOGLE_CLIENT_SECRET_FILE=/run/secrets/client_secret' \
  --mount "type=bind,src=$SECRET_FILE,dst=/run/secrets/client_secret,readonly" \
  --label 'traefik.enable=false' \
  "$IMAGE@$IMAGE_DIGEST" >/dev/null
if ! test "$(docker inspect "$PREFLIGHT" --format '{{.State.Running}}')" = true; then
  docker logs --tail 20 "$PREFLIGHT" >&2 || true
  echo 'google_probe_container_preflight_failed' >&2
  exit 1
fi

PREFLIGHT_HEALTHY=false
for attempt in $(seq 1 10); do
  if ! test "$(docker inspect "$PREFLIGHT" --format '{{.State.Running}}')" = true; then
    break
  fi
  if docker exec "$PREFLIGHT" python3 -c '
from urllib.request import Request, urlopen
request = Request("http://127.0.0.1:8092/auth/google/healthz", headers={"Host": "miscon.phireij.cloud"})
with urlopen(request, timeout=5) as response:
    assert response.status == 200
    assert response.read(100) == b"probe_ready;authority_effect=none"
' >/dev/null 2>&1; then
    PREFLIGHT_HEALTHY=true
    echo "google_probe_health_preflight_ready=true attempts=$attempt"
    break
  fi
  sleep 1
done
if [[ "$PREFLIGHT_HEALTHY" != true ]]; then
  docker logs --tail 20 "$PREFLIGHT" >&2 || true
  echo 'google_probe_health_preflight_failed' >&2
  exit 1
fi
docker rm -f "$PREFLIGHT" >/dev/null
PREFLIGHT_STARTED=false

if docker inspect "$CONTAINER" >/dev/null 2>&1; then
  test "$(docker inspect "$CONTAINER" --format '{{.State.Running}}')" = true
  docker rename "$CONTAINER" "$ROLLBACK"
  OLD_STAGED=true
  docker stop "$ROLLBACK" >/dev/null
fi

NEW_STARTED=true
docker run -d --name "$CONTAINER" --restart unless-stopped --network bridge \
  --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --env 'MISSION_CONTROL_GOOGLE_PROBE_ENABLED=true' \
  --env 'MISSION_CONTROL_GOOGLE_CLIENT_ID=531519060424-c2n6uclfuko18tubr9ejs9o2fhf8s4c1.apps.googleusercontent.com' \
  --env 'MISSION_CONTROL_GOOGLE_CLIENT_SECRET_FILE=/run/secrets/client_secret' \
  --mount "type=bind,src=$SECRET_FILE,dst=/run/secrets/client_secret,readonly" \
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
sleep 5
test "$(docker inspect "$CONTAINER" --format '{{.State.Running}}')" = true
test "$(docker inspect "$CONTAINER" --format '{{.Config.Image}}')" = "$IMAGE@$IMAGE_DIGEST"
test "$(docker inspect "$CONTAINER" --format '{{.HostConfig.NetworkMode}}')" = bridge
test "$(docker inspect "$CONTAINER" --format '{{.HostConfig.ReadonlyRootfs}}')" = true
AFTER="$(docker ps --format '{{.Names}}|{{.Image}}' | awk -F'|' -v c="$CONTAINER" '$1 != c' | sort)"
test "$BEFORE" = "$AFTER"
trap - ERR HUP INT TERM
echo "google_probe_activated=true image=$IMAGE@$IMAGE_DIGEST route=https://$HOSTNAME/auth/google existing_workloads_unchanged=true rollback_staged=$OLD_STAGED"
