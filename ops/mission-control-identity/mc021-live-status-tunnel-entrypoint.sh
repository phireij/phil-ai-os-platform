#!/bin/sh
# Runtime credentials and tunnel identity are supplied only by the VPS process
# environment.  They are deliberately absent from this image and repository.
set -eu

profile="mc021-live-status-nonprod"
profile_dir="${TUNNEL_CLIENT_PROFILE_DIR:?}"

python3 -m operations_hub.mission_control_live_status_mcp_server &
mcp_pid="$!"

cleanup() {
  kill "$mcp_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

ready=0
for attempt in $(seq 1 30); do
  if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8788/healthz', timeout=1).read()"; then
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
  --mcp-server-url "http://127.0.0.1:8788/mcp" \
  --health-listen-addr "127.0.0.1:18081"

# Validates profile and control-plane authorization; it does not invoke the
# live-status MCP tool or either allowed Mission Control source.
tunnel-client doctor --profile "$profile" --profile-dir "$profile_dir"

exec tunnel-client run --profile "$profile" --profile-dir "$profile_dir"
