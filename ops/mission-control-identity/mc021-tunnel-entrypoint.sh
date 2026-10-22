#!/bin/sh
# The runtime key is supplied only by the VPS environment at launch.  It is
# deliberately absent from this image, profile, repository and stdout.
set -eu

profile="mc021-nonprod"
profile_dir="${TUNNEL_CLIENT_PROFILE_DIR:?}"

python3 -m operations_hub.mission_control_cto_mcp_server &
fixture_pid="$!"

cleanup() {
  kill "$fixture_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

ready=0
for attempt in $(seq 1 30); do
  if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/healthz', timeout=1).read()"; then
    ready=1
    break
  fi
  sleep 1
done
test "$ready" = 1

mkdir -p "$profile_dir"
tunnel-client init \
  --profile "$profile" \
  --profile-dir "$profile_dir" \
  --force \
  --tunnel-id "${CONTROL_PLANE_TUNNEL_ID:?}" \
  --mcp-server-url "http://127.0.0.1:8787/mcp" \
  --health-listen-addr "127.0.0.1:18080"

# This verifies the client profile and control-plane authorization.  It never
# calls the MCP tool, which is intentionally still fail-closed without an
# approved owner credential.
tunnel-client doctor --profile "$profile" --profile-dir "$profile_dir"

exec tunnel-client run --profile "$profile" --profile-dir "$profile_dir"
