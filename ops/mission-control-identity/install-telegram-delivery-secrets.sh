#!/usr/bin/env bash
# Installs dedicated Mission Control Telegram secrets from standard input into
# the existing protected CEO-session secret volume. Values never reach logs.
set -euo pipefail

: "${IMAGE_DIGEST:?Set the reviewed CEO-session image digest}"
: "${SECRET_VOLUME:?Set the active CEO-session secret volume}"
[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "$SECRET_VOLUME" =~ ^phil-ai-os-mc-google-session-secret-[0-9]+-[0-9]+$ ]]
IMAGE=ghcr.io/phireij/phil-ai-os-platform/mission-control-google-ceo-session

docker run --rm -i --network none --read-only --cap-drop ALL --cap-add CHOWN --cap-add DAC_OVERRIDE --security-opt no-new-privileges:true \
  --user 0:0 --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets" \
  --entrypoint python3 "$IMAGE@$IMAGE_DIGEST" -c '
import os, re, sys
token = sys.stdin.buffer.readline().rstrip(b"\r\n")
chat = sys.stdin.buffer.readline().rstrip(b"\r\n")
if sys.stdin.buffer.readline(): raise SystemExit("telegram_secret_installation_blocked=unexpected_input")
if not re.fullmatch(rb"[0-9]{6,16}:[A-Za-z0-9_-]{20,256}", token): raise SystemExit("telegram_secret_installation_blocked=token_invalid")
if not re.fullmatch(rb"-?[0-9]{1,32}", chat) or chat == b"0": raise SystemExit("telegram_secret_installation_blocked=chat_invalid")
paths = [("/run/secrets/telegram_bot_token", token), ("/run/secrets/telegram_chat_id", chat)]
if any(os.path.lexists(path) for path, _ in paths): raise SystemExit("telegram_secret_installation_blocked=secret_already_exists")
created=[]
try:
  for path, value in paths:
    fd=os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o400); created.append(path)
    with os.fdopen(fd, "wb") as handle: handle.write(value+b"\n"); handle.flush(); os.fsync(handle.fileno())
    os.chown(path, 10003, 10003); os.chmod(path, 0o400)
  for path, _ in paths:
    details=os.lstat(path)
    if os.path.islink(path) or not os.path.isfile(path) or details.st_uid != 10003 or details.st_mode & 0o077: raise SystemExit("telegram_secret_installation_blocked=verification_failed")
except BaseException:
  for path in created:
    try: os.unlink(path)
    except FileNotFoundError: pass
  raise
finally:
  token=b""; chat=b""
print("telegram_secret_installation_completed=true authority_effect=none")
'
