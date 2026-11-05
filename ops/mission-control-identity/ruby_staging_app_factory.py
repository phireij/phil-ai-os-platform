"""Default-off composition of the real staging backend and WSGI application.

Explicit trusted startup inputs only. No environment/file/CLI credential loader,
listener, server configuration or identity defaults. Call only after worker fork
under a separately reviewed single-process lifecycle; never preload an enabled
instance in a master or share its pools, locks or in-memory state across forks.
Successful construction does not authenticate anyone or authorize execution.
"""
from __future__ import annotations

import math
import time
from typing import Callable

from ruby_staging_google_auth import StagingGoogleOwnerAuthenticator
from ruby_staging_http_app import StagingHTTPApplication, StagingHTTPConfig, StagingRequestLimits


class StagingFactoryConfigurationError(ValueError):
    """Fixed startup failure; never includes supplied configuration or secrets."""


def create_staging_application(*, enabled: bool = False,
        config: StagingHTTPConfig | None = None,
        limits: StagingRequestLimits | None = None,
        client_secret: str | None = None,
        max_cache_seconds: int | None = None,
        wall_clock: Callable[[], float] = time.time,
        monotonic_clock: Callable[[], float] = time.monotonic) -> StagingHTTPApplication:
    """Build one owned backend and app, or return the default inactive app.

All static policies and initial clocks are validated before a Session is
allocated. The backend validates its secret/cache/wall clock before allocation;
this function validates the app's complete policy and monotonic clock first.
Future clock reads remain the existing components' responsibility.

The factory owns its backend until app construction succeeds. On failure it
closes what it owns before redacting ordinary exceptions; control exceptions
propagate unchanged. Cleanup is best effort during Python unwinding, not a
guarantee for SIGKILL/process death or a Session constructor that never returns.
The returned app owns the backend and must be closed by its future runtime.
"""
    if enabled is False:
        # Do not inspect supplied secret, config, limits or clocks when inactive.
        return StagingHTTPApplication()
    try:
        if (enabled is not True or type(config) is not StagingHTTPConfig
                or type(limits) is not StagingRequestLimits
                or not callable(wall_clock) or not callable(monotonic_clock)):
            raise ValueError
        config.validate()
        limits.validate()
        now = monotonic_clock()
        if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
            raise ValueError
    except Exception:
        raise StagingFactoryConfigurationError("staging_factory_configuration_invalid") from None

    backend = None
    try:
        backend = StagingGoogleOwnerAuthenticator(
            origin=config.origin, client_id=config.client_id,
            owner_subject=config.owner_subject, client_secret=client_secret,
            max_cache_seconds=max_cache_seconds, enabled=True, clock=wall_clock)
        # This public constructor revalidates the policy match and transfers
        # exclusive ownership only after successful enabled construction.
        return StagingHTTPApplication(config=config, enabled=True,
            authenticator=backend, limits=limits, clock=monotonic_clock)
    except BaseException as failure:
        if backend is not None:
            try:
                backend.close()
            except BaseException:
                pass
        if isinstance(failure, Exception):
            raise StagingFactoryConfigurationError("staging_factory_configuration_invalid") from None
        raise
