#!/usr/bin/env python3
"""Pure, synthetic AO-MVP webhook ingress contract.

No socket binding, DNS, routes, credentials, external calls, or production mutation.
"""
import hashlib
import hmac
import json
import time

MAX_BODY_BYTES = 64 * 1024
MAX_SKEW_SECONDS = 300
SUPPORTED_CONTENT_TYPE = "application/json"

class Reject(Exception):
    pass

def _signature(secret: bytes, timestamp: int, nonce: str, body: bytes) -> str:
    msg = str(timestamp).encode() + b"." + nonce.encode() + b"." + body
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()

def evaluate_request(*, secret: bytes, headers: dict, body: bytes, now: int | None = None, seen_nonces=None):
    """Return sanitized metadata only when a synthetic request passes the contract."""
    if not secret:
        raise Reject("missing verifier secret")
    if len(body) > MAX_BODY_BYTES:
        raise Reject("body too large")
    if headers.get("content-type", "").split(";", 1)[0].strip().lower() != SUPPORTED_CONTENT_TYPE:
        raise Reject("unsupported content type")
    try:
        timestamp = int(headers["x-ao-timestamp"])
        nonce = headers["x-ao-nonce"]
        supplied = headers["x-ao-signature"]
    except (KeyError, TypeError, ValueError):
        raise Reject("missing authentication metadata")
    now = int(time.time()) if now is None else int(now)
    if abs(now - timestamp) > MAX_SKEW_SECONDS:
        raise Reject("stale request")
    if not nonce or len(nonce) > 128:
        raise Reject("invalid nonce")
    seen_nonces = set() if seen_nonces is None else seen_nonces
    if nonce in seen_nonces:
        raise Reject("replay")
    expected = _signature(secret, timestamp, nonce, body)
    if not hmac.compare_digest(expected, supplied):
        raise Reject("invalid signature")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise Reject("invalid json")
    if not isinstance(payload, dict) or set(payload) != {"event_id", "kind"}:
        raise Reject("invalid schema")
    if not isinstance(payload["event_id"], str) or not payload["event_id"]:
        raise Reject("invalid event_id")
    if payload["kind"] != "synthetic_canary":
        raise Reject("unsupported event kind")
    # Deliberately return no payload/body/secret/signature.
    return {"accepted": True, "event_id_hash": hashlib.sha256(payload["event_id"].encode()).hexdigest()[:16], "kind": "synthetic_canary", "authority_effect": "none"}

def synthetic_headers(secret: bytes, timestamp: int, nonce: str, body: bytes):
    return {
        "content-type": SUPPORTED_CONTENT_TYPE,
        "x-ao-timestamp": str(timestamp),
        "x-ao-nonce": nonce,
        "x-ao-signature": _signature(secret, timestamp, nonce, body),
    }
