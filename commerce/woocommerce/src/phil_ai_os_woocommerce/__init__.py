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
from .audit import CommerceSyncAuditEvent, MemoryAuditSink
from .category_plan import (
    CategoryHierarchyError,
    CategoryPlanItem,
    plan_category_hierarchy,
    project_category_payload,
)
from .inventory_guard import (
    InventoryConflictError,
    InventoryRevisionState,
    MemoryInventoryRevisionStore,
    StaleInventoryRevision,
)
from .media_plan import MediaPlanError, build_product_media_plan
from .models import CategoryRecord, InventoryRecord, LocalizedText, MediaRecord, ProductRecord
from .resilience import (
    FailureInjectingTransport,
    HTTPStatusFailure,
    RetryExecutionResult,
    execute_with_retry,
)
from .retry import RetryDecision, retry_decision
from .reconciliation import MemoryIdempotencyStore, ReconciliationResult

__all__ = [
    "CategoryHierarchyError",
    "CategoryPlanItem",
    "CategoryRecord",
    "CommerceSyncAuditEvent",
    "FailureInjectingTransport",
    "HTTPStatusFailure",
    "InventoryConflictError",
    "InventoryRecord",
    "InventoryRevisionState",
    "LocalizedText",
    "MediaPlanError",
    "MediaRecord",
    "MemoryAuditSink",
    "MemoryIdempotencyStore",
    "MemoryInventoryRevisionStore",
    "MockWooCommerceTransport",
    "ProductRecord",
    "ProductionConnectivityBlocked",
    "ReconciliationResult",
    "RetryDecision",
    "RetryExecutionResult",
    "StaleInventoryRevision",
    "WooCommerceAdapter",
    "build_product_media_plan",
    "execute_with_retry",
    "plan_category_hierarchy",
    "project_category_payload",
    "retry_decision",
]
