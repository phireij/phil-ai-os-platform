#!/usr/bin/env bash
# Receives the client secret only on stdin and writes it atomically as root.
set -euo pipefail
: "${SECRET_FILE:?Set the canonical protected secret-file path}"
test "$SECRET_FILE" = /opt/phil-ai-os-platform/mission-control/secrets/google-identity-probe-client-secret
test ! -e "$SECRET_FILE"
install -d -m 750 /opt/phil-ai-os-platform/mission-control/secrets
temporary="${SECRET_FILE}.new"
trap 'rm -f -- "$temporary"' EXIT HUP INT TERM
umask 077
cat > "$temporary"
test -s "$temporary"
test "$(wc -c < "$temporary")" -le 4096
chown root:10002 "$temporary"
chmod 640 "$temporary"
mv -f -- "$temporary" "$SECRET_FILE"
test "$(stat -c '%u:%g:%a' "$SECRET_FILE")" = '0:10002:640'
trap - EXIT HUP INT TERM
echo 'google_probe_host_secret_staged=true'
