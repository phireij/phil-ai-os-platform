"""Fail-closed Google OIDC configuration for the inactive CEO session service.

This module performs configuration validation only. It does not start a listener,
exchange authorization codes, create a session, or grant conversation access.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path


ISSUER = "https://accounts.google.com"
REDIRECT_URI = "https://miscon.phireij.cloud/auth/google/callback"
CONVERSATION_SCOPE = "mission_control:conversation"
CLIENT_ID = "531519060424-c2n6uclfuko18tubr9ejs9o2fhf8s4c1.apps.googleusercontent.com"


class GoogleOidcConfigurationError(ValueError):
    """A non-secret, safe-to-log configuration error."""


@dataclass(frozen=True)
class GoogleOidcConfig:
    issuer: str
    redirect_uri: str
    client_id: str
    client_secret_file: Path
    ceo_subject_file: Path
    conversation_scope: str = CONVERSATION_SCOPE

    @classmethod
    def from_environment(cls) -> "GoogleOidcConfig":
        if os.environ.get("MISSION_CONTROL_GOOGLE_OIDC_ENABLED") != "true":
            raise GoogleOidcConfigurationError("google_oidc_inactive")

        if os.environ.get("MISSION_CONTROL_GOOGLE_OIDC_ISSUER") != ISSUER:
            raise GoogleOidcConfigurationError("google_oidc_issuer_invalid")
        if os.environ.get("MISSION_CONTROL_GOOGLE_REDIRECT_URI") != REDIRECT_URI:
            raise GoogleOidcConfigurationError("google_oidc_redirect_invalid")

        client_id = os.environ.get("MISSION_CONTROL_GOOGLE_CLIENT_ID", "")
        if client_id != CLIENT_ID:
            raise GoogleOidcConfigurationError("google_oidc_client_id_invalid")

        secret_file = _protected_file("MISSION_CONTROL_GOOGLE_CLIENT_SECRET_FILE")
        subject_file = _protected_file("MISSION_CONTROL_GOOGLE_CEO_SUBJECT_FILE")
        return cls(
            issuer=ISSUER,
            redirect_uri=REDIRECT_URI,
            client_id=client_id,
            client_secret_file=secret_file,
            ceo_subject_file=subject_file,
        )


def _protected_file(variable: str) -> Path:
    raw = os.environ.get(variable, "")
    if not raw or not Path(raw).is_absolute():
        raise GoogleOidcConfigurationError("google_oidc_protected_file_unset")
    path = Path(raw)
    try:
        details = path.lstat()
        if not stat.S_ISREG(details.st_mode):
            raise GoogleOidcConfigurationError("google_oidc_protected_file_invalid")
        if details.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise GoogleOidcConfigurationError("google_oidc_protected_file_permissions")
        if details.st_size == 0:
            raise GoogleOidcConfigurationError("google_oidc_protected_file_empty")
    except OSError as exc:
        raise GoogleOidcConfigurationError("google_oidc_protected_file_unavailable") from exc
    return path
