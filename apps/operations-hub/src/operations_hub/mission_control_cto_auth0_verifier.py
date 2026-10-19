"""Fail-closed Auth0 JWT verification for the private MC-021 fixture.

This module never obtains tokens, creates clients, or maps a real person to the
fixture owner.  It verifies a caller-provided RS256 token only when an explicit
owner subject has been supplied to the local runtime configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urlsplit

from .mission_control_cto_tool import CEO_SUBJECT, VerifiedContext


ISSUER_ENV = "MCP_AUTHORIZATION_ISSUER"
JWKS_ENV = "MCP_AUTHORIZATION_JWKS_URI"
OWNER_SUBJECT_ENV = "MCP_OWNER_SUBJECT"


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
            raise ValueError("owner_subject_and_credential_required")
        decode, signing_key = self._jwt_primitives()
        claims = decode(
            credential,
            signing_key(credential),
            algorithms=["RS256"],
            audience=self.audience,
            issuer=self.issuer,
            options={"require": ["exp", "iat", "sub", "scope"]},
        )
        subject = claims.get("sub")
        scope = claims.get("scope")
        expiry = claims.get("exp")
        if subject != self.owner_subject or not isinstance(scope, str) or not isinstance(expiry, (int, float)):
            raise ValueError("owner_scope_or_expiry_invalid")
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


def verifier_from_environment(audience: str) -> Auth0JwtVerifier:
    return Auth0JwtVerifier(
        issuer=os.environ.get(ISSUER_ENV, ""),
        audience=audience,
        jwks_uri=os.environ.get(JWKS_ENV, ""),
        owner_subject=os.environ.get(OWNER_SUBJECT_ENV, ""),
    )
