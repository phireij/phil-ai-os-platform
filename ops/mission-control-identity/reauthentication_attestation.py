"""Offline, short-lived reauthentication-attestation primitives.

This module does not read configuration, start a listener, authenticate a
browser, retain a raw identity subject, or authorize a Mission Control action.
A future identity service may use it only after independently verifying an OIDC
reauthentication event and obtaining a protected signing key.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
from dataclasses import dataclass


ATTESTATION_AUDIENCE = "mission-control-r3"
ATTESTATION_TTL_SECONDS = 5 * 60
_TOKEN_VERSION = "v1"
_ATTESTATION_ID = re.compile(r"^[A-Za-z0-9_-]{22,128}$")
_SUBJECT_MAX_LENGTH = 255


class ReauthenticationAttestationError(ValueError):
    """A safe-to-log attestation issuance or verification error."""


@dataclass(frozen=True)
class VerifiedReauthenticationAttestation:
    attestation_id: str
    issuer: str
    subject_sha256: str
    authenticated_at_epoch: int
    expires_at_epoch: int
    audience: str = ATTESTATION_AUDIENCE


class SingleUseAttestationRegistry:
    """Bounded in-memory replay protection for an eventual identity service.

    Entries contain opaque identifiers only and are automatically removed after
    their attestation expiry. This class deliberately has no persistence;
    production retention/audit storage needs an independently reviewed design.
    """

    def __init__(self, maximum_entries: int = 100) -> None:
        if not isinstance(maximum_entries, int) or isinstance(maximum_entries, bool) or maximum_entries < 1:
            raise ReauthenticationAttestationError("attestation_registry_limit_invalid")
        self._maximum_entries = maximum_entries
        self._consumed_until: dict[str, int] = {}
        self._lock = threading.Lock()

    def consume(self, attestation: VerifiedReauthenticationAttestation, now_epoch_seconds: int) -> None:
        _validate_now(now_epoch_seconds)
        with self._lock:
            self._expired(now_epoch_seconds)
            if attestation.attestation_id in self._consumed_until:
                raise ReauthenticationAttestationError("attestation_already_consumed")
            if len(self._consumed_until) >= self._maximum_entries:
                raise ReauthenticationAttestationError("attestation_registry_full")
            self._consumed_until[attestation.attestation_id] = attestation.expires_at_epoch

    def _expired(self, now_epoch_seconds: int) -> None:
        for attestation_id, expires_at in list(self._consumed_until.items()):
            if expires_at < now_epoch_seconds:
                del self._consumed_until[attestation_id]


def issue_attestation(
    *,
    signing_key: bytes,
    issuer: str,
    subject: str,
    authenticated_at_epoch: int,
    attestation_id: str | None = None,
) -> str:
    """Create an opaque, HMAC-authenticated five-minute R3 proof.

    The serialized token includes only the SHA-256 digest of the identity
    subject. Callers must never log the returned bearer token.
    """

    _validate_signing_key(signing_key)
    _validate_issuer(issuer)
    _validate_subject(subject)
    _validate_now(authenticated_at_epoch)
    token_id = attestation_id if attestation_id is not None else secrets.token_urlsafe(24)
    if not isinstance(token_id, str) or not _ATTESTATION_ID.fullmatch(token_id):
        raise ReauthenticationAttestationError("attestation_id_invalid")
    claims = {
        "attestation_id": token_id,
        "audience": ATTESTATION_AUDIENCE,
        "authenticated_at_epoch": authenticated_at_epoch,
        "expires_at_epoch": authenticated_at_epoch + ATTESTATION_TTL_SECONDS,
        "issuer": issuer,
        "subject_sha256": _subject_digest(subject),
    }
    encoded_claims = _encode_claims(claims)
    signature = hmac.new(signing_key, encoded_claims.encode("ascii"), hashlib.sha256).digest()
    return _TOKEN_VERSION + "." + encoded_claims + "." + _b64(signature)


def verify_attestation(
    *,
    token: str,
    signing_key: bytes,
    expected_issuer: str,
    expected_subject: str,
    now_epoch_seconds: int,
) -> VerifiedReauthenticationAttestation:
    """Verify a proof's signature, binding, format, and five-minute lifetime."""

    _validate_signing_key(signing_key)
    _validate_issuer(expected_issuer)
    _validate_subject(expected_subject)
    _validate_now(now_epoch_seconds)
    if not isinstance(token, str) or len(token) > 4096:
        raise ReauthenticationAttestationError("attestation_token_invalid")
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != _TOKEN_VERSION or not parts[1] or not parts[2]:
        raise ReauthenticationAttestationError("attestation_token_invalid")
    encoded_claims, encoded_signature = parts[1:]
    try:
        supplied_signature = _unb64(encoded_signature)
    except ValueError as error:
        raise ReauthenticationAttestationError("attestation_signature_invalid") from error
    expected_signature = hmac.new(signing_key, encoded_claims.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise ReauthenticationAttestationError("attestation_signature_invalid")
    claims = _decode_claims(encoded_claims)
    required_keys = {
        "attestation_id",
        "audience",
        "authenticated_at_epoch",
        "expires_at_epoch",
        "issuer",
        "subject_sha256",
    }
    if set(claims) != required_keys:
        raise ReauthenticationAttestationError("attestation_claims_invalid")
    attestation_id = claims["attestation_id"]
    authenticated_at = claims["authenticated_at_epoch"]
    expires_at = claims["expires_at_epoch"]
    if not isinstance(attestation_id, str) or not _ATTESTATION_ID.fullmatch(attestation_id):
        raise ReauthenticationAttestationError("attestation_claims_invalid")
    if claims["audience"] != ATTESTATION_AUDIENCE or claims["issuer"] != expected_issuer:
        raise ReauthenticationAttestationError("attestation_binding_mismatch")
    if claims["subject_sha256"] != _subject_digest(expected_subject):
        raise ReauthenticationAttestationError("attestation_binding_mismatch")
    if (
        not isinstance(authenticated_at, int)
        or isinstance(authenticated_at, bool)
        or not isinstance(expires_at, int)
        or isinstance(expires_at, bool)
        or expires_at - authenticated_at != ATTESTATION_TTL_SECONDS
        or authenticated_at > now_epoch_seconds
        or now_epoch_seconds > expires_at
    ):
        raise ReauthenticationAttestationError("attestation_expired_or_invalid")
    return VerifiedReauthenticationAttestation(
        attestation_id=attestation_id,
        issuer=claims["issuer"],
        subject_sha256=claims["subject_sha256"],
        authenticated_at_epoch=authenticated_at,
        expires_at_epoch=expires_at,
    )


def _validate_signing_key(signing_key: bytes) -> None:
    if not isinstance(signing_key, bytes) or len(signing_key) < 32:
        raise ReauthenticationAttestationError("attestation_signing_key_invalid")


def _validate_issuer(issuer: str) -> None:
    if not isinstance(issuer, str) or not issuer or len(issuer) > 255:
        raise ReauthenticationAttestationError("attestation_issuer_invalid")


def _validate_subject(subject: str) -> None:
    if not isinstance(subject, str) or not subject or len(subject) > _SUBJECT_MAX_LENGTH:
        raise ReauthenticationAttestationError("attestation_subject_invalid")


def _validate_now(now_epoch_seconds: int) -> None:
    if not isinstance(now_epoch_seconds, int) or isinstance(now_epoch_seconds, bool) or now_epoch_seconds <= 0:
        raise ReauthenticationAttestationError("attestation_time_invalid")


def _subject_digest(subject: str) -> str:
    return "sha256:" + hashlib.sha256(subject.encode("utf-8")).hexdigest()


def _encode_claims(claims: dict[str, object]) -> str:
    return _b64(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _decode_claims(encoded_claims: str) -> dict[str, object]:
    try:
        decoded = json.loads(_unb64(encoded_claims))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReauthenticationAttestationError("attestation_claims_invalid") from error
    if not isinstance(decoded, dict):
        raise ReauthenticationAttestationError("attestation_claims_invalid")
    return decoded


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    if not isinstance(value, str) or not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("base64url_invalid")
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
