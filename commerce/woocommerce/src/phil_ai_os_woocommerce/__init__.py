"""Phil AI OS WooCommerce foundation package.

Sprint 3 boundary: this package contains contracts, reconciliation logic, and
mock/injected adapter behavior only. It intentionally ships no live WooCommerce
network transport or production credentials.
"""

from .adapter import (
    MockWooCommerceTransport,
    ProductionConnectivityBlocked,
    WooCommerceAdapter,
)
from .models import CategoryRecord, InventoryRecord, LocalizedText, MediaRecord, ProductRecord
from .reconciliation import MemoryIdempotencyStore, ReconciliationResult

__all__ = [
    "CategoryRecord",
    "InventoryRecord",
    "LocalizedText",
    "MediaRecord",
    "MemoryIdempotencyStore",
    "MockWooCommerceTransport",
    "ProductRecord",
    "ProductionConnectivityBlocked",
    "ReconciliationResult",
    "WooCommerceAdapter",
]
