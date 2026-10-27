"""Fail-closed configuration contract for the R3 metadata writer.

This module is deliberately preparation only.  It validates the exact
configuration that a separately approved runtime integration would need, but
does not read the password, import a database driver, connect, write metadata,
start a listener, or authorize any action.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path


DATABASE_NAME = "mission_control"
WRITER_ROLE = "mission_control_attestation_writer"
DATABASE_HOST = "buzz-prod-postgres-1"
DATABASE_PORT = 5432
# The host file is root:app 0640 and is exposed read-only at this exact
# in-container path.  The host path is intentionally not accepted as a
# container configuration value.
WRITER_PASSWORD_PATH = Path("/run/secrets/attestation_writer_password")


class R3AttestationMetadataWriterConfigurationError(ValueError):
    """A non-secret configuration error safe for the audit record."""


@dataclass(frozen=True)
class R3AttestationMetadataWriterConfig:
    """Validated inputs for a future, separately approved metadata writer."""

    database_name: str
    writer_role: str
    database_host: str
    database_port: int
    password_file: Path
    activation_state: str = "metadata_writer_configured"
    authority_effect: str = "none"

    @classmethod
    def from_environment(cls) -> "R3AttestationMetadataWriterConfig":
        if os.environ.get("MISSION_CONTROL_R3_ATTESTATION_METADATA_WRITER_ENABLED") != "true":
            raise R3AttestationMetadataWriterConfigurationError("r3_attestation_metadata_writer_inactive")
        if os.environ.get("MISSION_CONTROL_R3_ATTESTATION_DATABASE") != DATABASE_NAME:
            raise R3AttestationMetadataWriterConfigurationError("r3_attestation_metadata_writer_database_invalid")
        if os.environ.get("MISSION_CONTROL_R3_ATTESTATION_WRITER_ROLE") != WRITER_ROLE:
            raise R3AttestationMetadataWriterConfigurationError("r3_attestation_metadata_writer_role_invalid")
        if os.environ.get("MISSION_CONTROL_R3_ATTESTATION_DATABASE_HOST") != DATABASE_HOST:
            raise R3AttestationMetadataWriterConfigurationError("r3_attestation_metadata_writer_host_invalid")
        if os.environ.get("MISSION_CONTROL_R3_ATTESTATION_DATABASE_PORT") != str(DATABASE_PORT):
            raise R3AttestationMetadataWriterConfigurationError("r3_attestation_metadata_writer_port_invalid")
        return cls(
            database_name=DATABASE_NAME,
            writer_role=WRITER_ROLE,
            database_host=DATABASE_HOST,
            database_port=DATABASE_PORT,
            password_file=_protected_password_file("MISSION_CONTROL_R3_ATTESTATION_WRITER_PASSWORD_FILE"),
        )


def _protected_password_file(variable: str) -> Path:
    raw = os.environ.get(variable, "")
    if raw != str(WRITER_PASSWORD_PATH):
        raise R3AttestationMetadataWriterConfigurationError("r3_attestation_metadata_writer_password_path_invalid")
    path = Path(raw)
    try:
        details = path.lstat()
    except OSError as error:
        raise R3AttestationMetadataWriterConfigurationError("r3_attestation_metadata_writer_password_unavailable") from error
    if not stat.S_ISREG(details.st_mode) or details.st_uid != 0 or not 32 <= details.st_size <= 4096:
        raise R3AttestationMetadataWriterConfigurationError("r3_attestation_metadata_writer_password_invalid")
    if (details.st_gid, stat.S_IMODE(details.st_mode)) != (10002, 0o640):
        raise R3AttestationMetadataWriterConfigurationError("r3_attestation_metadata_writer_password_permissions")
    return path
