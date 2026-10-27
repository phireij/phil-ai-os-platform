"""Fail-closed configuration contract for the internal R3 attestation handoff.

This module neither reads a signing key nor starts an integration. It only
validates the exact opt-in configuration a separately approved runtime would
need to mount from protected host files.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path


ISSUER = "https://accounts.google.com"
# The root:app 0640 host key is exposed read-only only at this in-container
# location. The host path is never accepted as runtime configuration.
SIGNING_KEY_PATH = Path("/run/secrets/r3_signing_key")


class R3AttestationHandoffConfigurationError(ValueError):
    """A non-secret configuration error safe for an audit record."""


@dataclass(frozen=True)
class R3AttestationHandoffConfig:
    issuer: str
    signing_key_file: Path
    ceo_subject_file: Path
    activation_state: str = "design_only_inactive"
    authority_effect: str = "none"

    @classmethod
    def from_environment(cls) -> "R3AttestationHandoffConfig":
        if os.environ.get("MISSION_CONTROL_R3_ATTESTATION_HANDOFF_ENABLED") != "true":
            raise R3AttestationHandoffConfigurationError("r3_attestation_handoff_inactive")
        if os.environ.get("MISSION_CONTROL_R3_ATTESTATION_ISSUER") != ISSUER:
            raise R3AttestationHandoffConfigurationError("r3_attestation_handoff_issuer_invalid")
        signing_key_file = _protected_signing_key("MISSION_CONTROL_R3_ATTESTATION_SIGNING_KEY_FILE")
        ceo_subject_file = _protected_subject_file("MISSION_CONTROL_GOOGLE_CEO_SUBJECT_FILE")
        return cls(issuer=ISSUER, signing_key_file=signing_key_file, ceo_subject_file=ceo_subject_file)


def _protected_signing_key(variable: str) -> Path:
    raw = os.environ.get(variable, "")
    if raw != str(SIGNING_KEY_PATH):
        raise R3AttestationHandoffConfigurationError("r3_attestation_handoff_signing_key_path_invalid")
    return _protected_file(Path(raw), variable, required_mode=0o640, required_group=10002, minimum_size=32)


def _protected_subject_file(variable: str) -> Path:
    raw = os.environ.get(variable, "")
    if not raw or not Path(raw).is_absolute():
        raise R3AttestationHandoffConfigurationError("r3_attestation_handoff_subject_file_invalid")
    return _protected_file(Path(raw), variable, required_mode=None, required_group=None, minimum_size=1)


def _protected_file(path: Path, variable: str, *, required_mode: int | None, required_group: int | None, minimum_size: int) -> Path:
    try:
        details = path.lstat()
    except OSError as error:
        raise R3AttestationHandoffConfigurationError("r3_attestation_handoff_protected_file_unavailable") from error
    if not stat.S_ISREG(details.st_mode) or details.st_uid != 0 or details.st_size < minimum_size or details.st_size > 4096:
        raise R3AttestationHandoffConfigurationError("r3_attestation_handoff_protected_file_invalid")
    mode = stat.S_IMODE(details.st_mode)
    if required_mode is not None and (details.st_gid, mode) != (required_group, required_mode):
        raise R3AttestationHandoffConfigurationError("r3_attestation_handoff_signing_key_permissions")
    if required_mode is None and details.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise R3AttestationHandoffConfigurationError("r3_attestation_handoff_subject_file_permissions")
    return path
