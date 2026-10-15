#!/usr/bin/env bash
# One-time key bootstrap for the still-inactive conversation store. The
# recovery passphrase arrives only on standard input and is never logged.
set -euo pipefail

: "${IMAGE_DIGEST:?Set the immutable digest of the active CEO-session image}"
: "${SECRET_VOLUME:?Set the protected CEO-session secret volume}"

[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
[[ "$SECRET_VOLUME" =~ ^phil-ai-os-mc-google-session-secret-[0-9]+-[0-9]+$ ]]

IMAGE=ghcr.io/phireij/phil-ai-os-platform/mission-control-google-ceo-session
SESSION=phil-ai-os-mission-control-google-ceo-session

test "$(docker inspect "$SESSION" --format '{{.State.Running}}')" = true
test "$(docker inspect "$SESSION" --format '{{.Config.Image}}')" = "$IMAGE@$IMAGE_DIGEST"
test "$(docker inspect "$SESSION" --format '{{.HostConfig.ReadonlyRootfs}}')" = true
test "$(docker volume inspect "$SECRET_VOLUME" --format '{{.Name}}')" = "$SECRET_VOLUME"

# The package contains only the key encrypted with the CEO-provided recovery
# passphrase. It is kept root-readable until the CEO retrieves it to offline
# storage. Neither plaintext nor passphrase is written to a log or artifact.
docker run --rm -i --network none --read-only --cap-drop ALL --cap-add CHOWN --cap-add DAC_OVERRIDE --security-opt no-new-privileges:true \
  --user 0:0 \
  --mount "type=volume,src=$SECRET_VOLUME,dst=/run/secrets" \
  --entrypoint python3 "$IMAGE@$IMAGE_DIGEST" \
  -c '
import base64
import json
import os
import secrets
import sys
import time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

secret_dir = "/run/secrets"
key_path = os.path.join(secret_dir, "conversation_key")
recovery_path = os.path.join(secret_dir, "conversation-key-recovery.v1.json")
passphrase = sys.stdin.buffer.readline().rstrip(b"\r\n")
if not 20 <= len(passphrase) <= 1024:
    raise SystemExit("conversation_key_bootstrap_blocked=recovery_passphrase_invalid")
def exists(path):
    try:
        os.lstat(path)
    except FileNotFoundError:
        return False
    return True

key_exists = exists(key_path)
recovery_exists = exists(recovery_path)
if recovery_exists:
    raise SystemExit("conversation_key_bootstrap_blocked=recovery_package_already_exists")
if key_exists:
    details = os.lstat(key_path)
    if os.path.islink(key_path) or not os.path.isfile(key_path) or details.st_uid != 10003 or details.st_mode & 0o077:
        raise SystemExit("conversation_key_bootstrap_blocked=existing_key_invalid")
    try:
        master_key = bytes.fromhex(open(key_path, "rt", encoding="ascii").read().strip())
    except (OSError, UnicodeError, ValueError) as exc:
        raise SystemExit("conversation_key_bootstrap_blocked=existing_key_invalid") from exc
    if len(master_key) != 32:
        raise SystemExit("conversation_key_bootstrap_blocked=existing_key_invalid")
else:
    master_key = secrets.token_bytes(32)
salt = secrets.token_bytes(16)
nonce = secrets.token_bytes(12)
kdf = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1)
wrapped = AESGCM(kdf.derive(passphrase)).encrypt(nonce, master_key, b"phil-ai-os-mission-control-conversation-recovery-v1")
payload = json.dumps({
    "format": "phil-ai-os-mission-control-conversation-recovery-v1",
    "created_at": int(time.time()),
    "kdf": {"name": "scrypt", "n": 32768, "r": 8, "p": 1, "salt": base64.b64encode(salt).decode("ascii")},
    "cipher": {"name": "aes-256-gcm", "nonce": base64.b64encode(nonce).decode("ascii"), "ciphertext": base64.b64encode(wrapped).decode("ascii")},
}, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"

created = []
try:
    if not key_exists:
        key_fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
        created.append(key_path)
        with os.fdopen(key_fd, "wb") as handle:
            handle.write(master_key.hex().encode("ascii") + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(key_path, 0o400)
        os.chown(key_path, 10003, 10003)

    recovery_fd = os.open(recovery_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    created.append(recovery_path)
    with os.fdopen(recovery_fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.chown(recovery_path, 0, 0)
    os.chmod(recovery_path, 0o400)
    details = os.lstat(recovery_path)
    if os.path.islink(recovery_path) or not os.path.isfile(recovery_path) or details.st_uid != 0 or details.st_mode & 0o077 or details.st_size < 128:
        raise SystemExit("conversation_key_bootstrap_blocked=recovery_package_verification_failed")
except BaseException:
    for path in reversed(created):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    raise
finally:
    master_key = b""
    passphrase = b""

print(f"conversation_key_bootstrap_completed=true recovery_package_repaired={str(key_exists).lower()} recovery_package_pending_offline_retrieval=true storage_initialized=false authority_effect=none")
'
