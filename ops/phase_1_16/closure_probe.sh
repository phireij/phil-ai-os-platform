#!/usr/bin/env bash
set -euo pipefail

echo '=== SERVICE STATE ==='
echo "monitor_active=$(systemctl is-active phil-ai-os-monitor.service || true)"
echo "monitor_enabled=$(systemctl is-enabled phil-ai-os-monitor.service || true)"
curl -fsS --max-time 5 http://127.0.0.1:4870/healthz >/dev/null
curl -fsS --max-time 5 http://127.0.0.1:4870/readyz >/dev/null
echo 'control_api_health=ok'

echo '=== CONTROL API ENDPOINT STATUS DISCOVERY ==='
for p in \
  /v1/runtime/status \
  /v1/runtime-snapshot \
  /v1/runtime/snapshot \
  /v1/system-metadata \
  /v1/mission-control \
  /v1/mission-control/snapshot \
  /v1/audit-consistency \
  /v1/audit/consistency \
  /v1/audit-integrity \
  /v1/audit/integrity \
  /v1/safety \
  /v1/safety/snapshot \
  /v1/status; do
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:4870${p}" || true)
  echo "${p}=${code}"
done

echo '=== CONTROL API CONTAINER DISCOVERY ==='
CONTROL=$(docker ps --format '{{.Names}}' | grep -m1 -E 'control[-_]?api|phil.*control' || true)
if [ -n "$CONTROL" ]; then
  echo 'control_container=found'
  echo "control_container_name=$CONTROL"
  echo 'control_mount_destinations:'
  docker inspect "$CONTROL" --format '{{range .Mounts}}{{println .Destination}}{{end}}' | sed '/^$/d' | head -n 50
  echo 'control_env_key_names:'
  docker inspect "$CONTROL" --format '{{range .Config.Env}}{{println .}}{{end}}' | cut -d= -f1 | sort -u | grep -Ei 'TOKEN|AUTH|MISSION|AUDIT|RUNTIME|SAFETY|EXECUTION|ROUT|LIVE|KILL' | head -n 100 || true
  echo 'control_route_strings:'
  docker exec "$CONTROL" sh -lc 'grep -RhoE "\"/v1/[A-Za-z0-9_./{}:-]+\"|\x27/v1/[A-Za-z0-9_./{}:-]+\x27" /app 2>/dev/null | tr -d "\"\x27" | sort -u | grep -Ei "audit|mission|runtime|safety|status|approval" | head -n 100' || true
else
  echo 'control_container=not_found'
fi

echo '=== HERMES CONFIG DISCOVERY ==='
HERMES=$(docker ps --format '{{.Names}}' | grep -m1 'hermes' || true)
if [ -n "$HERMES" ]; then
  echo 'hermes_container=found'
  echo "hermes_container_name=$HERMES"
  echo 'hermes_mount_destinations:'
  docker inspect "$HERMES" --format '{{range .Mounts}}{{println .Destination}}{{end}}' | sed '/^$/d' | head -n 50
  echo 'hermes_candidate_config_files:'
  docker exec "$HERMES" sh -lc 'find / -maxdepth 4 -type f \( -iname "*telegram*" -o -iname "*config*" -o -iname "*.env" \) 2>/dev/null | head -n 100' || true
  echo 'hermes_telegram_key_names_from_text_files:'
  docker exec "$HERMES" sh -lc 'grep -RhoE "[A-Za-z_][A-Za-z0-9_]*(TELEGRAM|BOT_TOKEN|CHAT_ID)[A-Za-z0-9_]*[[:space:]]*[:=]" /root /app /config /data 2>/dev/null | sed -E "s/[[:space:]]*[:=]$//" | sort -u | head -n 100' || true
else
  echo 'hermes_container=not_found'
fi

echo '=== MONITOR LOG HEALTH ==='
journalctl -u phil-ai-os-monitor.service -n 20 --no-pager | sed -E 's/[0-9]{6,}:[A-Za-z0-9_-]{20,}/[REDACTED_TOKEN]/g' | tail -n 20

echo 'PHIL_AI_OS_PHASE_1_16_DEEP_CLOSURE_PROBE_OK'
