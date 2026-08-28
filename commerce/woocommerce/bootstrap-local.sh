#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE=(docker compose -f "${ROOT_DIR}/docker-compose.dev.yml" --profile local-tools)
PORT="${WC_DEV_PORT:-8088}"
SITE_URL="http://127.0.0.1:${PORT}"

case "${SITE_URL}" in
  http://127.0.0.1:*) ;;
  *)
    echo "Refusing non-loopback WooCommerce bootstrap target: ${SITE_URL}" >&2
    exit 1
    ;;
esac

"${COMPOSE[@]}" up -d db wordpress

ready=0
for _ in $(seq 1 30); do
  if "${COMPOSE[@]}" run --rm wpcli db check >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done

if [[ "${ready}" -ne 1 ]]; then
  echo "Local WordPress database did not become ready" >&2
  exit 1
fi

if ! "${COMPOSE[@]}" run --rm wpcli core is-installed >/dev/null 2>&1; then
  "${COMPOSE[@]}" run --rm wpcli core install \
    --url="${SITE_URL}" \
    --title="Phil AI OS WooCommerce Local" \
    --admin_user="localadmin" \
    --admin_password="local-development-only" \
    --admin_email="local@example.invalid" \
    --skip-email
fi

"${COMPOSE[@]}" run --rm wpcli plugin install woocommerce --activate
"${COMPOSE[@]}" run --rm wpcli plugin status woocommerce

echo "PHIL_AI_OS_SPRINT_3_LOCAL_WOOCOMMERCE_BOOTSTRAP_GREEN"
