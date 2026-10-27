"""Default-off, internal-only R3 reauthentication handoff preparation.

This module may issue a short-lived attestation only after the caller has
verified a Google OIDC subject and the exact CEO subject is available from a
protected host file.  It deliberately has no listener, database connection,
route, action adapter, or logging.  Its token is an internal bearer value and
must never be returned to a browser, persisted, or logged.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from pathlib import Path

from reauthentication_attestation import (
    ATTESTATION_TTL_SECONDS,
    ReauthenticationAttestationError,
    VerifiedReauthenticationAttestation,
    issue_attestation,
    verify_attestation,
)
from r3_attestation_handoff_config import R3AttestationHandoffConfig


METADATA_RETENTION_SECONDS = 365 * 24 * 60 * 60
_SUBJECT_SHA256 = re.compile(r"^sha256:[a-f0-9]{64}$")


class R3AttestationHandoffError(ValueError):
    """A safe-to-log handoff preparation error."""


@dataclass(frozen=True)
class R3AttestationMetadata:
    """Metadata allowed in the dedicated Mission Control database.

    No raw subject, proof, signing key, authorization code, access token, or
    action body is represented here.  Both authority flags must remain false.
    """

    attestation_id: str
    issuer: str
    subject_sha256: str
    attestation_digest: str
    verification_id: str
    authenticated_at_epoch: int
    expires_at_epoch: int
    retention_expires_at_epoch: int
    state: str = "issued"
    execution_authorized: bool = False
    mutation_authorized: bool = False
    authority_effect: str = "none"


@dataclass(frozen=True)
class IssuedR3Attestation:
    """Internal-only result; callers must handle ``token`` as a bearer value."""

    token: str
    metadata: R3AttestationMetadata


class R3AttestationHandoff:
    """Prepare an opaque R3 proof after exact protected-subject comparison."""

    def __init__(self, config: R3AttestationHandoffConfig) -> None:
        self._config = config

    @classmethod
    def from_environment(cls) -> "R3AttestationHandoff":
        return cls(R3AttestationHandoffConfig.from_environment())

    def issue_for_verified_subject(
        self, *, verified_subject: str, authenticated_at_epoch: int
    ) -> IssuedR3Attestation:
        """Issue a five-minute proof, retaining only safe metadata in the result."""

        _validate_verified_subject(verified_subject)
        expected_subject_digest = _read_subject_digest(self._config.ceo_subject_file)
        supplied_subject_digest = _subject_digest(verified_subject)
        if not hmac.compare_digest(supplied_subject_digest, expected_subject_digest):
            raise R3AttestationHandoffError("r3_attestation_handoff_subject_mismatch")
        signing_key = _read_signing_key(self._config.signing_key_file)
        try:
            token = issue_attestation(
                signing_key=signing_key,
                issuer=self._config.issuer,
                subject=verified_subject,
                authenticated_at_epoch=authenticated_at_epoch,
            )
            verified = verify_attestation(
                token=token,
                signing_key=signing_key,
                expected_issuer=self._config.issuer,
                expected_subject=verified_subject,
                now_epoch_seconds=authenticated_at_epoch,
            )
        except ReauthenticationAttestationError as error:
            raise R3AttestationHandoffError("r3_attestation_handoff_issuance_invalid") from error
        return IssuedR3Attestation(token=token, metadata=_metadata(verified, token))


def _metadata(verified: VerifiedReauthenticationAttestation, token: str) -> R3AttestationMetadata:
    return R3AttestationMetadata(
        attestation_id=verified.attestation_id,
        issuer=verified.issuer,
        subject_sha256=verified.subject_sha256,
        attestation_digest="sha256:" + hashlib.sha256(token.encode("ascii")).hexdigest(),
        verification_id="r3v_" + secrets.token_urlsafe(24),
        authenticated_at_epoch=verified.authenticated_at_epoch,
        expires_at_epoch=verified.expires_at_epoch,
        retention_expires_at_epoch=verified.expires_at_epoch + METADATA_RETENTION_SECONDS,
    )


def _validate_verified_subject(subject: str) -> None:
    if not isinstance(subject, str) or not subject or len(subject) > 255:
        raise R3AttestationHandoffError("r3_attestation_handoff_verified_subject_invalid")


def _read_subject_digest(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8")
    except OSError as error:
        raise R3AttestationHandoffError("r3_attestation_handoff_subject_unavailable") from error
    if not value.endswith("\n") or value.count("\n") != 1:
        raise R3AttestationHandoffError("r3_attestation_handoff_subject_format_invalid")
    digest = value[:-1]
    if not _SUBJECT_SHA256.fullmatch(digest):
        raise R3AttestationHandoffError("r3_attestation_handoff_subject_format_invalid")
    return digest


def _subject_digest(subject: str) -> str:
    return "sha256:" + hashlib.sha256(subject.encode("utf-8")).hexdigest()


def _read_signing_key(path: Path) -> bytes:
    try:
        value = path.read_bytes()
    except OSError as error:
        raise R3AttestationHandoffError("r3_attestation_handoff_signing_key_unavailable") from error
    if len(value) < 32:
        raise R3AttestationHandoffError("r3_attestation_handoff_signing_key_invalid")
    return value
