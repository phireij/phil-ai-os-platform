"""Private, INSERT-only R3 attestation metadata persistence.

This is not an action adapter. It only persists the pre-approved metadata
shape after a verified R3 reauthentication proof has been produced. It never
receives a raw subject, bearer proof, authorization code, access token, action
body, or authority-bearing flag. The driver is imported only at write time so
offline configuration checks remain dependency-free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from r3_attestation_handoff import R3AttestationMetadata
from r3_attestation_metadata_writer_config import R3AttestationMetadataWriterConfig


_ATTESTATION_ID = re.compile(r"^[A-Za-z0-9_-]{22,128}$")
_SHA256 = re.compile(r"^sha256:[a-f0-9]{64}$")
_VERIFICATION_ID = re.compile(r"^r3v_[A-Za-z0-9_-]{22,128}$")
_INSERT = """
INSERT INTO mission_control.r3_reauthentication_attestations (
    attestation_id, issuer, subject_sha256, attestation_digest, verification_id,
    authenticated_at, expires_at, state, retention_expires_at,
    execution_authorized, mutation_authorized, authority_effect
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING
"""


class R3AttestationMetadataWriterError(ValueError):
    """A non-secret error safe for an audit record."""


@dataclass(frozen=True)
class R3AttestationMetadataWriteResult:
    verification_id: str
    persisted: bool
    authority_effect: str = "none"


class R3AttestationMetadataWriter:
    """Persist an approved metadata row through the dedicated writer role."""

    def __init__(self, config: R3AttestationMetadataWriterConfig) -> None:
        self._config = config

    @classmethod
    def from_environment(cls) -> "R3AttestationMetadataWriter":
        return cls(R3AttestationMetadataWriterConfig.from_environment())

    def write(self, metadata: R3AttestationMetadata) -> R3AttestationMetadataWriteResult:
        values = _validated_values(metadata)
        password = _read_password(self._config.password_file)
        try:
            import psycopg

            with psycopg.connect(
                host=self._config.database_host,
                port=self._config.database_port,
                dbname=self._config.database_name,
                user=self._config.writer_role,
                password=password,
                connect_timeout=3,
                application_name="mission-control-r3-attestation-writer",
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(_INSERT, values)
                    persisted = cursor.rowcount == 1
        except Exception as error:
            raise R3AttestationMetadataWriterError("r3_attestation_metadata_writer_persistence_failed") from error
        return R3AttestationMetadataWriteResult(
            verification_id=metadata.verification_id,
            persisted=persisted,
        )


def _validated_values(metadata: R3AttestationMetadata) -> tuple[object, ...]:
    if not isinstance(metadata, R3AttestationMetadata):
        raise R3AttestationMetadataWriterError("r3_attestation_metadata_writer_metadata_invalid")
    if (
        not _ATTESTATION_ID.fullmatch(metadata.attestation_id)
        or metadata.issuer != "https://accounts.google.com"
        or not _SHA256.fullmatch(metadata.subject_sha256)
        or not _SHA256.fullmatch(metadata.attestation_digest)
        or not _VERIFICATION_ID.fullmatch(metadata.verification_id)
        or metadata.state != "issued"
        or metadata.execution_authorized is not False
        or metadata.mutation_authorized is not False
        or metadata.authority_effect != "none"
    ):
        raise R3AttestationMetadataWriterError("r3_attestation_metadata_writer_metadata_invalid")
    for value in (metadata.authenticated_at_epoch, metadata.expires_at_epoch, metadata.retention_expires_at_epoch):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise R3AttestationMetadataWriterError("r3_attestation_metadata_writer_metadata_invalid")
    if not metadata.authenticated_at_epoch < metadata.expires_at_epoch <= metadata.retention_expires_at_epoch:
        raise R3AttestationMetadataWriterError("r3_attestation_metadata_writer_metadata_invalid")
    return (
        metadata.attestation_id,
        metadata.issuer,
        metadata.subject_sha256,
        metadata.attestation_digest,
        metadata.verification_id,
        datetime.fromtimestamp(metadata.authenticated_at_epoch, timezone.utc),
        datetime.fromtimestamp(metadata.expires_at_epoch, timezone.utc),
        metadata.state,
        datetime.fromtimestamp(metadata.retention_expires_at_epoch, timezone.utc),
        False,
        False,
        "none",
    )


def _read_password(path) -> str:
    try:
        value = path.read_text(encoding="utf-8")
    except OSError as error:
        raise R3AttestationMetadataWriterError("r3_attestation_metadata_writer_password_unavailable") from error
    if not value.endswith("\n") or value.count("\n") != 1 or not 32 <= len(value) - 1 <= 4096:
        raise R3AttestationMetadataWriterError("r3_attestation_metadata_writer_password_invalid")
    return value[:-1]
