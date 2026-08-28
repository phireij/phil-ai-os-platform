from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .adapter import MockWooCommerceTransport


class MockRollbackError(ValueError):
    pass


@dataclass(frozen=True)
class MockCommerceSnapshot:
    """Isolated-test snapshot of mock commerce state.

    This is deliberately limited to MockWooCommerceTransport. It is evidence for
    deterministic rollback semantics only; it is not a production backup or
    rollback mechanism.
    """

    products: dict[int, dict[str, Any]]
    categories: dict[int, dict[str, Any]]
    next_product_id: int
    next_category_id: int


def capture_mock_snapshot(transport: MockWooCommerceTransport) -> MockCommerceSnapshot:
    if not isinstance(transport, MockWooCommerceTransport):
        raise MockRollbackError("Sprint 3 rollback snapshots are mock-transport only")
    return MockCommerceSnapshot(
        products=deepcopy(transport._products),
        categories=deepcopy(transport._categories),
        next_product_id=int(transport._next_id),
        next_category_id=int(transport._next_category_id),
    )


def restore_mock_snapshot(
    transport: MockWooCommerceTransport,
    snapshot: MockCommerceSnapshot,
) -> None:
    if not isinstance(transport, MockWooCommerceTransport):
        raise MockRollbackError("Sprint 3 rollback restore is mock-transport only")
    if snapshot.next_product_id < 1 or snapshot.next_category_id < 1:
        raise MockRollbackError("invalid mock snapshot identity counters")
    transport._products = deepcopy(snapshot.products)
    transport._categories = deepcopy(snapshot.categories)
    transport._next_id = int(snapshot.next_product_id)
    transport._next_category_id = int(snapshot.next_category_id)
