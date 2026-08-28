from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class CredentialBoundaryError(ValueError):
    """Raised when an authentication contract crosses the inert Sprint 3 boundary."""


@dataclass(frozen=True)
class CredentialReference:
    """Opaque reference to future WooCommerce credential material.

    This contract never stores consumer-key or consumer-secret values. A later,
    separately authorized production transport may resolve an opaque secret
    reference outside this package.
    """

    identity_alias: str
    secret_ref: str
    access_mode: str = "read_only"
    environment: str = "isolated"

    def __post_init__(self) -> None:
        if not self.identity_alias.strip():
            raise CredentialBoundaryError("credential identity_alias is required")
        if not self.secret_ref.strip():
            raise CredentialBoundaryError("credential secret_ref is required")
        if self.access_mode not in {"read_only", "read_write"}:
            raise CredentialBoundaryError("unsupported WooCommerce credential access_mode")
        if self.environment not in {"isolated", "production"}:
            raise CredentialBoundaryError("unsupported WooCommerce credential environment")
        lowered = self.secret_ref.lower()
        if lowered.startswith("ck_") or lowered.startswith("cs_"):
            raise CredentialBoundaryError("raw WooCommerce credential material is forbidden; use an opaque secret reference")


class CredentialReferenceProvider(Protocol):
    def get_reference(self) -> CredentialReference | None: ...


class NoCredentialsProvider:
    """Default Sprint 3 provider: deliberately exposes no credential reference."""

    def get_reference(self) -> None:
        return None


@dataclass(frozen=True)
class AuthenticationBoundary:
    """Describes the non-authorizing authentication posture of this foundation."""

    live_transport_present: bool = False
    raw_credentials_allowed: bool = False
    production_identity_present: bool = False
    resolution_authorized: bool = False

    def assert_inert(self) -> None:
        if any(
            (
                self.live_transport_present,
                self.raw_credentials_allowed,
                self.production_identity_present,
                self.resolution_authorized,
            )
        ):
            raise CredentialBoundaryError("Sprint 3 authentication boundary must remain inert")


SPRINT3_AUTH_BOUNDARY = AuthenticationBoundary()
