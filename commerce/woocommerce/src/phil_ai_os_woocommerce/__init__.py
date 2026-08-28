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
from .audit import CommerceSyncAuditEvent
from .inventory_guard import (
    InventoryConflictError,
    InventoryRevisionState,
    MemoryInventoryRevisionStore,
    StaleInventoryRevision,
)
from .models import CategoryRecord, InventoryRecord, LocalizedText, MediaRecord, ProductRecord
from .retry import RetryDecision, retry_decision
from .reconciliation import MemoryIdempotencyStore, ReconciliationResult

__all__ = [
    "CategoryRecord",
    "CommerceSyncAuditEvent",
    "InventoryConflictError",
    "InventoryRecord",
    "InventoryRevisionState",
    "LocalizedText",
    "MediaRecord",
    "MemoryIdempotencyStore",
    "MemoryInventoryRevisionStore",
    "MockWooCommerceTransport",
    "ProductRecord",
    "ProductionConnectivityBlocked",
    "ReconciliationResult",
    "RetryDecision",
    "StaleInventoryRevision",
    "WooCommerceAdapter",
    "retry_decision",
]
