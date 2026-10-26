#!/usr/bin/env bash
# Receives the client secret only on stdin and writes it atomically as root.
set -euo pipefail
: "${SECRET_FILE:?Set the canonical protected secret-file path}"
test "$SECRET_FILE" = /opt/phil-ai-os-platform/mission-control/secrets/google-identity-probe-client-secret
BACKUP_FILE="${SECRET_FILE}.rollback"
test ! -e "$BACKUP_FILE"
install -d -m 750 /opt/phil-ai-os-platform/mission-control/secrets
temporary="${SECRET_FILE}.new"
replaced=false
restore() { rm -f -- "$temporary"; if [[ "$replaced" == true ]]; then mv -f -- "$BACKUP_FILE" "$SECRET_FILE"; fi; }
trap restore EXIT HUP INT TERM
if [[ -e "$SECRET_FILE" ]]; then
  test "$(stat -c '%u:%g:%a' "$SECRET_FILE")" = '0:10002:640'
  mv -- "$SECRET_FILE" "$BACKUP_FILE"
  replaced=true
fi
umask 077
cat > "$temporary"
test -s "$temporary"
test "$(wc -c < "$temporary")" -le 4096
chown root:10002 "$temporary"
chmod 640 "$temporary"
mv -f -- "$temporary" "$SECRET_FILE"
test "$(stat -c '%u:%g:%a' "$SECRET_FILE")" = '0:10002:640'
trap - EXIT HUP INT TERM
echo "google_probe_host_secret_staged=true previous_secret_backed_up=$replaced"
