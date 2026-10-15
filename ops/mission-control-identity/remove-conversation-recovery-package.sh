#!/usr/bin/env bash
# One-way, owner-approved removal of only the on-host encrypted recovery
# package after the CEO has confirmed offline custody. It never touches the
# live conversation key or state volume.
set -euo pipefail

: "${IMAGE_DIGEST:?Set the reviewed immutable CEO-session image digest}"
: "${SECRET_VOLUME:?Set the protected Docker secret volume name}"

[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "$SECRET_VOLUME" =~ ^phil-ai-os-mc-google-session-secret-[0-9]+-[0-9]+$ ]]

IMAGE=ghcr.io/phireij/phil-ai-os-platform/mission-control-google-ceo-session
SESSION=phil-ai-os-mission-control-google-ceo-session
PACKAGE=/run/secrets/conversation-key-recovery.v1.json
KEY=/run/secrets/conversation_key

test "$(docker inspect "$SESSION" --format '{{.State.Running}}')" = true
test "$(docker inspect "$SESSION" --format '{{.Config.Image}}')" = "$IMAGE@$IMAGE_DIGEST"
test "$(docker inspect "$SESSION" --format '{{.HostConfig.ReadonlyRootfs}}')" = true
test "$(docker inspect "$SESSION" --format '{{range .Mounts}}{{if eq .Destination "/run/secrets"}}{{.Name}}{{end}}{{end}}')" = "$SECRET_VOLUME"
test "$(docker volume inspect "$SECRET_VOLUME" --format '{{.Name}}')" = "$SECRET_VOLUME"
test "$(docker image inspect "$IMAGE@$IMAGE_DIGEST" --format '{{.Id}}')" != ''

# The mounted secret volume is the exact target. Python uses lstat so a link
# cannot redirect removal. No recovery content is read or printed.
docker run --rm --network none --read-only --cap-drop ALL --cap-add DAC_OVERRIDE --cap-add FOWNER \
  --security-opt no-new-privileges:true --user 0:0 \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets" \
  --entrypoint python3 "$IMAGE@$IMAGE_DIGEST" \
  -c 'import os
from pathlib import Path

package = Path("/run/secrets/conversation-key-recovery.v1.json")
key = Path("/run/secrets/conversation_key")
key_details = key.lstat()
details = package.lstat()
if package.is_symlink() or not package.is_file() or details.st_uid != 0 or details.st_mode & 0o077 or not 128 <= details.st_size <= 65536:
    raise SystemExit("conversation_recovery_package_removal_blocked=package_invalid")
if key.is_symlink() or not key.is_file() or key_details.st_uid != 10003 or key_details.st_mode & 0o077 or key_details.st_size < 64:
    raise SystemExit("conversation_recovery_package_removal_blocked=live_key_invalid")
os.unlink(package)
if package.exists():
    raise SystemExit("conversation_recovery_package_removal_blocked=package_still_present")
if not key.exists():
    raise SystemExit("conversation_recovery_package_removal_blocked=live_key_missing")
print("conversation_recovery_package_removed=true live_key_retained=true state_unchanged=true")'

test "$(docker inspect "$SESSION" --format '{{.State.Running}}')" = true
echo 'conversation_recovery_package_removal_completed=true live_key_retained=true state_unchanged=true existing_workloads_unchanged=true'
