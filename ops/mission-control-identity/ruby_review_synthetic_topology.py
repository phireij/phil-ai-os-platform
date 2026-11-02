"""Test-only loopback composition for Ruby synthetic review paths.

The production CEO-session bootstrap deliberately leaves Ruby transport
unbound.  This module composes the existing in-process owner-session handler
with one disposable synthetic Core only in an explicit loopback test.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruby_review_synthetic_harness import (
    DisposableRubySyntheticHarness,
    RubySyntheticHarnessError,
)


class RubySyntheticTopologyError(ValueError):
    """A safe-to-log refusal to compose the test-only topology."""


@dataclass
class LoopbackRubySyntheticTopology:
    """One explicit binding on one existing loopback owner-session server."""

    server: Any
    harness: DisposableRubySyntheticHarness
    _closed: bool = False

    @classmethod
    def create_and_bind(
        cls,
        *,
        server: Any,
        storage_scope: Path,
        opt_in: str | None,
        owner_subject: str,
        issuer: str,
    ) -> "LoopbackRubySyntheticTopology":
        _require_loopback_owner_session(server, owner_subject)
        try:
            harness = DisposableRubySyntheticHarness.create(
                storage_scope=storage_scope,
                opt_in=opt_in,
                owner_subject=owner_subject,
                issuer=issuer,
            )
        except RubySyntheticHarnessError:
            raise
        try:
            server.ruby_review_transport_binding = harness.binding
            return cls(server, harness)
        except Exception:
            harness.cleanup()
            raise

    def close(self) -> None:
        if self._closed:
            return
        if getattr(self.server, "ruby_review_transport_binding", None) is self.harness.binding:
            self.server.ruby_review_transport_binding = None
        self.harness.cleanup()
        self._closed = True

    def __enter__(self) -> "LoopbackRubySyntheticTopology":
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()


def _require_loopback_owner_session(server: Any, owner_subject: str) -> None:
    address = getattr(server, "server_address", None)
    if not isinstance(address, tuple) or len(address) < 2:
        raise RubySyntheticTopologyError("ruby_synthetic_topology_server_invalid")
    try:
        if not ipaddress.ip_address(address[0]).is_loopback:
            raise RubySyntheticTopologyError("ruby_synthetic_topology_loopback_required")
    except ValueError as exc:
        raise RubySyntheticTopologyError("ruby_synthetic_topology_loopback_required") from exc
    if getattr(server, "ceo_subject", None) != owner_subject:
        raise RubySyntheticTopologyError("ruby_synthetic_topology_owner_mismatch")
    if getattr(server, "ruby_review_transport_binding", None) is not None:
        raise RubySyntheticTopologyError("ruby_synthetic_topology_binding_already_set")
