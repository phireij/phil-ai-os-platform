"""Fail-closed Auth0 JWT verification for the private MC-021 fixture.

This module never obtains tokens, creates clients, or maps a real person to the
fixture owner.  It verifies a caller-provided RS256 token only when an explicit
owner subject has been supplied to the local runtime configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from .mission_control_cto_tool import CEO_SUBJECT, VerifiedContext


ISSUER_ENV = "MCP_AUTHORIZATION_ISSUER"
JWKS_ENV = "MCP_AUTHORIZATION_JWKS_URI"
OWNER_SUBJECT_FILE_ENV = "MCP_OWNER_SUBJECT_FILE"


class CredentialRejected(ValueError):
    """A fixed, redacted credential rejection category for diagnostics."""

    def __init__(self, category: str) -> None:
        super().__init__(category)
        self.category = category


def _https_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return (
        isinstance(value, str)
        and value == value.strip()
        and parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
    )


def _owner_subject_from_encrypted_credential() -> str:
    """Read the owner identity only from the runtime credential mount.

    The encrypted credential is decrypted by systemd into an in-memory,
    read-only path before the container starts.  Keeping the value out of an
    environment variable prevents it appearing in process inspection output.
    """

    credential_path = os.environ.get(OWNER_SUBJECT_FILE_ENV, "")
    path = Path(credential_path)
    if not credential_path or not credential_path.startswith("/"):
        raise ValueError("owner_subject_credential_path_required")
    try:
        owner_subject = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError("owner_subject_credential_unreadable") from exc
    if not owner_subject or any(character.isspace() for character in owner_subject):
        raise ValueError("owner_subject_credential_invalid")
    return owner_subject


@dataclass(frozen=True)
class Auth0JwtVerifier:
    """Convert only a validated owner token into the fixture's trusted context."""

    issuer: str
    audience: str
    jwks_uri: str
    owner_subject: str
    _decode: Callable[..., dict] | None = None
    _signing_key: Callable[[str], object] | None = None

    def __post_init__(self) -> None:
        if not _https_url(self.issuer) or not _https_url(self.audience) or not _https_url(self.jwks_uri):
            raise ValueError("https_issuer_audience_and_jwks_required")

    def __call__(self, credential: str) -> VerifiedContext:
        # Leaving owner_subject blank keeps the deployed fixture non-callable
        # until a later, separately approved owner-identity mapping exists.
        if not self.owner_subject or not isinstance(credential, str) or not credential:
            raise CredentialRejected("owner_mapping_invalid")
        decode, signing_key = self._jwt_primitives()
        try:
            claims = decode(
                credential,
                signing_key(credential),
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "sub", "scope"]},
            )
        except Exception as exc:
            raise CredentialRejected(_jwt_rejection_category(exc)) from exc
        subject = claims.get("sub")
        scope = claims.get("scope")
        expiry = claims.get("exp")
        if subject != self.owner_subject:
            raise CredentialRejected("owner_mismatch")
        if not isinstance(scope, str) or not isinstance(expiry, (int, float)):
            raise CredentialRejected("required_claim_missing")
        return VerifiedContext(
            subject=CEO_SUBJECT,
            audience=self.audience,
            scopes=frozenset(scope.split()),
            expires_at=datetime.fromtimestamp(expiry, tz=timezone.utc),
        )

    def _jwt_primitives(self) -> tuple[Callable[..., dict], Callable[[str], object]]:
        if self._decode is not None and self._signing_key is not None:
            return self._decode, self._signing_key
        from jwt import PyJWKClient, decode  # Installed only in the isolated runtime image.

        client = PyJWKClient(self.jwks_uri, cache_jwk_set=True, lifespan=300)
        return decode, lambda token: client.get_signing_key_from_jwt(token).key


def _jwt_rejection_category(exc: Exception) -> str:
    """Map verifier failures to fixed labels without retaining exception detail."""

    return {
        "ExpiredSignatureError": "token_expired",
        "InvalidAudienceError": "audience_mismatch",
        "InvalidIssuerError": "issuer_mismatch",
        "InvalidSignatureError": "signature_invalid",
        "InvalidAlgorithmError": "signature_invalid",
        "MissingRequiredClaimError": "required_claim_missing",
        "PyJWKClientError": "signature_unavailable",
    }.get(type(exc).__name__, "token_verification_failed")


def verifier_from_environment(audience: str) -> Auth0JwtVerifier:
    return Auth0JwtVerifier(
        issuer=os.environ.get(ISSUER_ENV, ""),
        audience=audience,
        jwks_uri=os.environ.get(JWKS_ENV, ""),
        owner_subject=_owner_subject_from_encrypted_credential(),
    )
