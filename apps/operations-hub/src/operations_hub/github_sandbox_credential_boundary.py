"""Pure credential-boundary checks for the dormant GitHub sandbox pilot.

This module accepts only public file metadata and non-secret numeric/time values.
It never opens a private-key file, creates a JWT, requests an installation token,
uses a network client, or dispatches a GitHub operation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath


class GitHubSandboxCredentialBoundaryError(ValueError):
    """Raised when public credential-boundary evidence is insufficient."""


EXPECTED_PRIVATE_KEY_PATH = PurePosixPath(
    "/opt/phil-ai-os-platform/mission-control/secrets/github-sandbox-pilot/private-key.pem"
)
EXPECTED_PRIVATE_KEY_MODE = 0o400
EXPECTED_SECRET_DIRECTORY_MODE = 0o700
_CLOCK_SKEW_SECONDS = 60
_MAX_JWT_LIFETIME_SECONDS = 600
_DEFAULT_JWT_LIFETIME_SECONDS = 540


@dataclass(frozen=True)
class PrivateKeyFileMetadata:
    """Public metadata only; no key value or file handle is representable."""

    path: PurePosixPath
    is_regular_file: bool
    file_owner_uid: int
    file_mode: int
    parent_owner_uid: int
    parent_mode: int


@dataclass(frozen=True)
class CredentialBoundaryPreview:
    """A successful metadata check that still grants no credential authority."""

    private_key_path: str
    state: str = "metadata_valid_runtime_inactive"
    key_read_authorized: bool = False
    jwt_authorized: bool = False
    token_request_authorized: bool = False
    dispatch_authorized: bool = False
    authority_effect: str = "none"

    def as_record(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class GitHubAppJwtTimingPreview:
    """Non-secret JWT timing constraints for a future separately activated worker."""

    issued_at: int
    expires_at: int
    state: str = "timing_valid_runtime_inactive"
    jwt_authorized: bool = False
    authority_effect: str = "none"

    def as_record(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class InstallationTokenScopePreview:
    """Pinned token scope expressed without creating or requesting a token."""

    installation_id: int
    repository_id: int
    permissions: tuple[str, ...] = ("issues:write",)
    state: str = "scope_valid_runtime_inactive"
    token_request_authorized: bool = False
    authority_effect: str = "none"

    def as_record(self) -> dict[str, object]:
        return asdict(self)


def validate_private_key_metadata(metadata: PrivateKeyFileMetadata) -> CredentialBoundaryPreview:
    """Validate the fixed secret-file boundary without opening the key file."""

    if not isinstance(metadata, PrivateKeyFileMetadata):
        raise GitHubSandboxCredentialBoundaryError("github_sandbox_key_metadata_invalid")
    if metadata.path != EXPECTED_PRIVATE_KEY_PATH:
        raise GitHubSandboxCredentialBoundaryError("github_sandbox_key_path_not_allowlisted")
    if not metadata.is_regular_file:
        raise GitHubSandboxCredentialBoundaryError("github_sandbox_key_not_regular_file")
    if metadata.file_owner_uid != 0 or metadata.parent_owner_uid != 0:
        raise GitHubSandboxCredentialBoundaryError("github_sandbox_key_owner_invalid")
    if metadata.file_mode != EXPECTED_PRIVATE_KEY_MODE:
        raise GitHubSandboxCredentialBoundaryError("github_sandbox_key_mode_invalid")
    if metadata.parent_mode != EXPECTED_SECRET_DIRECTORY_MODE:
        raise GitHubSandboxCredentialBoundaryError("github_sandbox_key_parent_mode_invalid")
    return CredentialBoundaryPreview(private_key_path=str(metadata.path))


def preview_jwt_timing(now_epoch_seconds: int, lifetime_seconds: int = _DEFAULT_JWT_LIFETIME_SECONDS) -> GitHubAppJwtTimingPreview:
    """Return a conservative, non-secret timing window without generating a JWT."""

    if not isinstance(now_epoch_seconds, int) or isinstance(now_epoch_seconds, bool) or now_epoch_seconds <= 0:
        raise GitHubSandboxCredentialBoundaryError("github_sandbox_jwt_clock_invalid")
    if not isinstance(lifetime_seconds, int) or isinstance(lifetime_seconds, bool) or not 1 <= lifetime_seconds <= _MAX_JWT_LIFETIME_SECONDS:
        raise GitHubSandboxCredentialBoundaryError("github_sandbox_jwt_lifetime_invalid")
    return GitHubAppJwtTimingPreview(
        issued_at=now_epoch_seconds - _CLOCK_SKEW_SECONDS,
        expires_at=now_epoch_seconds + lifetime_seconds,
    )


def preview_installation_token_scope(installation_id: int, repository_id: int) -> InstallationTokenScopePreview:
    """Validate a one-installation, one-repository issue-write scope preview."""

    for value, error in ((installation_id, "github_sandbox_installation_id_invalid"), (repository_id, "github_sandbox_repository_id_invalid")):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise GitHubSandboxCredentialBoundaryError(error)
    return InstallationTokenScopePreview(installation_id=installation_id, repository_id=repository_id)
