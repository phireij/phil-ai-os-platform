#!/usr/bin/env bash
set -euo pipefail

# Phase 1.16 mount-source probe; read-only and secret-value safe.
echo '=== SERVICE STATE ==='
echo "monitor_active=$(systemctl is-active phil-ai-os-monitor.service || true)"
echo "monitor_enabled=$(systemctl is-enabled phil-ai-os-monitor.service || true)"
curl -fsS --max-time 5 http://127.0.0.1:4870/healthz >/dev/null
curl -fsS --max-time 5 http://127.0.0.1:4870/readyz >/dev/null
echo 'control_api_health=ok'

echo '=== CONTROL API ENDPOINT STATUS DISCOVERY ==='
for p in \
  /v1/runtime/status \
  /v1/mission-control/snapshot \
  /v1/audit-consistency \
  /v1/audit/integrity \
  /v1/safety/snapshot; do
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:4870${p}" || true)
  echo "${p}=${code}"
done

echo '=== HERMES SECRET/CONFIG MOUNT SOURCES ==='
HERMES=$(docker ps --format '{{.Names}}' | grep -m1 'hermes' || true)
if [ -n "$HERMES" ]; then
  echo 'hermes_container=found'
  docker inspect "$HERMES" --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}' \
    | grep -E -- '-> /opt/data$|-> /opt/data/.env$|-> /run/philaios/hermes_control_api_token$' \
    || true
else
  echo 'hermes_container=not_found'
fi

echo '=== MONITOR LOG HEALTH ==='
journalctl -u phil-ai-os-monitor.service -n 10 --no-pager | tail -n 10

echo 'PHIL_AI_OS_PHASE_1_16_MOUNT_PROBE_OK'
