from __future__ import annotations

from dataclasses import dataclass


class StaleInventoryRevision(ValueError):
    """Raised when an older inventory revision attempts to replace a newer one."""


class InventoryConflictError(ValueError):
    """Raised when the inventory source/revision history is internally inconsistent."""


@dataclass(frozen=True)
class InventoryRevisionState:
    source_of_truth: str
    revision: int
    payload_fingerprint: str


class MemoryInventoryRevisionStore:
    """In-memory revision guard for isolated Sprint 3 reconciliation tests.

    This is deliberately not a production persistence mechanism. It establishes
    fail-closed stale/conflict semantics before any live WooCommerce activation.
    """

    def __init__(self) -> None:
        self._states: dict[str, InventoryRevisionState] = {}

    def assert_accept(
        self,
        *,
        sku: str,
        source_of_truth: str,
        revision: int,
        payload_fingerprint: str,
    ) -> None:
        current = self._states.get(sku)
        if current is None:
            return
        if source_of_truth != current.source_of_truth:
            raise InventoryConflictError(
                f"inventory source conflict for {sku}: {current.source_of_truth} -> {source_of_truth}"
            )
        if revision < current.revision:
            raise StaleInventoryRevision(
                f"stale inventory revision for {sku}: {revision} < {current.revision}"
            )
        if revision == current.revision and payload_fingerprint != current.payload_fingerprint:
            raise InventoryConflictError(
                f"inventory revision {revision} for {sku} has conflicting payloads"
            )

    def record(
        self,
        *,
        sku: str,
        source_of_truth: str,
        revision: int,
        payload_fingerprint: str,
    ) -> None:
        self._states[sku] = InventoryRevisionState(
            source_of_truth=source_of_truth,
            revision=revision,
            payload_fingerprint=payload_fingerprint,
        )

    def get(self, sku: str) -> InventoryRevisionState | None:
        return self._states.get(sku)
