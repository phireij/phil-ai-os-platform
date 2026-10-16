#!/usr/bin/env bash
# Installs dedicated Mission Control Telegram secrets from standard input into
# the existing protected CEO-session secret volume. Values never reach logs.
set -euo pipefail

: "${IMAGE_DIGEST:?Set the reviewed CEO-session image digest}"
: "${SECRET_VOLUME:?Set the active CEO-session secret volume}"
[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "$SECRET_VOLUME" =~ ^phil-ai-os-mc-google-session-secret-[0-9]+-[0-9]+$ ]]
IMAGE=ghcr.io/phireij/phil-ai-os-platform/mission-control-google-ceo-session

docker run --rm -i --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --user 10003:10003 --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets" \
  --entrypoint python3 "$IMAGE@$IMAGE_DIGEST" -c '
import hmac, os, re, sys
token = sys.stdin.buffer.readline().rstrip(b"\r\n")
chat = sys.stdin.buffer.readline().rstrip(b"\r\n")
if sys.stdin.buffer.readline(): raise SystemExit("telegram_secret_installation_blocked=unexpected_input")
if not re.fullmatch(rb"[0-9]{6,16}:[A-Za-z0-9_-]{20,256}", token): raise SystemExit("telegram_secret_installation_blocked=token_invalid")
if not re.fullmatch(rb"-?[0-9]{1,32}", chat) or chat == b"0": raise SystemExit("telegram_secret_installation_blocked=chat_invalid")
secret_dir = "/run/secrets/telegram"
directory = os.lstat(secret_dir)
if os.path.islink(secret_dir) or not os.path.isdir(secret_dir) or (directory.st_mode & 0o7777) != 0o1733:
  raise SystemExit("telegram_secret_installation_blocked=directory_invalid")
paths = [(f"{secret_dir}/bot_token", token), (f"{secret_dir}/chat_id", chat)]
exists = [os.path.lexists(path) for path, _ in paths]
rotation = os.environ.get("MISSION_CONTROL_TELEGRAM_SECRET_ROTATION", "")
if rotation not in {"", "chat_id"}:
  raise SystemExit("telegram_secret_installation_blocked=rotation_invalid")
if any(exists):
  if not all(exists): raise SystemExit("telegram_secret_installation_blocked=partial_secret_state")
  for path, _ in paths:
    details = os.lstat(path)
    if os.path.islink(path) or not os.path.isfile(path) or details.st_uid != 10003 or (details.st_mode & 0o7777) != 0o400 or details.st_size < 2 or details.st_size > 512:
      raise SystemExit("telegram_secret_installation_blocked=existing_secret_invalid")
  existing_token = open(f"{secret_dir}/bot_token", "rb").read().rstrip(b"\r\n")
  if not hmac.compare_digest(existing_token, token):
    raise SystemExit("telegram_secret_installation_blocked=token_mismatch")
  if rotation == "chat_id":
    replacement = f"{secret_dir}/chat_id.replacement"
    if os.path.lexists(replacement):
      raise SystemExit("telegram_secret_installation_blocked=replacement_exists")
    fd = os.open(replacement, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o400)
    try:
      with os.fdopen(fd, "wb") as handle:
        handle.write(chat+b"\n"); handle.flush(); os.fsync(handle.fileno())
      os.chmod(replacement, 0o400)
      details = os.lstat(replacement)
      if os.path.islink(replacement) or not os.path.isfile(replacement) or details.st_uid != 10003 or (details.st_mode & 0o7777) != 0o400:
        raise SystemExit("telegram_secret_installation_blocked=replacement_invalid")
      os.replace(replacement, f"{secret_dir}/chat_id")
    except BaseException:
      try: os.unlink(replacement)
      except FileNotFoundError: pass
      raise
    token=b""; chat=b""; existing_token=b""
    print("telegram_secret_installation_completed=true chat_id_rotated=true authority_effect=none")
    raise SystemExit(0)
  token=b""; chat=b""
  print("telegram_secret_installation_completed=true reused_existing=true authority_effect=none")
  raise SystemExit(0)
if rotation:
  raise SystemExit("telegram_secret_installation_blocked=rotation_requires_existing")
created=[]
try:
  for path, value in paths:
    fd=os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o400); created.append(path)
    with os.fdopen(fd, "wb") as handle: handle.write(value+b"\n"); handle.flush(); os.fsync(handle.fileno())
    os.chmod(path, 0o400)
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
