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
from ruby_staging_http_app import StagingHTTPApplication, StagingHTTPConfig, StagingRequestLimits, StagingOwnerQuoteBinding, StagingOwnerWorkbenchAssets, StagingOwnerIntakeAssets


class StagingFactoryConfigurationError(ValueError):
    """Fixed startup failure; never includes supplied configuration or secrets."""


def create_staging_application(*, enabled: bool = False,
        config: StagingHTTPConfig | None = None,
        limits: StagingRequestLimits | None = None,
        client_secret: str | None = None,
        max_cache_seconds: int | None = None,
        owner_quote_binding: StagingOwnerQuoteBinding | None = None,
        owner_workbench_assets: StagingOwnerWorkbenchAssets | None = None,
        owner_intake_assets: StagingOwnerIntakeAssets | None = None,
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
        if owner_quote_binding is not None:
            from ruby_staging_id_token import ISSUER
            if (type(owner_quote_binding) is not StagingOwnerQuoteBinding or
                    not owner_quote_binding.matches_policy(issuer=ISSUER, owner_subject=config.owner_subject)):
                raise ValueError
        if owner_workbench_assets is not None:
            if (type(owner_workbench_assets) is not StagingOwnerWorkbenchAssets or
                    owner_workbench_assets.binding is not owner_quote_binding):
                raise ValueError
            owner_workbench_assets.__post_init__()
        if owner_intake_assets is not None:
            if (type(owner_intake_assets) is not StagingOwnerIntakeAssets or
                    owner_intake_assets.binding is not owner_quote_binding):
                raise ValueError
            owner_intake_assets.__post_init__()
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
            authenticator=backend, limits=limits, clock=monotonic_clock,
            owner_quote_binding=owner_quote_binding, owner_workbench_assets=owner_workbench_assets,
            owner_intake_assets=owner_intake_assets)
    except BaseException as failure:
        if backend is not None:
            try:
                backend.close()
            except BaseException as cleanup:
                if isinstance(failure, Exception) and not isinstance(cleanup, Exception):
                    raise cleanup
        if isinstance(failure, Exception):
            raise StagingFactoryConfigurationError("staging_factory_configuration_invalid") from None
        raise
